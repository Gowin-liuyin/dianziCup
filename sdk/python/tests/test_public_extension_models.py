"""Synthetic public envelope contracts, with independent frozen-schema checks."""

from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path

import ai_intel_client
import pytest
from ai_intel_client.models import (
    PublicProblem,
    PublicRecord,
    RiskFinding,
    RiskSummary,
    SourceDescriptor,
    SourcePage,
    StackCheckEnvelope,
    TaskDescriptor,
    TaskResultEnvelope,
    VulnerabilityDetailPage,
    VulnerabilityPage,
)
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = json.loads((ROOT / "contracts/schemas/public_api_extensions_v1.json").read_bytes())
IDENTIFIER = "00000000-0000-4000-8000-000000000001"
OTHER_IDENTIFIER = "00000000-0000-4000-8000-000000000002"
TIME = "2026-10-16T09:00:00+08:00"
Payload = dict[str, object]


def citation() -> Payload:
    return {
        "evidence_id": IDENTIFIER,
        "revision_id": IDENTIFIER,
        "quote": "Synthetic source explicitly grades the event.",
        "locator": "/metrics/score",
        "source_uri": "https://example.invalid/synthetic-advisory",
    }


def finding() -> Payload:
    return {
        "component_index": 0,
        "event_id": IDENTIFIER,
        "assessment_id": IDENTIFIER,
        "rule_id": IDENTIFIER,
        "rule_version": 1,
        "grading_claim_id": IDENTIFIER,
        "severity": "high",
        "cvss_score": 7.0,
        "cvss_version": "3.1",
        "citations": [citation()],
        "freshness": "current",
    }


def summary() -> Payload:
    return {
        "policy_version": "r18-risk-policy-1",
        "minimum_severity": "high",
        "confirmation": "confirmed",
        "coverage": "complete",
        "freshness": "current",
        "evaluated_components": 1,
        "unknown_component_indices": [],
        "findings": [finding()],
    }


def stack_envelope() -> Payload:
    return {
        "result": {
            "kind": "completed",
            "results": [
                {
                    "component": {
                        "ecosystem": "PyPI",
                        "package_name": "synthetic-package",
                        "version": "1",
                    },
                    "status": "supported_applicability",
                    "reason_code": "rule_supported",
                    "assessment_id": IDENTIFIER,
                    "citations": [citation()],
                    "freshness": "current",
                }
            ],
            "limitations": [],
        },
        "risk_summary": summary(),
    }


def vulnerability() -> Payload:
    return {
        "intel_id": IDENTIFIER,
        "event_id": IDENTIFIER,
        "title": "Synthetic AI vulnerability",
        "external_ids": [],
        "enrichments": [],
        "relations": [],
        "freshness": "unknown",
    }


def source() -> Payload:
    return {
        "source_id": "synthetic-source",
        "name": "Synthetic vendor",
        "category": "vendor_advisory",
        "enabled": True,
        "health": "never_polled",
        "last_attempt_at": None,
        "last_success_at": None,
        "reason_code": None,
        "data_mode": "fixture",
    }


def task() -> Payload:
    return {
        "task_id": IDENTIFIER,
        "task_type": "ask",
        "status": "queued",
        "poll_uri": "/api/v1/tasks/" + IDENTIFIER,
        "created_at": TIME,
        "updated_at": TIME,
    }


def problem() -> Payload:
    return {
        "type": "urn:dianzi:problem:not-configured",
        "title": "Dependency unavailable",
        "status": 503,
        "error": "not_configured",
        "trace_id": IDENTIFIER,
    }


def answer() -> Payload:
    return {
        "kind": "completed",
        "answer_id": IDENTIFIER,
        "answer_text": "Synthetic grounded answer",
        "claims": [],
        "citations": [],
        "limitations": ["Synthetic fixture; no live result."],
        "freshness": "unknown",
        "data_mode": "fixture",
        "started_at": TIME,
        "completed_at": TIME,
        "latency_milliseconds": 0,
    }


def task_envelope() -> Payload:
    return {
        "task": task(),
        "result": None,
        "error": None,
        "completed_steps": [],
        "pending_steps": ["generate"],
        "failed_steps": [],
    }


def source_page() -> Payload:
    return {"items": [source()], "next_cursor": None, "data_mode": "fixture"}


def vulnerability_page() -> Payload:
    return {"items": [vulnerability()], "next_cursor": None, "data_mode": "fixture"}


def detail_page() -> Payload:
    return {
        "vulnerability": vulnerability(),
        "advisories": [],
        "next_cursor": None,
        "mapping_limits": ["Synthetic mapping without external identifiers."],
        "data_mode": "fixture",
    }


EXAMPLES: tuple[tuple[type[PublicRecord], Callable[[], Payload]], ...] = (
    (RiskFinding, finding),
    (RiskSummary, summary),
    (StackCheckEnvelope, stack_envelope),
    (VulnerabilityPage, vulnerability_page),
    (VulnerabilityDetailPage, detail_page),
    (SourceDescriptor, source),
    (SourcePage, source_page),
    (TaskDescriptor, task),
    (PublicProblem, problem),
    (TaskResultEnvelope, task_envelope),
)


def schema_valid(model: type[PublicRecord], value: Payload) -> bool:
    validator = Draft202012Validator(
        {**SCHEMA, "$ref": "#/$defs/" + model.__name__}, format_checker=FormatChecker()
    )
    return validator.is_valid(value)


def rejected(model: type[PublicRecord], value: Payload, *, schema_rejects: bool = True) -> None:
    if schema_rejects:
        assert not schema_valid(model, value)
    with pytest.raises(ValidationError):
        model.model_validate_json(json.dumps(value))


@pytest.mark.parametrize("model,factory", EXAMPLES)
def test_new_models_preserve_all_frozen_fields_and_roundtrip(
    model: type[PublicRecord], factory: Callable[[], Payload]
) -> None:
    value = factory()
    assert schema_valid(model, value)
    parsed = model.model_validate_json(json.dumps(value))
    assert json.loads(parsed.wire_json()) == value
    generated = model.model_json_schema()
    approved = SCHEMA["$defs"][model.__name__]
    assert set(generated["properties"]) == set(approved["properties"])
    assert set(generated["required"]) == set(approved["required"])
    assert generated["additionalProperties"] is False
    assert getattr(ai_intel_client, model.__name__) is model


@pytest.mark.parametrize("model,factory", EXAMPLES)
def test_every_required_field_is_required_and_extra_fields_are_rejected(
    model: type[PublicRecord], factory: Callable[[], Payload]
) -> None:
    for name in SCHEMA["$defs"][model.__name__]["required"]:
        value = factory()
        del value[name]
        rejected(model, value)
    for name in ("tenant_id", "authorization", "secret_ref", "skip_validation"):
        rejected(model, {**factory(), name: "forged"})


@pytest.mark.parametrize(
    "severity,score,valid",
    [
        ("none", 0, True),
        ("none", 0.1, False),
        ("low", 0, False),
        ("low", 0.1, True),
        ("low", 3.999, True),
        ("low", 4, False),
        ("medium", 4, True),
        ("medium", 6.999, True),
        ("medium", 7, False),
        ("high", 7, True),
        ("high", 8.999, True),
        ("high", 9, False),
        ("critical", 9, True),
        ("critical", 10, True),
        ("critical", 10.1, False),
    ],
)
def test_cvss_normalized_grade_boundaries(severity: str, score: float, valid: bool) -> None:
    value = {**finding(), "severity": severity, "cvss_score": score}
    assert schema_valid(RiskFinding, value) is valid
    if valid:
        assert RiskFinding.model_validate_json(json.dumps(value)).severity == severity
    else:
        rejected(RiskFinding, value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("component_index", True),
        ("component_index", "0"),
        ("component_index", -1),
        ("component_index", 200),
        ("rule_version", True),
        ("rule_version", "1"),
        ("rule_version", 0),
        ("cvss_score", True),
        ("cvss_score", "7"),
        ("cvss_score", float("inf")),
        ("cvss_score", float("nan")),
        ("cvss_version", "5.0"),
        ("freshness", "stale"),
        ("citations", []),
        ("event_id", IDENTIFIER.replace("-", "")),
        ("grading_claim_id", "not-a-uuid"),
    ],
)
def test_risk_finding_strict_bounds_and_traceability(field: str, value: object) -> None:
    rejected(RiskFinding, {**finding(), field: value}, schema_rejects=False)


@pytest.mark.parametrize(
    "field,value",
    [
        ("enabled", 1),
        ("enabled", "true"),
        ("source_id", ""),
        ("source_id", "s" * 201),
        ("name", "s" * 501),
        ("category", "unregistered"),
        ("reason_code", ""),
        ("reason_code", "s" * 101),
        ("data_mode", "mock"),
        ("last_attempt_at", "2026-10-16T00:00:00"),
        ("last_attempt_at", "2026-02-30T00:00:00Z"),
        ("last_attempt_at", 42),
        ("last_success_at", "2026-10-16 00:00:00Z"),
    ],
)
def test_source_strict_types_and_formats(field: str, value: object) -> None:
    rejected(SourceDescriptor, {**source(), field: value})


def test_enabled_is_not_a_successful_poll_and_health_uses_observations() -> None:
    parsed = SourceDescriptor.model_validate_json(json.dumps(source()))
    assert parsed.enabled and parsed.health == "never_polled"
    rejected(SourceDescriptor, {**source(), "health": "healthy"}, schema_rejects=False)
    rejected(SourceDescriptor, {**source(), "last_attempt_at": TIME}, schema_rejects=False)
    value = {**source(), "health": "healthy", "last_attempt_at": TIME, "last_success_at": TIME}
    assert SourceDescriptor.model_validate_json(json.dumps(value)).health == "healthy"


@pytest.mark.parametrize("page_mode,item_mode", [("live", "fixture"), ("fixture", "live")])
def test_source_page_preserves_fixture_live_separation(page_mode: str, item_mode: str) -> None:
    value = {
        **source_page(),
        "data_mode": page_mode,
        "items": [{**source(), "data_mode": item_mode}],
    }
    rejected(SourcePage, value, schema_rejects=False)


def test_empty_source_page_keeps_its_explicit_mode_without_claiming_live_observations() -> None:
    for mode in ("fixture", "live"):
        parsed = SourcePage.model_validate_json(
            json.dumps({"items": [], "next_cursor": None, "data_mode": mode})
        )
        assert parsed.data_mode == mode and parsed.items == ()


@pytest.mark.parametrize(
    "model,factory",
    [
        (SourcePage, source_page),
        (VulnerabilityPage, vulnerability_page),
        (VulnerabilityDetailPage, detail_page),
    ],
)
@pytest.mark.parametrize(
    "cursor,valid",
    [(None, True), ("x", True), ("x" * 2048, True), ("", False), ("x" * 2049, False), (4, False)],
)
def test_page_cursor_bounds(
    model: type[PublicRecord], factory: Callable[[], Payload], cursor: object, valid: bool
) -> None:
    value = {**factory(), "next_cursor": cursor}
    assert schema_valid(model, value) is valid
    if valid:
        model.model_validate_json(json.dumps(value))
    else:
        rejected(model, value)


@pytest.mark.parametrize(
    "model,factory,item",
    [
        (SourcePage, source_page, source),
        (VulnerabilityPage, vulnerability_page, vulnerability),
    ],
)
def test_page_duplicates_and_array_limits(
    model: type[PublicRecord], factory: Callable[[], Payload], item: Callable[[], Payload]
) -> None:
    rejected(model, {**factory(), "items": [item(), item()]}, schema_rejects=False)
    rejected(model, {**factory(), "items": [item()] * 101})
    assert model.model_validate_json(json.dumps({**factory(), "items": []})).wire_json()


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "clean"),
        ("status", "completed"),
        ("created_at", "2026-10-16"),
        ("task_id", IDENTIFIER.replace("-", "")),
        ("task_type", "report"),
        ("poll_uri", "https://example.invalid/api/v1/tasks/" + IDENTIFIER),
        ("poll_uri", "/api/v1/tasks/" + IDENTIFIER + "?token=synthetic"),
        ("poll_uri", "/api/v1/tasks/" + OTHER_IDENTIFIER),
        ("updated_at", "2026-10-15T09:00:00+08:00"),
    ],
)
def test_task_fixed_identity_and_datetime(field: str, value: object) -> None:
    rejected(TaskDescriptor, {**task(), field: value}, schema_rejects=False)


@pytest.mark.parametrize("status", ["queued", "running", "retry_wait", "waiting_approval"])
def test_pending_tasks_cannot_fabricate_result_or_problem(status: str) -> None:
    value = {**task_envelope(), "task": {**task(), "status": status}}
    TaskResultEnvelope.model_validate_json(json.dumps(value))
    rejected(TaskResultEnvelope, {**value, "result": answer()})
    rejected(TaskResultEnvelope, {**value, "error": problem()})


@pytest.mark.parametrize("status", ["failed", "cancelled", "blocked"])
def test_unsuccessful_terminal_tasks_require_explicit_problem(status: str) -> None:
    value = {**task_envelope(), "task": {**task(), "status": status}, "error": problem()}
    TaskResultEnvelope.model_validate_json(json.dumps(value))
    rejected(TaskResultEnvelope, {**value, "error": None})
    rejected(TaskResultEnvelope, {**value, "result": answer()})


@pytest.mark.parametrize("task_type,result", [("ask", answer()), ("stack_check", stack_envelope())])
def test_succeeded_task_result_is_bound_to_type_and_complete_steps(
    task_type: str, result: Payload
) -> None:
    value = {
        **task_envelope(),
        "task": {**task(), "task_type": task_type, "status": "succeeded"},
        "result": result,
        "pending_steps": [],
        "completed_steps": ["generate"],
    }
    TaskResultEnvelope.model_validate_json(json.dumps(value))
    for field, invalid in (
        ("result", None),
        ("error", problem()),
        ("pending_steps", ["wait"]),
        ("failed_steps", ["failed"]),
    ):
        rejected(TaskResultEnvelope, {**value, field: invalid})
    wrong = stack_envelope() if task_type == "ask" else answer()
    rejected(TaskResultEnvelope, {**value, "result": wrong})


def test_partial_task_preserves_result_problem_and_pending_limits() -> None:
    value = {
        **task_envelope(),
        "task": {**task(), "status": "partial"},
        "result": answer(),
        "error": problem(),
        "completed_steps": ["retrieved"],
    }
    parsed = TaskResultEnvelope.model_validate_json(json.dumps(value))
    assert parsed.error is not None and parsed.pending_steps == ("generate",)
    for field in ("completed_steps", "pending_steps", "failed_steps"):
        rejected(TaskResultEnvelope, {**value, field: ["duplicate", "duplicate"]})
        rejected(TaskResultEnvelope, {**value, field: ["x" * 501]})
        rejected(TaskResultEnvelope, {**value, field: [str(index) for index in range(101)]})
    rejected(TaskResultEnvelope, {**value, "completed_steps": ["generate"]}, schema_rejects=False)


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", True),
        ("status", "503"),
        ("status", 399),
        ("status", 600),
        ("title", ""),
        ("error", ""),
        ("trace_id", IDENTIFIER.replace("-", "")),
        ("type", "/relative/problem"),
    ],
)
def test_public_problem_is_strict_and_contains_no_hidden_fields(field: str, value: object) -> None:
    rejected(PublicProblem, {**problem(), field: value})


def test_summary_does_not_erase_confirmed_threshold_or_unknowns() -> None:
    for confirmation in ("none_confirmed", "unknown", "conflict"):
        rejected(RiskSummary, {**summary(), "confirmation": confirmation}, schema_rejects=False)
    rejected(RiskSummary, {**summary(), "minimum_severity": "critical"})
    rejected(RiskSummary, {**summary(), "findings": []})
    rejected(RiskSummary, {**summary(), "unknown_component_indices": [0]}, schema_rejects=False)
    rejected(RiskSummary, {**summary(), "freshness": "stale"}, schema_rejects=False)
    mixed = {**summary(), "coverage": "partial", "unknown_component_indices": [1]}
    assert RiskSummary.model_validate_json(json.dumps(mixed)).confirmation == "confirmed"


def test_summary_rejects_duplicate_and_conflicting_assessment_claim_bindings() -> None:
    rejected(RiskSummary, {**summary(), "findings": [finding(), finding()]}, schema_rejects=False)
    for field in ("event_id", "rule_id"):
        second = {**finding(), field: OTHER_IDENTIFIER, "grading_claim_id": OTHER_IDENTIFIER}
        rejected(RiskSummary, {**summary(), "findings": [finding(), second]}, schema_rejects=False)
    second = {
        **finding(),
        "component_index": 1,
        "assessment_id": OTHER_IDENTIFIER,
        "event_id": OTHER_IDENTIFIER,
    }
    rejected(RiskSummary, {**summary(), "findings": [finding(), second]}, schema_rejects=False)
    rejected(RiskSummary, {**summary(), "unknown_component_indices": [0, 0]}, schema_rejects=True)


@pytest.mark.parametrize("status", ["insufficient_evidence", "conflicting_evidence", "clean"])
def test_stack_findings_cannot_be_supported_by_unknown_or_safe_status(status: str) -> None:
    value = stack_envelope()
    result = value["result"]
    assert isinstance(result, dict)
    results = result["results"]
    assert isinstance(results, list) and isinstance(results[0], dict)
    results[0]["status"] = status
    rejected(StackCheckEnvelope, value, schema_rejects=status == "clean")


@pytest.mark.parametrize(
    "field,value", [("assessment_id", OTHER_IDENTIFIER), ("freshness", "stale"), ("citations", [])]
)
def test_stack_findings_require_the_same_current_evidenced_assessment(
    field: str, value: object
) -> None:
    envelope = stack_envelope()
    result = envelope["result"]
    assert isinstance(result, dict)
    results = result["results"]
    assert isinstance(results, list) and isinstance(results[0], dict)
    results[0][field] = value
    rejected(StackCheckEnvelope, envelope, schema_rejects=False)


def test_stack_summary_indices_and_unknown_component_coverage_are_complete() -> None:
    for summary_value in (
        {**summary(), "evaluated_components": 2},
        {**summary(), "coverage": "partial", "unknown_component_indices": [1]},
        {**summary(), "findings": [{**finding(), "component_index": 1}]},
    ):
        rejected(
            StackCheckEnvelope,
            {**stack_envelope(), "risk_summary": summary_value},
            schema_rejects=False,
        )
    envelope = stack_envelope()
    result = envelope["result"]
    assert isinstance(result, dict)
    results = result["results"]
    assert isinstance(results, list)
    unknown = deepcopy(results[0])
    assert isinstance(unknown, dict)
    unknown.update(status="insufficient_evidence", reason_code="no_match", assessment_id=None)
    results.append(unknown)
    envelope["risk_summary"] = {**summary(), "coverage": "partial"}
    rejected(StackCheckEnvelope, envelope, schema_rejects=False)
    envelope["risk_summary"] = {
        **summary(),
        "coverage": "partial",
        "unknown_component_indices": [1],
    }
    parsed = StackCheckEnvelope.model_validate_json(json.dumps(envelope))
    assert parsed.risk_summary.confirmation == "confirmed"
    assert parsed.result.results[1].status == "insufficient_evidence"


def test_empty_scope_cannot_claim_complete_or_safe_coverage() -> None:
    empty_result = {"kind": "completed", "results": [], "limitations": ["No evaluated inputs."]}
    empty_summary = {
        **summary(),
        "evaluated_components": 0,
        "findings": [],
        "confirmation": "none_confirmed",
    }
    envelope = {"result": empty_result, "risk_summary": empty_summary}
    rejected(StackCheckEnvelope, envelope, schema_rejects=False)
    envelope["risk_summary"] = {
        **empty_summary,
        "coverage": "unknown",
        "freshness": "unknown",
        "confirmation": "unknown",
    }
    parsed = StackCheckEnvelope.model_validate_json(json.dumps(envelope))
    assert parsed.risk_summary.confirmation == "unknown"


def test_schema_legacy_definitions_and_original_exports_are_unchanged() -> None:
    legacy = json.loads((ROOT / "contracts/schemas/public_api_v2.json").read_bytes())
    assert len(legacy["$defs"]) == 14
    for name, definition in legacy["$defs"].items():
        assert SCHEMA["$defs"][name] == definition
    for name in (
        "AskRequest",
        "AskResult",
        "DianziApiError",
        "DianziClient",
        "DianziTransportError",
        "StackCheckRequest",
        "StackCheckResult",
    ):
        assert name in ai_intel_client.__all__
