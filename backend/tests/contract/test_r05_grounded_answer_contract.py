"""R05 typed model schemas and public v2 shape compatibility; synthetic, offline only."""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from ai_intel.answering.contracts import (
    AnswerClaim,
    GeneratedAnswer,
    GroundedAnswerDraft,
    SupportVerification,
)
from ai_intel.answering.grounding import validate_support_verdicts
from ai_intel.api.knowledge_contracts import CitationProjection
from ai_intel.infrastructure.models.generation import require_strict_schema

EVIDENCE_ID = "00000000-0000-4000-8000-000000000001"
REVISION_ID = "00000000-0000-4000-8000-000000000002"


def claim():
    return {"text": "修复版本未知。", "kind": "source_fact", "support_ids": [EVIDENCE_ID]}


def verdict(index=1):
    return {
        "claim_index": index,
        "verdict": "supported",
        "numbers_match": True,
        "states_preserved": True,
        "suggestion_only": False,
    }


@pytest.mark.parametrize("schema", [GeneratedAnswer, SupportVerification])
def test_all_nested_schemas_forbid_extra_fields(schema):
    require_strict_schema(schema)
    generated_schema = schema.model_json_schema()
    assert generated_schema["additionalProperties"] is False
    assert all(
        value.get("additionalProperties") is False
        for value in generated_schema.get("$defs", {}).values()
    )


@pytest.mark.parametrize("location", ["root", "claim", "citation"])
def test_generation_extra_fields_cannot_smuggle_answer_or_source_metadata(location):
    payload = {
        "claims": [claim()],
        "citations": [{"evidence_id": EVIDENCE_ID, "quote": "修复版本未知。"}],
    }
    if location == "root":
        payload["answer_text"] = "unverified free text"
    elif location == "claim":
        payload["claims"][0]["tenant_id"] = "attacker tenant"
    else:
        payload["citations"][0]["source_uri"] = "https://attacker.example/"
    with pytest.raises(ValidationError):
        GeneratedAnswer.model_validate_json(json.dumps(payload), strict=True)


@pytest.mark.parametrize("extra_in_item", [True, False])
def test_verification_extra_fields_are_rejected(extra_in_item):
    payload = {"verdicts": [verdict()]}
    (payload["verdicts"][0] if extra_in_item else payload)["skip_validation"] = True
    with pytest.raises(ValidationError):
        SupportVerification.model_validate_json(json.dumps(payload), strict=True)


@pytest.mark.parametrize("text", ["", " ", "a\r\nb", "a\u2028b", "\ud800", "x" * 2049])
def test_output_text_boundaries_do_not_normalize_input(text):
    payload = {**claim(), "text": text}
    with pytest.raises(ValidationError):
        AnswerClaim.model_validate_json(json.dumps(payload), strict=True)


@pytest.mark.parametrize("supports", [[], [EVIDENCE_ID, EVIDENCE_ID], ["invented-span"]])
def test_source_facts_require_unique_uuid_supports(supports):
    with pytest.raises(ValidationError):
        AnswerClaim.model_validate_json(
            json.dumps({**claim(), "support_ids": supports}), strict=True
        )


def test_two_claim_verdicts_cover_all_indices_once_in_any_order():
    first = AnswerClaim.model_validate_json(json.dumps(claim()), strict=True)
    second = first.model_copy(update={"text": "尚未确认受影响。"})
    verification = SupportVerification.model_validate_json(
        json.dumps({"verdicts": [verdict(2), verdict(1)]}), strict=True
    )
    validate_support_verdicts((first, second), verification)


@pytest.mark.parametrize("indices", [[1], [1, 1], [1, 3], [1, 2, 3]])
def test_multi_claim_missing_duplicate_and_fabricated_indices_fail(indices):
    first = AnswerClaim.model_validate_json(json.dumps(claim()), strict=True)
    verification = SupportVerification.model_validate_json(
        json.dumps({"verdicts": [verdict(index) for index in indices]}), strict=True
    )
    with pytest.raises(RuntimeError, match="answer_verdict_coverage_invalid"):
        validate_support_verdicts((first, first), verification)


def test_draft_fields_fit_frozen_public_qaanswer_without_creating_api_state():
    citation = CitationProjection.model_validate_json(
        json.dumps(
            {
                "evidence_id": EVIDENCE_ID,
                "revision_id": REVISION_ID,
                "quote": "修复版本未知。",
                "locator": "text:0:7",
                "source_uri": "https://vendor.example/advisory",
            }
        )
    )
    confirmed = AnswerClaim.model_validate_json(json.dumps(claim()), strict=True)
    draft = GroundedAnswerDraft(
        "来源事实 1：修复版本未知。", (confirmed,), (citation,), ("仅覆盖提供的公开来源。",), ()
    )
    assert set(asdict(draft)) == {"answer_text", "claims", "citations", "limitations", "attempts"}
    schema_path = Path(__file__).resolve().parents[3] / "contracts/schemas/public_api_v2.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    answer = {
        "kind": "completed",
        "answer_id": str(UUID(int=10)),
        "answer_text": draft.answer_text,
        "claims": [confirmed.model_dump(mode="json")],
        "citations": [citation.model_dump(mode="json")],
        "limitations": list(draft.limitations),
        "freshness": "unknown",
        "data_mode": "fixture",
        "started_at": datetime.now(UTC).isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        "latency_milliseconds": 0,
    }
    Draft202012Validator(
        {"$defs": schema["$defs"], **schema["$defs"]["QAAnswer"]}, format_checker=FormatChecker()
    ).validate(answer)
