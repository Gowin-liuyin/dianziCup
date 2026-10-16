"""Public envelope fixtures test contradictions and preserve the frozen legacy profile."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = json.loads(
    (ROOT / "contracts/schemas/public_api_extensions_v1.json").read_text(encoding="utf-8")
)
LEGACY = json.loads((ROOT / "contracts/schemas/public_api_v2.json").read_text(encoding="utf-8"))
IDENTIFIER = "00000000-0000-4000-8000-000000000001"


def validate(name: str, value: object) -> bool:
    validator = Draft202012Validator(
        {**SCHEMA, "$ref": "#/$defs/" + name}, format_checker=FormatChecker()
    )
    return validator.is_valid(value)


def risk_finding() -> dict[str, object]:
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
        "citations": [
            {
                "evidence_id": IDENTIFIER,
                "revision_id": IDENTIFIER,
                "quote": "Synthetic source grades this event.",
                "locator": "/metrics/score",
                "source_uri": "https://example.invalid/synthetic-advisory",
            }
        ],
        "freshness": "current",
    }


def risk_summary() -> dict[str, object]:
    return {
        "policy_version": "r18-risk-policy-1",
        "minimum_severity": "high",
        "confirmation": "unknown",
        "coverage": "unknown",
        "freshness": "unknown",
        "evaluated_components": 0,
        "unknown_component_indices": [],
        "findings": [],
    }


def task_result() -> dict[str, object]:
    return {
        "task": {
            "task_id": IDENTIFIER,
            "task_type": "ask",
            "status": "queued",
            "poll_uri": "/api/v1/tasks/" + IDENTIFIER,
            "created_at": "2026-10-16T08:00:00+08:00",
            "updated_at": "2026-10-16T08:00:00+08:00",
        },
        "result": None,
        "error": None,
        "completed_steps": [],
        "pending_steps": ["generate"],
        "failed_steps": [],
    }


def test_legacy_definitions_are_preserved_without_field_expansion() -> None:
    assert len(LEGACY["$defs"]) == 14
    for name, definition in LEGACY["$defs"].items():
        assert SCHEMA["$defs"][name] == definition
    assert len(SCHEMA["$defs"]) == 24


@pytest.mark.parametrize(
    ("severity", "score", "expected"),
    [
        ("none", 0, True),
        ("low", 0.1, True),
        ("low", 0, False),
        ("low", 4, False),
        ("medium", 4, True),
        ("medium", 7, False),
        ("high", 7, True),
        ("high", 9, False),
        ("critical", 9, True),
        ("critical", 10, True),
        ("critical", 10.1, False),
    ],
)
def test_risk_grade_boundaries(severity: str, score: float, expected: bool) -> None:
    finding = risk_finding()
    finding.update(severity=severity, cvss_score=score)
    assert validate("RiskFinding", finding) is expected


@pytest.mark.parametrize(
    "missing", ["grading_claim_id", "assessment_id", "citations", "rule_version"]
)
def test_confirmed_grade_requires_traceable_support(missing: str) -> None:
    finding = risk_finding()
    del finding[missing]
    assert not validate("RiskFinding", finding)


def test_missing_evidence_cannot_be_confirmed_high_risk() -> None:
    summary = risk_summary()
    assert validate("RiskSummary", summary)
    summary["confirmation"] = "confirmed"
    assert not validate("RiskSummary", summary)
    summary["findings"] = [risk_finding()]
    assert validate("RiskSummary", summary)
    summary["minimum_severity"] = "critical"
    assert not validate("RiskSummary", summary)


def test_source_health_remains_unknown_until_an_actual_observation() -> None:
    source = {
        "source_id": "synthetic-source",
        "name": "Synthetic official source",
        "category": "vendor_advisory",
        "enabled": True,
        "health": "never_polled",
        "last_attempt_at": None,
        "last_success_at": None,
        "reason_code": None,
        "data_mode": "fixture",
    }
    assert validate("SourceDescriptor", source)
    source["secret_ref"] = "untrusted-input"
    assert not validate("SourceDescriptor", source)


def test_terminal_task_cannot_keep_a_queued_handle_or_fabricate_an_answer() -> None:
    result = task_result()
    assert validate("TaskResultEnvelope", result)
    completed = json.loads(
        (ROOT / "contracts/schemas/public_api_v2_examples.json").read_text(encoding="utf-8")
    )["valid"]["AskResult"][1]
    result["result"] = completed
    assert not validate("TaskResultEnvelope", result)
    task = result["task"]
    assert isinstance(task, dict)
    task["status"] = "succeeded"
    result["pending_steps"] = []
    assert validate("TaskResultEnvelope", result)
    task["task_type"] = "stack_check"
    assert not validate("TaskResultEnvelope", result)


@pytest.mark.parametrize("status", ["failed", "cancelled", "blocked"])
def test_failed_task_has_an_explicit_problem(status: str) -> None:
    result = task_result()
    task = result["task"]
    assert isinstance(task, dict)
    task["status"] = status
    assert not validate("TaskResultEnvelope", result)
    result["error"] = {
        "type": "urn:dianzi:problem:not-configured",
        "title": "Dependency unavailable",
        "status": 503,
        "error": "not_configured",
        "trace_id": IDENTIFIER,
    }
    assert validate("TaskResultEnvelope", result)


def test_legacy_examples_keep_the_same_positive_and_negative_results() -> None:
    examples = json.loads(
        (ROOT / "contracts/schemas/public_api_v2_examples.json").read_text(encoding="utf-8")
    )
    for group, expected in (("valid", True), ("invalid", False)):
        for name, values in examples[group].items():
            for value in values:
                assert validate(name, copy.deepcopy(value)) is expected
