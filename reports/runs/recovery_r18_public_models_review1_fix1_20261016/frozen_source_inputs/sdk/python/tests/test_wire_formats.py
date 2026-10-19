"""Frozen format semantics cover raw JSON before normalization and ordinary typed callers."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from ai_intel_client.client import DianziClient, ResponseContractError
from ai_intel_client.models import (
    Advisory,
    AnswerClaim,
    AskRequest,
    Citation,
    Component,
    ComponentAssessment,
    Enrichment,
    NormalizedIntel,
    PublicRecord,
    QAAnswer,
    Relation,
    StackUploadRequest,
    TaskHandle,
    Vulnerability,
)
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import SecretStr, ValidationError
from test_models import CITATION, COMPONENT, ENRICHMENT, ID, RELATION

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = json.loads((ROOT / "contracts/schemas/public_api_v2.json").read_bytes())
ANSWER = {
    "kind": "completed",
    "answer_id": ID,
    "answer_text": "synthetic unknown",
    "claims": [],
    "citations": [],
    "limitations": ["fixture only"],
    "freshness": "unknown",
    "data_mode": "fixture",
    "started_at": "2026-10-16T00:00:00Z",
    "completed_at": "2026-10-16T00:00:01Z",
    "latency_milliseconds": 1000,
}
TASK = {
    "kind": "task",
    "task_id": ID,
    "status": "queued",
    "poll_uri": "/api/v1/tasks/" + ID,
    "created_at": "2026-10-16T00:00:00Z",
}


def assert_format_rejected(model: type[PublicRecord], raw: dict[str, object]) -> None:
    references = {
        "AnswerClaim": "#/$defs/QAAnswer/properties/claims/items",
        "ComponentAssessment": "#/$defs/StackCheckResult/properties/results/items",
    }
    validator = Draft202012Validator(
        {**SCHEMA, "$ref": references.get(model.__name__, "#/$defs/" + model.__name__)},
        format_checker=FormatChecker(),
    )
    assert list(validator.iter_errors(raw))
    with pytest.raises(ValidationError):
        model.model_validate_json(json.dumps(raw))


@pytest.mark.parametrize(
    "model,raw",
    [
        (Citation, dict(CITATION, revision_id=ID.replace("-", ""))),
        (Component, dict(COMPONENT, component_id=ID.replace("-", ""))),
        (Enrichment, dict(ENRICHMENT, claim_ids=[ID.replace("-", "")])),
        (Relation, dict(RELATION, relation_id=ID.replace("-", ""))),
        (Relation, dict(RELATION, subject_id=ID.replace("-", ""))),
        (Relation, dict(RELATION, object_id=ID.replace("-", ""))),
        (Relation, dict(RELATION, source_revision=ID.replace("-", ""))),
        (
            NormalizedIntel,
            {
                "intel_id": ID.replace("-", ""),
                "revision_id": ID,
                "title": "fixture",
                "kind": "advisory",
                "external_ids": [],
                "citations": [],
                "data_mode": "fixture",
            },
        ),
        (
            Vulnerability,
            {
                "intel_id": ID,
                "event_id": ID.replace("-", ""),
                "title": "fixture",
                "external_ids": [],
                "enrichments": [],
                "relations": [],
                "freshness": "unknown",
            },
        ),
        (
            Advisory,
            {
                "intel_id": ID,
                "revision_id": ID.replace("-", ""),
                "title": "fixture",
                "source_uri": "https://example.org/fixture",
                "published_at": None,
                "citations": [],
            },
        ),
        (
            AnswerClaim,
            {"text": "fixture", "kind": "source_fact", "support_ids": [ID.replace("-", "")]},
        ),
        (QAAnswer, dict(ANSWER, answer_id=ID.replace("-", ""))),
        (TaskHandle, dict(TASK, task_id=ID.replace("-", ""))),
        (
            AskRequest,
            {"question": "fixture", "mode": "library", "conversation_id": ID.replace("-", "")},
        ),
        (
            AskRequest,
            {"question": "fixture", "mode": "library", "asset_ids": [ID.replace("-", "")]},
        ),
        (
            AskRequest,
            {"question": "fixture", "mode": "library", "event_ids": [ID.replace("-", "")]},
        ),
        (
            ComponentAssessment,
            {
                "component": COMPONENT,
                "status": "insufficient_evidence",
                "reason_code": "no_match",
                "assessment_id": ID.replace("-", ""),
                "citations": [],
                "freshness": "unknown",
            },
        ),
        (
            StackUploadRequest,
            {
                "upload_id": ID.replace("-", ""),
                "size_bytes": 1,
                "declared_component_count": 1,
                "format": "json_components",
            },
        ),
    ],
)
def test_all_public_uuid_boundaries_reject_noncanonical_raw_spelling(
    model: type[PublicRecord], raw: dict[str, object]
) -> None:
    assert_format_rejected(model, raw)


@pytest.mark.parametrize(
    "model,raw",
    [
        (Enrichment, dict(ENRICHMENT, observed_at="2026-10-16 00:00:00Z")),
        (
            Advisory,
            {
                "intel_id": ID,
                "revision_id": ID,
                "title": "fixture",
                "source_uri": "https://example.org/fixture",
                "published_at": "2026-10-16 00:00:00Z",
                "citations": [],
            },
        ),
        (QAAnswer, dict(ANSWER, started_at="2026-10-16 00:00:00Z")),
        (QAAnswer, dict(ANSWER, completed_at="2026-10-16 00:00:00Z")),
        (TaskHandle, dict(TASK, created_at="2026-10-16 00:00:00Z")),
        (AskRequest, {"question": "fixture", "mode": "library", "known_at": "1760572800"}),
        (AskRequest, {"question": "fixture", "mode": "library", "valid_at": "1760572800"}),
    ],
)
def test_all_public_datetime_boundaries_reject_non_rfc3339_raw_spelling(
    model: type[PublicRecord], raw: dict[str, object]
) -> None:
    assert_format_rejected(model, raw)


@pytest.mark.parametrize(
    "value",
    [
        "2026-10-16T00:00:00Z",
        "2026-10-16t00:00:00z",
        "2026-10-16T00:00:00.1Z",
        "2026-10-16T00:00:00.123456Z",
        "2026-10-16T00:00:00+08:00",
        "2026-10-16T00:00:00-05:30",
        "2026-10-16T00:00:00+23:59",
        "2024-02-29T00:00:00Z",
    ],
)
def test_approved_timezone_case_calendar_and_microsecond_forms_stay_valid(value: str) -> None:
    raw = dict(ANSWER, started_at=value, completed_at=value)
    validator = Draft202012Validator(
        {**SCHEMA, "$ref": "#/$defs/QAAnswer"}, format_checker=FormatChecker()
    )
    assert list(validator.iter_errors(raw)) == []
    parsed = QAAnswer.model_validate_json(json.dumps(raw))
    assert parsed.started_at.utcoffset() is not None
    assert parsed.completed_at == parsed.started_at
    assert list(validator.iter_errors(json.loads(parsed.wire_json()))) == []


@pytest.mark.parametrize(
    "value",
    [
        "aabbccdd-eeff-4abc-9def-0123456789ab",
        "AABBCCDD-EEFF-4ABC-9DEF-0123456789AB",
        "AaBbCcDd-EeFf-4aBc-9DeF-0123456789Ab",
    ],
)
def test_approved_uuid_case_forms_keep_typed_identity(value: str) -> None:
    parsed = Citation.model_validate_json(json.dumps(dict(CITATION, evidence_id=value)))
    assert parsed.evidence_id == UUID(value)


@pytest.mark.parametrize(
    "value",
    [
        "2026-10-16T00:00:00+08:60",
        "2026-10-16T00:00:00+24:00",
        "2026-10-16T24:00:00Z",
        "2026-10-16T00:00:60Z",
        "2026-02-30T00:00:00Z",
        "2026-10-16T00:00:00",
    ],
)
def test_invalid_timezone_clock_calendar_and_missing_zone_stay_rejected(value: str) -> None:
    assert_format_rejected(QAAnswer, dict(ANSWER, started_at=value, completed_at=value))


def test_typed_uuid_and_aware_datetime_python_callers_remain_supported() -> None:
    timestamp = datetime(2026, 10, 16, microsecond=123456, tzinfo=timezone(timedelta(hours=8)))
    request = AskRequest(
        question="fixture", mode="library", conversation_id=UUID(ID), known_at=timestamp
    )
    restored = AskRequest.model_validate_json(request.wire_json())
    assert restored.conversation_id == UUID(ID)
    assert restored.known_at == timestamp
    citation = Citation(
        evidence_id=UUID(ID),
        revision_id=UUID(ID),
        quote="fixture",
        locator="paragraph:1",
        source_uri="https://example.org/fixture",
    )
    assert citation.evidence_id == UUID(ID)


def test_missing_optional_dates_remain_omitted_and_naive_python_datetime_rejected() -> None:
    request = AskRequest(question="fixture", mode="library")
    assert "known_at" not in json.loads(request.wire_json())
    with pytest.raises(ValidationError):
        AskRequest(question="fixture", mode="library", known_at=datetime(2026, 10, 16))


@pytest.mark.parametrize(
    "invalid_response",
    [dict(ANSWER, answer_id=ID.replace("-", "")), dict(ANSWER, started_at="2026-10-16 00:00:00Z")],
)
def test_http_invalid_wire_format_becomes_contract_error_before_success(
    invalid_response: dict[str, object],
) -> None:
    with (
        DianziClient(
            "http://127.0.0.1:12345",
            SecretStr("synthetic-format-key-no-provider-access"),
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=invalid_response)),
        ) as client,
        pytest.raises(ResponseContractError),
    ):
        client.ask(AskRequest(question="fixture", mode="library"))
