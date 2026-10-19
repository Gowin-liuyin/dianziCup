"""Independent synthetic cases check public profile validation boundaries."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
import pytest


ROOT = Path(__file__).resolve().parents[3]
SCHEMA = json.loads((ROOT / "contracts/schemas/public_api_extensions_v1.json").read_text(encoding="utf-8"))
EXAMPLES = json.loads((ROOT / "contracts/schemas/public_api_v2_examples.json").read_text(encoding="utf-8"))
ID = "11111111-2222-4333-8444-555555555555"
NOW = "2026-10-16T09:00:00+08:00"


def valid(name: str, value: object) -> bool:
    return Draft202012Validator(
        {**SCHEMA, "$ref": "#/$defs/" + name}, format_checker=FormatChecker()
    ).is_valid(value)


def finding() -> dict[str, object]:
    return {
        "component_index": 0, "event_id": ID, "assessment_id": ID,
        "rule_id": ID, "rule_version": 1, "grading_claim_id": ID,
        "severity": "high", "cvss_score": 8.4, "cvss_version": "3.1",
        "citations": [{"evidence_id": ID, "revision_id": ID,
                       "quote": "Synthetic grade 8.4", "locator": "/score",
                       "source_uri": "https://example.invalid/review"}],
        "freshness": "current",
    }


def summary() -> dict[str, object]:
    return {
        "policy_version": "r18-risk-policy-1", "minimum_severity": "high",
        "confirmation": "confirmed", "coverage": "complete", "freshness": "current",
        "evaluated_components": 1, "unknown_component_indices": [], "findings": [finding()],
    }


def source() -> dict[str, object]:
    return {
        "source_id": "synthetic-review-source", "name": "Synthetic review source",
        "category": "vendor_advisory", "enabled": True, "health": "healthy",
        "last_attempt_at": NOW, "last_success_at": NOW, "reason_code": None,
        "data_mode": "fixture",
    }


def task() -> dict[str, object]:
    return {
        "task_id": ID, "task_type": "ask", "status": "queued",
        "poll_uri": "/api/v1/tasks/" + ID, "created_at": NOW, "updated_at": NOW,
    }


def answer() -> dict[str, object]:
    return copy.deepcopy(EXAMPLES["valid"]["AskResult"][1])


def stack() -> dict[str, object]:
    return {
        "result": {"kind": "completed", "results": [{
            "component": {"ecosystem": "PyPI", "package_name": "synthetic-review", "version": "1.0"},
            "status": "supported_applicability", "reason_code": "matched_rule",
            "assessment_id": ID, "citations": finding()["citations"], "freshness": "current",
        }], "limitations": []},
        "risk_summary": summary(),
    }


def problem() -> dict[str, object]:
    return {"type": "urn:dianzi:problem:blocked", "title": "Synthetic blocked",
            "status": 503, "error": "not_configured", "trace_id": ID}


def envelope(status: str = "queued", task_type: str = "ask") -> dict[str, object]:
    descriptor = task()
    descriptor.update(status=status, task_type=task_type)
    result = answer() if task_type == "ask" else stack()
    return {
        "task": descriptor,
        "result": result if status in {"succeeded", "partial"} else None,
        "error": problem() if status in {"failed", "blocked", "cancelled"} else None,
        "completed_steps": ["retrieve"] if status in {"succeeded", "partial"} else [],
        "pending_steps": ["generate"] if status in {"queued", "partial"} else [],
        "failed_steps": ["generate"] if status in {"failed", "blocked", "cancelled"} else [],
    }


SAMPLES = {
    "RiskFinding": finding(), "RiskSummary": summary(), "StackCheckEnvelope": stack(),
    "VulnerabilityPage": {"items": [], "next_cursor": None, "data_mode": "fixture"},
    "VulnerabilityDetailPage": {
        "vulnerability": {"intel_id": ID, "event_id": ID, "title": "Synthetic review",
                          "external_ids": [], "enrichments": [], "relations": [], "freshness": "unknown"},
        "advisories": [], "next_cursor": None, "mapping_limits": [], "data_mode": "fixture",
    },
    "SourceDescriptor": source(),
    "SourcePage": {"items": [source()], "next_cursor": None, "data_mode": "fixture"},
    "TaskDescriptor": task(), "PublicProblem": problem(), "TaskResultEnvelope": envelope(),
}


@pytest.mark.parametrize("name", list(SAMPLES))
def test_all_new_objects_reject_extra_fields(name: str) -> None:
    sample = copy.deepcopy(SAMPLES[name])
    assert valid(name, sample)
    sample["skip_validation"] = True
    assert not valid(name, sample)


@pytest.mark.parametrize("name,field", [
    ("RiskFinding", "event_id"), ("RiskFinding", "assessment_id"),
    ("RiskFinding", "rule_id"), ("RiskFinding", "grading_claim_id"),
    ("TaskDescriptor", "task_id"), ("PublicProblem", "trace_id"),
])
def test_new_uuid_fields_reject_malformed_identifiers(name: str, field: str) -> None:
    sample = copy.deepcopy(SAMPLES[name])
    sample[field] = "------------------------------------"
    assert not valid(name, sample)


@pytest.mark.parametrize("name,field", [
    ("TaskDescriptor", "created_at"), ("TaskDescriptor", "updated_at"),
    ("SourceDescriptor", "last_attempt_at"), ("SourceDescriptor", "last_success_at"),
])
@pytest.mark.parametrize("bad_time", ["2026-10-16T09:00:00", "2026-02-30T09:00:00Z"])
def test_date_fields_reject_naive_or_impossible_dates(name: str, field: str, bad_time: str) -> None:
    sample = copy.deepcopy(SAMPLES[name])
    sample[field] = bad_time
    assert not valid(name, sample)


@pytest.mark.parametrize("severity,score,expected", [
    ("none", 0, True), ("none", 0.01, False), ("low", 0.01, True),
    ("low", 3.999, True), ("low", 4, False), ("medium", 4, True),
    ("medium", 6.999, True), ("medium", 7, False), ("high", 7, True),
    ("high", 8.999, True), ("high", 9, False), ("critical", 9, True),
    ("critical", 10, True), ("critical", 10.01, False), ("low", -0.01, False),
])
def test_normalized_score_bands(severity: str, score: float, expected: bool) -> None:
    sample = finding()
    sample.update(severity=severity, cvss_score=score)
    assert valid("RiskFinding", sample) is expected


@pytest.mark.parametrize("version", ["2.0", "3.0", "3.1", "4.0"])
def test_normalized_band_preserves_cvss_source_version(version: str) -> None:
    sample = finding()
    sample.update(severity="critical", cvss_score=9, cvss_version=version)
    assert valid("RiskFinding", sample)


@pytest.mark.parametrize("threshold,severity,score,expected", [
    ("low", "none", 0, False), ("low", "low", 0.1, True),
    ("medium", "low", 3.9, False), ("medium", "medium", 4, True),
    ("high", "medium", 6.9, False), ("high", "high", 7, True),
    ("critical", "high", 8.9, False), ("critical", "critical", 9, True),
])
def test_confirmation_requires_finding_at_requested_threshold(
    threshold: str, severity: str, score: float, expected: bool
) -> None:
    sample = summary()
    grade = finding()
    grade.update(severity=severity, cvss_score=score)
    sample.update(minimum_severity=threshold, findings=[grade])
    assert valid("RiskSummary", sample) is expected


@pytest.mark.parametrize("status", [
    "queued", "running", "retry_wait", "waiting_approval", "succeeded",
    "partial", "failed", "cancelled", "blocked",
])
@pytest.mark.parametrize("task_type", ["ask", "stack_check"])
def test_all_nine_states_accept_corresponding_typed_payload(status: str, task_type: str) -> None:
    assert valid("TaskResultEnvelope", envelope(status, task_type))


@pytest.mark.parametrize("status", ["queued", "running", "retry_wait", "waiting_approval"])
def test_nonterminal_task_rejects_fabricated_result(status: str) -> None:
    sample = envelope(status)
    sample["result"] = answer()
    assert not valid("TaskResultEnvelope", sample)


@pytest.mark.parametrize("field,value", [
    ("result", None), ("error", problem()), ("pending_steps", ["generate"]),
    ("failed_steps", ["generate"]),
])
def test_succeeded_task_rejects_missing_result_or_unfinished_work(field: str, value: object) -> None:
    sample = envelope("succeeded")
    sample[field] = value
    assert not valid("TaskResultEnvelope", sample)


@pytest.mark.parametrize("status", ["failed", "cancelled", "blocked"])
@pytest.mark.parametrize("field,value", [("result", answer()), ("error", None)])
def test_failed_terminal_rejects_success_or_missing_problem(
    status: str, field: str, value: object
) -> None:
    sample = envelope(status)
    sample[field] = value
    assert not valid("TaskResultEnvelope", sample)


@pytest.mark.parametrize("task_type", ["ask", "stack_check"])
def test_success_rejects_other_task_payload_type(task_type: str) -> None:
    sample = envelope("succeeded", task_type)
    sample["result"] = stack() if task_type == "ask" else answer()
    assert not valid("TaskResultEnvelope", sample)


@pytest.mark.parametrize("name", ["SourcePage", "VulnerabilityPage", "VulnerabilityDetailPage"])
@pytest.mark.parametrize("cursor", ["", "x" * 2049])
def test_pages_reject_invalid_cursor_length(name: str, cursor: str) -> None:
    sample = copy.deepcopy(SAMPLES[name])
    sample["next_cursor"] = cursor
    assert not valid(name, sample)


def test_source_page_rejects_more_than_hundred_items() -> None:
    sample = copy.deepcopy(SAMPLES["SourcePage"])
    sample["items"] = [source() for _ in range(101)]
    assert not valid("SourcePage", sample)


@pytest.mark.parametrize("poll_uri", [
    "https://example.invalid/api/v1/tasks/" + ID,
    "/api/v1/tasks/" + ID + "/../../secrets", "/api/v1/tasks/" + ID + "?token=synthetic",
])
def test_task_polling_rejects_external_or_path_injected_uri(poll_uri: str) -> None:
    sample = task()
    sample["poll_uri"] = poll_uri
    assert not valid("TaskDescriptor", sample)


@pytest.mark.parametrize("poll_tail", ["-" * 36, "a" * 36])
def test_task_polling_rejects_non_uuid_tail(poll_tail: str) -> None:
    sample = task()
    sample["poll_uri"] = "/api/v1/tasks/" + poll_tail
    assert not valid("TaskDescriptor", sample)
