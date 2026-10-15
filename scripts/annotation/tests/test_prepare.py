"""Explicit synthetic fixtures exercise T46 preparation; they are not human gold labels."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from scripts.annotation.prepare import (
    ROOT,
    PreparationError,
    digest,
    inspect_annotations,
    scan_leaks,
    summarize,
    validate_candidates,
)

NOW = "2026-10-15T22:00:00+08:00"
QUOTE = "Synthetic component"
QUOTE_HASH = hashlib.sha256(QUOTE.encode()).hexdigest()


def fixture_bundle() -> dict:
    return {
        "schema_version": 1,
        "prepared_at": NOW,
        "cases": [
            {
                "case_id": "SYN-ANNOTATION-01",
                "event_family_id": "SYN-FAMILY-01",
                "family_aliases": ["SYN-EVENT-01"],
                "data_kind": "synthetic",
                "split": "dev",
                "source_refs": [
                    {
                        "source_kind": "fixture",
                        "uri": "urn:synthetic:annotation-01",
                        "document_id": "SYN-DOCUMENT-01",
                        "revision_id": "SYN-REVISION-01",
                        "revision_number": 1,
                        "title": "Explicit synthetic annotation fixture",
                        "source_published_at": None,
                        "source_modified_at": None,
                        "observed_at": NOW,
                    }
                ],
                "source_snapshot_time": NOW,
                "input_refs": [
                    {
                        "kind": "evidence",
                        "ref_id": "SYN-SPAN-01",
                        "sha256": QUOTE_HASH,
                        "path": None,
                    }
                ],
                "license": {
                    "status": "unknown",
                    "identifier": None,
                    "uri": None,
                    "redistribution": "unverified",
                },
                "candidate_origin": "human_curated",
                "candidate_task": "Synthetic evidence checking exercise",
                "evidence": [
                    {
                        "span_id": "SYN-SPAN-01",
                        "revision_id": "SYN-REVISION-01",
                        "block_id": "SYN-BLOCK-01",
                        "start_offset": 10,
                        "end_offset": 29,
                        "quote_text": QUOTE,
                        "quote_sha256": QUOTE_HASH,
                        "locator_kind": "json_pointer",
                        "page_number": None,
                        "json_pointer": "/synthetic/name",
                        "source_uri": "urn:synthetic:annotation-01",
                        "verified_at": NOW,
                        "field_meaning": "Synthetic component name; not real source material",
                    }
                ],
                "limitations": ["Synthetic only"],
                "label_status": "awaiting_human_label",
            }
        ],
    }


def fixture_label(annotator: str, status: str = "unknown", revision: int = 1) -> dict:
    return {
        "case_id": "SYN-ANNOTATION-01",
        "annotator_id": annotator,
        "recorded_at": NOW,
        "revision": revision,
        "previous_sha256": None,
        "change_reason": None,
        "affected_case_ids": [],
        "retest_refs": [],
        "label": {
            "expected_claims": [],
            "expected_conditions": [],
            "expected_status": status,
        },
    }


def fixture_annotations() -> dict:
    return {
        "schema_version": 1,
        "data_mode": "fixture",
        "candidate_cases_sha256": digest(fixture_bundle()["cases"]),
        "annotators": [],
        "adjudication": [],
        "identity_checks": [],
    }


def fixture_decision(records: list[dict]) -> dict:
    return {
        "case_id": "SYN-ANNOTATION-01",
        "adjudicator_id": "fixture-adjudicator",
        "recorded_at": NOW,
        "label_sha256s": [digest(record) for record in records],
        "reason": "Synthetic exercise: missing evidence requires unknown",
        "label": {
            "expected_claims": [],
            "expected_conditions": [],
            "expected_status": "unknown",
        },
    }


def fixture_identity(records: list[dict]) -> dict:
    return {
        "case_id": "SYN-ANNOTATION-01",
        "annotator_ids": [record["annotator_id"] for record in records],
        "label_sha256s": [digest(record) for record in records],
        "verified_by": "fixture-checker",
        "verified_at": NOW,
        "method": "Explicit synthetic attestation, not human verification",
        "evidence_ref": "SYN-IDENTITY-CHECK-01",
        "independent_submission_confirmed": True,
    }


class CandidateContractTests(unittest.TestCase):
    def test_t46_c01_multilingual_revision_and_derived_question_same_split(
        self,
    ) -> None:
        document = fixture_bundle()
        original = document["cases"][0]
        for suffix in ("translation", "revision", "asset-question"):
            related = deepcopy(original)
            related["case_id"] += ":" + suffix
            document["cases"].append(related)
        self.assertEqual(len(validate_candidates(document)), 4)
        document["cases"][-1]["split"] = "holdout"
        with self.assertRaisesRegex(PreparationError, "FAMILY_SPLIT_LEAK"):
            validate_candidates(document)

    def test_family_relabel_does_not_hide_source_or_alias_overlap(self) -> None:
        for overlap in ("uri", "document_id", "alias"):
            with self.subTest(overlap=overlap):
                document = fixture_bundle()
                related = deepcopy(document["cases"][0])
                related.update(
                    case_id="SYN-02", event_family_id="SYN-FAMILY-02", split="holdout"
                )
                if overlap != "alias":
                    related["family_aliases"] = []
                if overlap != "uri":
                    related["source_refs"][0]["uri"] = "urn:synthetic:other"
                    related["evidence"][0]["source_uri"] = "urn:synthetic:other"
                if overlap != "document_id":
                    related["source_refs"][0]["document_id"] = "SYN-OTHER-DOC"
                document["cases"].append(related)
                with self.assertRaisesRegex(PreparationError, "FAMILY_SPLIT_LEAK"):
                    validate_candidates(document)

    def test_t46_c03_real_and_synthetic_are_separate_counts(self) -> None:
        document = fixture_bundle()
        real = deepcopy(document["cases"][0])
        real.update(
            case_id="REAL-01",
            event_family_id="REAL-FAMILY-01",
            data_kind="real",
            family_aliases=[],
        )
        real["source_refs"][0].update(
            source_kind="public_document",
            uri="https://example.org/public",
            document_id="PUBLIC-DOC",
        )
        real["evidence"][0]["source_uri"] = "https://example.org/public"
        document["cases"].append(real)
        summary = summarize(validate_candidates(document), None)
        self.assertEqual(
            summary["candidate_counts_by_data_kind"],
            {"real": 1, "synthetic": 1, "redacted": 0, "replay": 0},
        )

    def test_t46_c05_missing_source_license_or_snapshot_fails(self) -> None:
        for field in ("source_refs", "license", "source_snapshot_time"):
            with self.subTest(field=field):
                document = fixture_bundle()
                del document["cases"][0][field]
                with self.assertRaisesRegex(PreparationError, "SCHEMA_INVALID"):
                    validate_candidates(document)
        self.assertEqual(len(validate_candidates(fixture_bundle())), 1)

    def test_unknown_license_cannot_grant_redistribution(self) -> None:
        document = fixture_bundle()
        document["cases"][0]["license"]["redistribution"] = "permitted"
        with self.assertRaisesRegex(PreparationError, "SCHEMA_INVALID"):
            validate_candidates(document)

    def test_t46_c06_unlabeled_cases_remain_pending_without_accuracy(self) -> None:
        summary = summarize(validate_candidates(fixture_bundle()), None)
        self.assertEqual(summary["annotation_readiness"]["awaiting_human_label"], 1)
        self.assertEqual(summary["human_gold_count"], 0)
        self.assertEqual(
            summary["formal_evaluation"],
            {"status": "not_run", "numerator": None, "denominator": None},
        )

    def test_hash_offset_locator_and_reference_checks(self) -> None:
        for field, value, error in (
            ("quote_sha256", "0" * 64, "QUOTE_HASH_MISMATCH"),
            ("end_offset", 30, "QUOTE_OFFSET_MISMATCH"),
            ("json_pointer", None, "EVIDENCE_LOCATOR_REQUIRED"),
            ("revision_id", "OTHER", "EVIDENCE_SOURCE_MISMATCH"),
        ):
            with self.subTest(field=field):
                document = fixture_bundle()
                document["cases"][0]["evidence"][0][field] = value
                with self.assertRaisesRegex(PreparationError, error):
                    validate_candidates(document)

    def test_path_traversal_and_absolute_paths_refused(self) -> None:
        for path in (
            "../secret.json",
            "C:/secret.json",
            "/secret.json",
            "inputs\\secret.json",
            "a/./b",
        ):
            with self.subTest(path=path):
                document = fixture_bundle()
                document["cases"][0]["input_refs"][0]["path"] = path
                with self.assertRaisesRegex(PreparationError, "REFERENCE_PATH_UNSAFE"):
                    validate_candidates(document)

    def test_duplicate_case_and_expected_fields_refused(self) -> None:
        document = fixture_bundle()
        document["cases"].append(deepcopy(document["cases"][0]))
        with self.assertRaisesRegex(PreparationError, "DUPLICATE_CASE"):
            validate_candidates(document)
        document = fixture_bundle()
        document["cases"][0]["expected_status"] = "unknown"
        with self.assertRaisesRegex(PreparationError, "SCHEMA_INVALID"):
            validate_candidates(document)

    def test_synthetic_origin_cannot_masquerade_as_real(self) -> None:
        document = fixture_bundle()
        document["cases"][0]["data_kind"] = "real"
        with self.assertRaisesRegex(PreparationError, "PUBLIC_PROVENANCE_REQUIRED"):
            validate_candidates(document)


class AnnotationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = validate_candidates(fixture_bundle())

    def test_t46_c02_disagreement_requires_adjudication(self) -> None:
        labels = fixture_annotations()
        labels["annotators"] = [
            fixture_label("fixture-a"),
            fixture_label("fixture-b", "conflict"),
        ]
        self.assertEqual(
            inspect_annotations(self.cases, labels)["awaiting_adjudication"], 1
        )
        labels["adjudication"] = [fixture_decision(labels["annotators"])]
        self.assertEqual(
            inspect_annotations(self.cases, labels)["awaiting_identity_verification"], 1
        )
        labels["identity_checks"] = [fixture_identity(labels["annotators"])]
        self.assertEqual(
            inspect_annotations(self.cases, labels)["ready_for_manual_review"], 1
        )
        self.assertEqual(summarize(self.cases, labels)["human_gold_count"], 0)

    def test_distinct_strings_do_not_prove_independent_humans(self) -> None:
        labels = fixture_annotations()
        labels["annotators"] = [fixture_label("fixture-a"), fixture_label("fixture-b")]
        self.assertEqual(
            inspect_annotations(self.cases, labels)["awaiting_identity_verification"], 1
        )

    def test_labels_are_bound_to_candidate_version(self) -> None:
        labels = fixture_annotations()
        self.cases[0]["candidate_task"] = "Changed synthetic task"
        with self.assertRaisesRegex(
            PreparationError, "LABEL_CANDIDATE_VERSION_MISMATCH"
        ):
            inspect_annotations(self.cases, labels)

    def test_same_annotator_double_signature_refused(self) -> None:
        labels = fixture_annotations()
        labels["annotators"] = [fixture_label("fixture-a"), fixture_label("fixture-a")]
        with self.assertRaisesRegex(PreparationError, "LABEL_REVISION_AUDIT_REQUIRED"):
            inspect_annotations(self.cases, labels)

    def test_label_revision_requires_reason_impact_retest_and_previous_hash(
        self,
    ) -> None:
        first = fixture_label("fixture-a")
        second = fixture_label("fixture-a", "conflict", 2)
        second.update(
            previous_sha256=digest(first),
            change_reason="Synthetic correction",
            affected_case_ids=["SYN-ANNOTATION-01"],
            retest_refs=["SYN-RETEST-01"],
        )
        labels = fixture_annotations()
        labels["annotators"] = [first, second]
        self.assertEqual(
            inspect_annotations(self.cases, labels)["awaiting_human_label"], 1
        )
        for field, value in (
            ("change_reason", None),
            ("previous_sha256", "0" * 64),
            ("affected_case_ids", []),
            ("retest_refs", []),
        ):
            with self.subTest(field=field):
                invalid = deepcopy(labels)
                invalid["annotators"][-1][field] = value
                with self.assertRaisesRegex(
                    PreparationError, "LABEL_REVISION_AUDIT_REQUIRED"
                ):
                    inspect_annotations(self.cases, invalid)

    def test_stale_or_self_adjudication_refused(self) -> None:
        labels = fixture_annotations()
        labels["annotators"] = [
            fixture_label("fixture-a"),
            fixture_label("fixture-b", "conflict"),
        ]
        decision = fixture_decision(labels["annotators"])
        labels["adjudication"] = [decision]
        for field, value in (
            ("adjudicator_id", "fixture-a"),
            ("label_sha256s", ["0" * 64, "1" * 64]),
        ):
            with self.subTest(field=field):
                invalid = deepcopy(labels)
                invalid["adjudication"][0][field] = value
                with self.assertRaisesRegex(
                    PreparationError, "ADJUDICATION_INVALID_OR_STALE"
                ):
                    inspect_annotations(self.cases, invalid)

    def test_model_fields_and_unreferenced_label_evidence_refused(self) -> None:
        labels = fixture_annotations()
        labels["annotators"] = [fixture_label("fixture-a")]
        labels["data_mode"] = "model"
        with self.assertRaisesRegex(PreparationError, "SCHEMA_INVALID"):
            inspect_annotations(self.cases, labels)
        labels["data_mode"] = "fixture"
        labels["annotators"][0]["label"]["expected_claims"] = [
            {"claim": "Synthetic", "evidence_ids": ["UNKNOWN"]}
        ]
        with self.assertRaisesRegex(PreparationError, "LABEL_EVIDENCE_UNKNOWN"):
            inspect_annotations(self.cases, labels)


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(prefix="r19-synthetic-only-")
        self.path = Path(self.directory.name)
        self.input = self.path / "synthetic_candidates.json"
        self.write(self.input, fixture_bundle())

    def tearDown(self) -> None:
        self.directory.cleanup()

    def write(self, path: Path, value: dict) -> None:
        path.write_text(json.dumps(value), encoding="utf-8")

    def cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts/annotation/prepare.py"), *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )

    def test_import_validate_export_round_trip_and_replay_refusal(self) -> None:
        imported = self.path / "imported.json"
        self.assertEqual(
            self.cli(
                "import", "--input", str(self.input), "--output", str(imported)
            ).returncode,
            0,
        )
        self.assertEqual(self.cli("validate", "--input", str(imported)).returncode, 0)
        result = self.cli(
            "import", "--input", str(self.input), "--output", str(imported)
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("OUTPUT_EXISTS", result.stderr)
        exported = self.path / "exported.json"
        self.assertEqual(
            self.cli(
                "export",
                "--input",
                str(imported),
                "--output",
                str(exported),
                "--purpose",
                "prompt",
            ).returncode,
            0,
        )
        self.assertEqual(self.cli("validate", "--input", str(exported)).returncode, 0)

    def test_dual_fill_disagreement_adjudication_validation_export_cli(self) -> None:
        labels = fixture_annotations()
        labels_path = self.path / "synthetic_labels.json"
        labels["annotators"] = [fixture_label("fixture-a")]
        self.write(labels_path, labels)
        result = self.cli(
            "validate", "--input", str(self.input), "--labels", str(labels_path)
        )
        self.assertEqual(
            json.loads(result.stdout)["annotation_readiness"]["awaiting_human_label"], 1
        )
        labels["annotators"].append(fixture_label("fixture-b", "conflict"))
        self.write(labels_path, labels)
        result = self.cli(
            "validate", "--input", str(self.input), "--labels", str(labels_path)
        )
        self.assertEqual(
            json.loads(result.stdout)["annotation_readiness"]["awaiting_adjudication"],
            1,
        )
        labels["adjudication"] = [fixture_decision(labels["annotators"])]
        labels["identity_checks"] = [fixture_identity(labels["annotators"])]
        self.write(labels_path, labels)
        exported = self.path / "synthetic_annotation_export.json"
        result = self.cli(
            "export",
            "--input",
            str(self.input),
            "--labels",
            str(labels_path),
            "--output",
            str(exported),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("expected_status", result.stdout)
        self.assertEqual(
            json.loads(result.stdout)["annotation_readiness"][
                "ready_for_manual_review"
            ],
            1,
        )
        self.assertEqual(self.cli("validate", "--input", str(exported)).returncode, 0)
        self.assertEqual(json.loads(exported.read_text())["annotations"], labels)

    def test_t46_c04_holdout_prompt_image_and_index_leaks_fail(self) -> None:
        document = fixture_bundle()
        document["cases"][0]["split"] = "holdout"
        self.write(self.input, document)
        for surface in ("prompt", "image", "index"):
            with self.subTest(surface=surface):
                output = self.path / (surface + ".json")
                result = self.cli(
                    "export",
                    "--input",
                    str(self.input),
                    "--output",
                    str(output),
                    "--purpose",
                    surface,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("HOLDOUT_EXPORT_REFUSED", result.stderr)
                scan_root = self.path / surface
                scan_root.mkdir()
                (scan_root / "synthetic_manifest.txt").write_text(
                    "SYN-FAMILY-01", encoding="utf-8"
                )
                result = self.cli(
                    "scan", "--input", str(self.input), "--scan-root", str(scan_root)
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("HOLDOUT_LEAK_FOUND", result.stderr)

    def test_duplicate_nested_json_keys_fail_without_printing_value(self) -> None:
        self.input.write_text('{"private":"synthetic-value","nested":{"x":1,"x":2}}')
        result = self.cli("validate", "--input", str(self.input))
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("synthetic-value", result.stdout + result.stderr)

    def test_human_label_export_to_repository_or_product_mount_refused(self) -> None:
        labels = fixture_annotations()
        path = self.path / "labels.json"
        self.write(path, labels)
        result = self.cli(
            "export",
            "--input",
            str(self.input),
            "--labels",
            str(path),
            "--output",
            str(ROOT / "benchmarks/manifests/forbidden.json"),
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("HUMAN_OR_HOLDOUT_PATH_MUST_BE_EXTERNAL", result.stderr)
        mounted = self.path / "mounted-product"
        mounted.mkdir()
        result = self.cli(
            "export",
            "--input",
            str(self.input),
            "--labels",
            str(path),
            "--output",
            str(mounted / "labels.json"),
            "--product-root",
            str(mounted),
        )
        self.assertEqual(result.returncode, 2)
        self.assertFalse((mounted / "labels.json").exists())

    def test_concurrent_exports_create_exactly_one_file(self) -> None:
        output = self.path / "concurrent.json"
        command = [
            sys.executable,
            str(ROOT / "scripts/annotation/prepare.py"),
            "export",
            "--input",
            str(self.input),
            "--output",
            str(output),
        ]
        processes = [
            subprocess.Popen(
                command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            for _ in range(2)
        ]
        for process in processes:
            process.communicate(timeout=30)
        self.assertEqual(sorted(process.returncode for process in processes), [0, 2])
        self.assertEqual(self.cli("validate", "--input", str(output)).returncode, 0)

    def test_tampered_export_hash_refused(self) -> None:
        document = fixture_bundle()
        document["candidate_sha256"] = "0" * 64
        self.write(self.input, document)
        result = self.cli("validate", "--input", str(self.input))
        self.assertEqual(result.returncode, 2)
        self.assertIn("CANDIDATE_HASH_MISMATCH", result.stderr)

    def test_labels_cannot_be_exported_to_prompt_and_mutated_exports_fail(self) -> None:
        labels = fixture_annotations()
        labels_path = self.path / "synthetic_labels.json"
        self.write(labels_path, labels)
        output = self.path / "annotation.json"
        result = self.cli(
            "export",
            "--input",
            str(self.input),
            "--labels",
            str(labels_path),
            "--output",
            str(output),
            "--purpose",
            "prompt",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("LABEL_EXPORT_REFUSED", result.stderr)
        result = self.cli(
            "export",
            "--input",
            str(self.input),
            "--labels",
            str(labels_path),
            "--output",
            str(output),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        exported = json.loads(output.read_text())
        exported["annotations"]["annotators"] = [fixture_label("fixture-a")]
        self.write(output, exported)
        result = self.cli("validate", "--input", str(output))
        self.assertEqual(result.returncode, 2)
        self.assertIn("ANNOTATION_HASH_MISMATCH", result.stderr)

    def test_clean_selected_public_surface_scan_passes(self) -> None:
        public = self.path / "public"
        public.mkdir()
        (public / "safe.txt").write_text("Explicit synthetic public text")
        document = fixture_bundle()
        document["cases"][0]["split"] = "holdout"
        scan_leaks(validate_candidates(document), [public])

    def test_holdout_answer_only_leak_is_detected(self) -> None:
        document = fixture_bundle()
        document["cases"][0]["split"] = "holdout"
        labels = fixture_annotations()
        labels["candidate_cases_sha256"] = digest(document["cases"])
        record = fixture_label("fixture-a")
        record["label"]["expected_claims"] = [
            {
                "claim": "Synthetic answer with no case or family identifier",
                "evidence_ids": ["SYN-SPAN-01"],
            }
        ]
        labels["annotators"] = [record]
        self.write(self.input, document)
        labels_path = self.path / "holdout_synthetic_labels.json"
        self.write(labels_path, labels)
        public = self.path / "public-answer-only"
        public.mkdir()
        (public / "synthetic_prompt.txt").write_text(
            "Synthetic answer with no case or family identifier"
        )
        result = self.cli(
            "scan",
            "--input",
            str(self.input),
            "--labels",
            str(labels_path),
            "--scan-root",
            str(public),
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("HOLDOUT_LEAK_FOUND", result.stderr)
        self.assertNotIn("Synthetic answer", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
