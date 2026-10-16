"""Risk eligibility regressions use synthetic evidence and unchanged prior fixtures."""

from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy

import pytest
from ai_intel_client.cli import legacy_stack_exit_code
from ai_intel_client.models import (
    RiskSummary,
    StackCheckEnvelope,
    StackCheckResult,
    TaskResultEnvelope,
)
from pydantic import ValidationError
from test_public_extension_models import (
    IDENTIFIER,
    OTHER_IDENTIFIER,
    Payload,
    citation,
    finding,
    stack_envelope,
    summary,
    task,
    task_envelope,
)


def below_threshold_envelope() -> Payload:
    return {
        **stack_envelope(),
        "risk_summary": {
            **summary(),
            "confirmation": "none_confirmed",
            "findings": [{**finding(), "severity": "medium", "cvss_score": 4.0}],
        },
    }


def excluded_envelope() -> Payload:
    envelope = below_threshold_envelope()
    result = envelope["result"]
    assert isinstance(result, dict)
    results = result["results"]
    assert isinstance(results, list) and isinstance(results[0], dict)
    results[0]["status"] = "excluded_with_evidence"
    results[0]["reason_code"] = "explicit_exclusion"
    envelope["risk_summary"] = {**summary(), "confirmation": "none_confirmed", "findings": []}
    return envelope


def assessment_at(envelope: Payload, index: int = 0) -> Payload:
    result = envelope["result"]
    assert isinstance(result, dict)
    results = result["results"]
    assert isinstance(results, list) and isinstance(results[index], dict)
    return results[index]


def task_wrapped(envelope: Payload) -> Payload:
    return {
        **task_envelope(),
        "task": {**task(), "task_type": "stack_check", "status": "succeeded"},
        "result": envelope,
        "pending_steps": [],
        "completed_steps": ["checked"],
    }


@pytest.mark.parametrize("confirmation", ["unknown", "conflict"])
@pytest.mark.parametrize("wrapped", [False, True])
def test_complete_coverage_cannot_be_unknown_or_conflicting(
    confirmation: str, wrapped: bool
) -> None:
    envelope = excluded_envelope()
    envelope["risk_summary"] = {**summary(), "findings": [], "confirmation": confirmation}
    model = TaskResultEnvelope if wrapped else StackCheckEnvelope
    value = task_wrapped(envelope) if wrapped else envelope
    with pytest.raises(ValidationError):
        model.model_validate_json(json.dumps(value))


@pytest.mark.parametrize("missing", ["grade", "exclusion_citations", "exclusion_assessment"])
def test_complete_scope_requires_graded_support_or_traceable_exclusion(missing: str) -> None:
    envelope = (
        excluded_envelope() if missing.startswith("exclusion") else below_threshold_envelope()
    )
    if missing == "grade":
        envelope["risk_summary"] = {**summary(), "confirmation": "none_confirmed", "findings": []}
    else:
        assessment_at(envelope)[
            "citations" if missing == "exclusion_citations" else "assessment_id"
        ] = [] if missing == "exclusion_citations" else None
    with pytest.raises(ValidationError):
        StackCheckEnvelope.model_validate_json(json.dumps(envelope))


@pytest.mark.parametrize("missing", ["unknown", "grade"])
def test_partial_missing_eligibility_cannot_claim_none_confirmed(missing: str) -> None:
    envelope = below_threshold_envelope()
    if missing == "unknown":
        assessment_at(envelope).update(
            status="insufficient_evidence", reason_code="no_match", assessment_id=None
        )
    envelope["risk_summary"] = {
        **summary(),
        "confirmation": "none_confirmed",
        "coverage": "partial",
        "unknown_component_indices": [0],
        "findings": [],
    }
    with pytest.raises(ValidationError):
        StackCheckEnvelope.model_validate_json(json.dumps(envelope))


@pytest.mark.parametrize("coverage", ["partial", "unknown"])
def test_summary_only_cannot_call_an_incomplete_scope_none_confirmed(coverage: str) -> None:
    value = {
        **summary(),
        "confirmation": "none_confirmed",
        "coverage": coverage,
        "findings": [{**finding(), "severity": "medium", "cvss_score": 4.0}],
    }
    with pytest.raises(ValidationError):
        RiskSummary.model_validate_json(json.dumps(value))


@pytest.mark.parametrize("factory", [below_threshold_envelope, excluded_envelope])
@pytest.mark.parametrize("wrapped", [False, True])
def test_complete_low_grade_and_evidenced_exclusion_remain_valid(
    factory: Callable[[], Payload], wrapped: bool
) -> None:
    envelope = factory()
    model = TaskResultEnvelope if wrapped else StackCheckEnvelope
    value = task_wrapped(envelope) if wrapped else envelope
    parsed = model.model_validate_json(json.dumps(value))
    assert json.loads(parsed.wire_json()) == value


@pytest.mark.parametrize(
    "status",
    [
        "insufficient_evidence",
        "conflicting_evidence",
        "supported_applicability",
        "excluded_with_evidence",
    ],
)
def test_partial_unqualified_scope_remains_explicit_unknown(status: str) -> None:
    envelope = below_threshold_envelope()
    assessment = assessment_at(envelope)
    reason_codes = {
        "insufficient_evidence": "no_match",
        "conflicting_evidence": "explicit_conflict",
        "supported_applicability": "awaiting_grade",
        "excluded_with_evidence": "awaiting_exclusion_evidence",
    }
    assessment.update(status=status, reason_code=reason_codes[status])
    if status == "excluded_with_evidence":
        assessment["citations"] = []
    envelope["risk_summary"] = {
        **summary(),
        "findings": [],
        "confirmation": "unknown",
        "coverage": "partial",
        "unknown_component_indices": [0],
    }
    parsed = StackCheckEnvelope.model_validate_json(json.dumps(envelope))
    assert parsed.risk_summary.confirmation == "unknown"
    assert parsed.risk_summary.unknown_component_indices == (0,)


def test_partial_missing_grade_or_exclusion_evidence_preserves_global_uncertainty() -> None:
    for envelope in (below_threshold_envelope(), excluded_envelope()):
        assessment_at(envelope)["citations"] = []
        envelope["risk_summary"] = {
            **summary(),
            "findings": [],
            "confirmation": "unknown",
            "coverage": "partial",
        }
        parsed = StackCheckEnvelope.model_validate_json(json.dumps(envelope))
        assert parsed.risk_summary.confirmation == "unknown"
        assert parsed.risk_summary.coverage == "partial"
        assert len(parsed.result.results) == 1


def test_current_confirmed_risk_keeps_unknown_ungraded_components() -> None:
    envelope = stack_envelope()
    unknown = deepcopy(assessment_at(envelope))
    unknown["assessment_id"] = OTHER_IDENTIFIER
    result = envelope["result"]
    assert isinstance(result, dict) and isinstance(result["results"], list)
    result["results"].append(unknown)
    envelope["risk_summary"] = {
        **summary(),
        "coverage": "partial",
        "evaluated_components": 2,
        "unknown_component_indices": [1],
    }
    parsed = StackCheckEnvelope.model_validate_json(json.dumps(envelope))
    assert parsed.risk_summary.confirmation == "confirmed"
    assert parsed.risk_summary.findings[0].assessment_id.hex == IDENTIFIER.replace("-", "")
    assert len(parsed.result.results) == 2
    assert parsed.risk_summary.unknown_component_indices == (1,)


@pytest.mark.parametrize("status", ["succeeded", "partial"])
def test_task_union_rechecks_risk_eligibility_without_erasing_partial_result(status: str) -> None:
    envelope = below_threshold_envelope()
    envelope["risk_summary"] = {
        **summary(),
        "findings": [],
        "confirmation": "unknown",
        "coverage": "partial",
        "unknown_component_indices": [0],
    }
    value = {
        **task_wrapped(envelope),
        "task": {**task(), "task_type": "stack_check", "status": status},
    }
    parsed = TaskResultEnvelope.model_validate_json(json.dumps(value))
    assert isinstance(parsed.result, StackCheckEnvelope)
    assert parsed.result.risk_summary.confirmation == "unknown"


@pytest.mark.parametrize("factory", [below_threshold_envelope, excluded_envelope])
def test_legacy_cli_without_new_risk_summary_keeps_unknown_exit_code(
    factory: Callable[[], Payload],
) -> None:
    envelope = factory()
    parsed = StackCheckEnvelope.model_validate_json(json.dumps(envelope))
    legacy = StackCheckResult.model_validate_json(parsed.result.wire_json())
    assert legacy_stack_exit_code(legacy) == 2


def test_supported_zero_grade_preserves_explicit_grade_and_evidence() -> None:
    envelope = below_threshold_envelope()
    envelope["risk_summary"] = {
        **summary(),
        "confirmation": "none_confirmed",
        "findings": [{**finding(), "severity": "none", "cvss_score": 0}],
    }
    parsed = StackCheckEnvelope.model_validate_json(json.dumps(envelope))
    assert parsed.risk_summary.findings[0].cvss_score == 0
    assert parsed.risk_summary.findings[0].citations[0].quote == citation()["quote"]
