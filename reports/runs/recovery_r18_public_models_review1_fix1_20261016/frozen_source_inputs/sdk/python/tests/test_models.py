"""Observable public v2 semantics and fixed source-contract comparisons."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from ai_intel_client.models import (
    ASK_RESULT_ADAPTER,
    Advisory,
    AskRequest,
    Citation,
    Component,
    Enrichment,
    NormalizedIntel,
    QAAnswer,
    Relation,
    StackCheckRequest,
    StackCheckResult,
    StackUploadRequest,
    TaskHandle,
    Vulnerability,
)
from pydantic import TypeAdapter, ValidationError

ROOT = Path(__file__).resolve().parents[3]
ID = "00000000-0000-4000-8000-000000000001"
CITATION = {
    "evidence_id": ID,
    "revision_id": ID,
    "quote": "synthetic evidence",
    "locator": "paragraph:1",
    "source_uri": "https://example.org/synthetic-advisory",
}
ENRICHMENT = {
    "dimension": "cwe",
    "status": "available",
    "claim_ids": [ID],
    "citations": [CITATION],
    "freshness": "current",
    "observed_at": None,
    "source_version": "synthetic-1",
    "error_code": None,
}
RELATION = {
    "relation_id": ID,
    "relation_type": "same_event",
    "subject_id": ID,
    "object_id": ID,
    "source_revision": ID,
    "citations": [CITATION],
    "rule_or_model_version": "synthetic-1",
    "reason": "explicit synthetic identifier",
    "status": "supported",
}
COMPONENT = {"ecosystem": "PyPI", "package_name": "synthetic-package", "version": None}


@pytest.mark.parametrize(
    ("model", "value"),
    [
        (Citation, CITATION),
        (Component, COMPONENT),
        (Enrichment, ENRICHMENT),
        (Relation, RELATION),
        (
            NormalizedIntel,
            {
                "intel_id": ID,
                "revision_id": ID,
                "title": "synthetic paper",
                "kind": "paper",
                "external_ids": [],
                "citations": [CITATION],
                "data_mode": "fixture",
            },
        ),
        (
            Vulnerability,
            {
                "intel_id": ID,
                "event_id": ID,
                "title": "synthetic AI risk without CVE",
                "external_ids": [],
                "enrichments": [ENRICHMENT],
                "relations": [RELATION],
                "freshness": "current",
            },
        ),
        (
            Advisory,
            {
                "intel_id": ID,
                "revision_id": ID,
                "title": "synthetic advisory",
                "source_uri": "https://example.org/synthetic-advisory",
                "published_at": None,
                "citations": [CITATION],
            },
        ),
    ],
)
def test_public_business_object_json_roundtrip(model: type, value: dict[str, object]) -> None:
    parsed = model.model_validate_json(json.dumps(value))
    assert json.loads(parsed.wire_json()) == value


def test_frozen_public_example_cases() -> None:
    examples = json.loads((ROOT / "contracts/schemas/public_api_v2_examples.json").read_bytes())
    adapters = {
        "AskResult": ASK_RESULT_ADAPTER,
        "StackCheckRequest": TypeAdapter(StackCheckRequest),
        "StackCheckResult": TypeAdapter(StackCheckResult),
    }
    count = 0
    for name, values in examples["valid"].items():
        for value in values:
            adapters[name].validate_json(json.dumps(value))
            count += 1
    for name, values in examples["invalid"].items():
        for value in values:
            with pytest.raises(ValidationError):
                adapters[name].validate_json(json.dumps(value))
            count += 1
    assert count == 7


@pytest.mark.parametrize(
    "model",
    [NormalizedIntel, Vulnerability, Advisory, Component, Enrichment, Relation, Citation, QAAnswer],
)
def test_eight_model_properties_match_approved_public_schema(model: type) -> None:
    public = json.loads((ROOT / "contracts/schemas/public_api_v2.json").read_bytes())
    schema = model.model_json_schema()
    approved = public["$defs"][model.__name__]
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == set(approved["properties"])
    assert set(schema["required"]) == set(approved["required"])


@pytest.mark.parametrize(
    "identity", ["tenant_id", "user_id", "role", "permissions", "skip_validation"]
)
def test_request_rejects_identity_and_hidden_permission_fields(identity: str) -> None:
    value = {"question": "synthetic question", "mode": "library", identity: "forged"}
    with pytest.raises(ValidationError):
        AskRequest.model_validate_json(json.dumps(value))


@pytest.mark.parametrize("name", ["conversation_id", "known_at", "valid_at"])
def test_omitted_question_fields_are_not_explicit_nulls(name: str) -> None:
    value = {"question": "synthetic question", "mode": "library"}
    question = AskRequest.model_validate_json(json.dumps(value))
    assert name not in json.loads(question.wire_json())
    with pytest.raises(ValidationError):
        AskRequest.model_validate_json(json.dumps({**value, name: None}))


@pytest.mark.parametrize("value", ["2026-10-16T00:00:00", 42, True])
def test_question_rejects_naive_or_non_timestamp_time(value: object) -> None:
    with pytest.raises(ValidationError):
        AskRequest.model_validate_json(
            json.dumps({"question": "synthetic question", "mode": "library", "known_at": value})
        )


@pytest.mark.parametrize("count, valid", [(200, True), (201, False)])
def test_synchronous_component_boundary(count: int, valid: bool) -> None:
    raw = json.dumps({"components": [COMPONENT] * count})
    if valid:
        assert len(StackCheckRequest.model_validate_json(raw).components) == 200
    else:
        with pytest.raises(ValidationError):
            StackCheckRequest.model_validate_json(raw)


@pytest.mark.parametrize("extra", [{"size_bytes": 10485761}, {"declared_component_count": 10001}])
def test_upload_limits_are_independent_of_sync_count(extra: dict[str, int]) -> None:
    value = {
        "upload_id": ID,
        "size_bytes": 10485760,
        "declared_component_count": 10000,
        "format": "json_components",
    }
    assert (
        StackUploadRequest.model_validate_json(json.dumps(value)).declared_component_count == 10000
    )
    with pytest.raises(ValidationError):
        StackUploadRequest.model_validate_json(json.dumps({**value, **extra}))


@pytest.mark.parametrize(
    "reason", ["no_match", "unsupported", "unsupported_rule", "unsupported_ecosystem"]
)
def test_no_match_or_unsupported_cannot_be_exclusion(reason: str) -> None:
    result = {
        "kind": "completed",
        "results": [
            {
                "component": COMPONENT,
                "status": "insufficient_evidence",
                "reason_code": reason,
                "assessment_id": None,
                "citations": [],
                "freshness": "unknown",
            }
        ],
        "limitations": [],
    }
    assert (
        StackCheckResult.model_validate_json(json.dumps(result)).results[0].status
        == "insufficient_evidence"
    )
    result["results"][0]["status"] = "excluded_with_evidence"
    with pytest.raises(ValidationError):
        StackCheckResult.model_validate_json(json.dumps(result))


@pytest.mark.parametrize("model, value", [(Enrichment, ENRICHMENT), (Relation, RELATION)])
def test_confirmed_field_requires_evidence(model: type, value: dict[str, object]) -> None:
    changed = deepcopy(value)
    changed["citations"] = []
    with pytest.raises(ValidationError):
        model.model_validate_json(json.dumps(changed))


def test_task_cannot_redirect_polling_to_another_object_or_origin() -> None:
    value = {
        "kind": "task",
        "task_id": ID,
        "status": "queued",
        "poll_uri": "/api/v1/tasks/" + ID,
        "created_at": "2026-10-16T00:00:00Z",
    }
    assert TaskHandle.model_validate_json(json.dumps(value)).task_id.hex
    for uri in (
        "https://example.org/task",
        "/api/v1/tasks/00000000-0000-4000-8000-000000000002",
        "/api/v1/tasks/" + ID + "?api_key=synthetic",
    ):
        with pytest.raises(ValidationError):
            TaskHandle.model_validate_json(json.dumps({**value, "poll_uri": uri}))


@pytest.mark.parametrize(
    "uri",
    [
        "https://example.org/a b",
        "https://example.org/%zz",
        "https://example.org/<script>",
        "https://example.org/\nsecret",
        "relative/path",
        "https://example.org/正文",
    ],
)
def test_citation_rejects_non_uri_bytes_without_normalizing_them(uri: str) -> None:
    with pytest.raises(ValidationError):
        Citation.model_validate_json(json.dumps({**CITATION, "source_uri": uri}))


@pytest.mark.parametrize(
    "uri",
    ["https://example.org", "urn:example:synthetic", "https://example.org/%E6%AD%A3%E6%96%87"],
)
def test_uri_validation_keeps_the_original_identifier(uri: str) -> None:
    citation = Citation.model_validate_json(json.dumps({**CITATION, "source_uri": uri}))
    assert citation.source_uri == uri
