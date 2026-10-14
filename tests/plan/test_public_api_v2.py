"""Exercise the approved public contract with explicit synthetic examples."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contracts/schemas/public_api_v2.json"
EXAMPLES_PATH = ROOT / "contracts/schemas/public_api_v2_examples.json"


class PublicApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.examples = json.loads(EXAMPLES_PATH.read_text(encoding="utf-8"))

    def validator(self, definition: str) -> Draft202012Validator:
        schema = {**self.schema, "$ref": f"#/$defs/{definition}"}
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def test_schema_is_valid_and_contains_eight_public_objects(self) -> None:
        Draft202012Validator.check_schema(self.schema)
        names = {
            "NormalizedIntel",
            "Vulnerability",
            "Advisory",
            "Component",
            "Enrichment",
            "Relation",
            "Citation",
            "QAAnswer",
        }
        self.assertTrue(names.issubset(self.schema["$defs"]))

    def test_declared_examples_obey_positive_and_negative_contracts(self) -> None:
        self.assertTrue(self.examples["is_synthetic"])
        for polarity, expected in (("valid", True), ("invalid", False)):
            for definition, examples in self.examples[polarity].items():
                for example in examples:
                    with self.subTest(polarity=polarity, definition=definition):
                        self.assertEqual(self.validator(definition).is_valid(example), expected)

    def test_task_handle_needs_no_answer_and_cannot_pretend_to_be_completed(self) -> None:
        task = copy.deepcopy(self.examples["valid"]["AskResult"][0])
        self.assertNotIn("answer_text", task)
        self.assertTrue(self.validator("AskResult").is_valid(task))
        task["answer_text"] = "pretend completed"
        self.assertFalse(self.validator("AskResult").is_valid(task))

    def test_sync_stack_accepts_200_and_rejects_201(self) -> None:
        component = {"ecosystem": "PyPI", "package_name": "synthetic", "version": None}
        self.assertTrue(
            self.validator("StackCheckRequest").is_valid({"components": [component] * 200})
        )
        self.assertFalse(
            self.validator("StackCheckRequest").is_valid({"components": [component] * 201})
        )

    def test_large_manifest_uses_separate_bounded_upload(self) -> None:
        request = {
            "upload_id": "00000000-0000-4000-8000-000000000001",
            "size_bytes": 10 * 1024 * 1024,
            "declared_component_count": 10000,
            "format": "json_components",
        }
        validator = self.validator("StackUploadRequest")
        self.assertTrue(validator.is_valid(request))
        request["size_bytes"] += 1
        self.assertFalse(validator.is_valid(request))
        request["size_bytes"] -= 1
        request["declared_component_count"] += 1
        self.assertFalse(validator.is_valid(request))

    def test_all_four_assessment_states_are_preserved_and_clean_is_rejected(self) -> None:
        result = copy.deepcopy(self.examples["invalid"]["StackCheckResult"][0])
        for status in (
            "supported_applicability",
            "excluded_with_evidence",
            "insufficient_evidence",
            "conflicting_evidence",
        ):
            result["results"][0]["status"] = status
            result["results"][0]["reason_code"] = "synthetic_boundary"
            with self.subTest(status=status):
                self.assertTrue(self.validator("StackCheckResult").is_valid(result))
        result["results"][0]["status"] = "clean"
        self.assertFalse(self.validator("StackCheckResult").is_valid(result))

    def test_self_reported_tenant_and_bad_timestamp_are_rejected(self) -> None:
        request = {"question": "synthetic question", "mode": "library", "tenant_id": "other"}
        self.assertFalse(self.validator("AskRequest").is_valid(request))
        task = copy.deepcopy(self.examples["valid"]["AskResult"][0])
        task["created_at"] = "2026-10-14T20:00:00"
        self.assertFalse(self.validator("AskResult").is_valid(task))

    def test_question_and_context_limits(self) -> None:
        validator = self.validator("AskRequest")
        self.assertTrue(validator.is_valid({"question": "x" * 4096, "mode": "auto"}))
        self.assertFalse(validator.is_valid({"question": "x" * 4097, "mode": "auto"}))
        request = {
            "question": "synthetic question",
            "mode": "auto",
            "asset_ids": ["00000000-0000-4000-8000-000000000001"] * 21,
        }
        self.assertFalse(validator.is_valid(request))

    def test_source_facts_require_support_and_no_match_remains_unknown(self) -> None:
        answer = copy.deepcopy(self.examples["valid"]["AskResult"][1])
        answer["claims"] = [{"text": "synthetic claim", "kind": "source_fact", "support_ids": []}]
        self.assertFalse(self.validator("AskResult").is_valid(answer))
        result = copy.deepcopy(self.examples["invalid"]["StackCheckResult"][0])
        result["results"][0]["status"] = "excluded_with_evidence"
        self.assertFalse(self.validator("StackCheckResult").is_valid(result))
        result["results"][0]["status"] = "insufficient_evidence"
        self.assertTrue(self.validator("StackCheckResult").is_valid(result))


if __name__ == "__main__":
    unittest.main()
