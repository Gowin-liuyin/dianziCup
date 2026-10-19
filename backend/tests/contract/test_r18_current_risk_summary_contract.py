"""Frozen extensions and the separately loaded SDK must accept identical truthful envelopes."""

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from tests.unit.test_public_write_adapters import fixture_request
from tests.unit.test_r18_current_risk_summary import producer_fixture

from ai_intel.api.public_risk_summary import PublicStackCheckEnvelope, build_current_stack_envelope
from ai_intel.domain.enums import AssessmentStatus

ROOT = Path(__file__).resolve().parents[3]
EXTENSIONS = json.loads(
    (ROOT / "contracts/schemas/public_api_extensions_v1.json").read_text(encoding="utf-8")
)
SCHEMA = Draft202012Validator(
    {"$ref": "#/$defs/StackCheckEnvelope", "$defs": EXTENSIONS["$defs"]},
    format_checker=FormatChecker(),
)


def frozen_sdk():
    path = ROOT / "sdk/python/ai_intel_client/models.py"
    spec = importlib.util.spec_from_file_location("risk_summary_frozen_sdk", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def envelope(monkeypatch, *, status=AssessmentStatus.SUPPORTED_APPLICABILITY, score=9.8):
    _receipt, service, knowledge = producer_fixture(monkeypatch, status=status, score=score)
    return build_current_stack_envelope(fixture_request(), service, knowledge)


@pytest.mark.parametrize(
    ("status", "score", "confirmation"),
    [
        (AssessmentStatus.SUPPORTED_APPLICABILITY, 9.8, "confirmed"),
        (AssessmentStatus.SUPPORTED_APPLICABILITY, 6.9, "none_confirmed"),
        (AssessmentStatus.EXCLUDED_WITH_EVIDENCE, 9.8, "none_confirmed"),
    ],
)
def test_producer_wire_matches_frozen_schema_and_sdk(monkeypatch, status, score, confirmation):
    result = envelope(monkeypatch, status=status, score=score)
    wire = result.model_dump_json(exclude_unset=True)
    SCHEMA.validate(json.loads(wire))
    client = frozen_sdk().StackCheckEnvelope.model_validate_json(wire)
    assert client.risk_summary.confirmation == confirmation
    assert client.result.results[0].component.package_name == "fixture"
    assert "tenant_id" not in wire and "private-preparation" not in wire


@pytest.mark.parametrize(
    "change",
    [
        "unknown_index",
        "finding_index",
        "duplicate_finding",
        "wrong_assessment",
        "wrong_status",
        "missing_assessment_citation",
        "missing_grade_citation",
        "severity_disagrees",
        "none_confirmation",
        "complete_stale",
        "unknown_complete",
        "evaluated_overflow",
        "unknown_duplicate",
        "bad_policy",
        "unsupported_grade_version",
    ],
)
def test_frozen_cross_array_invariants_reject_untruthful_wire(monkeypatch, change):
    value = copy.deepcopy(envelope(monkeypatch).model_dump(mode="json", exclude_unset=True))
    summary = value["risk_summary"]
    finding = summary["findings"][0]
    result = value["result"]["results"][0]
    if change == "unknown_index":
        summary.update(coverage="partial", unknown_component_indices=[1])
    elif change == "finding_index":
        finding["component_index"] = 1
    elif change == "duplicate_finding":
        summary["findings"].append(copy.deepcopy(finding))
    elif change == "wrong_assessment":
        finding["assessment_id"] = "00000000-0000-0000-0000-000000000099"
    elif change == "wrong_status":
        result["status"] = "excluded_with_evidence"
    elif change == "missing_assessment_citation":
        result["citations"] = []
    elif change == "missing_grade_citation":
        finding["citations"] = []
    elif change == "severity_disagrees":
        finding["severity"] = "low"
    elif change == "none_confirmation":
        summary["confirmation"] = "none_confirmed"
    elif change == "complete_stale":
        summary["freshness"] = "stale"
    elif change == "unknown_complete":
        summary["unknown_component_indices"] = [0]
    elif change == "evaluated_overflow":
        summary["evaluated_components"] = 2
    elif change == "unknown_duplicate":
        summary.update(coverage="partial", unknown_component_indices=[0, 0])
    elif change == "bad_policy":
        summary["policy_version"] = "injected-policy"
    elif change == "unsupported_grade_version":
        finding["cvss_version"] = "5.0"
    wire = json.dumps(value)
    with pytest.raises(ValueError):
        PublicStackCheckEnvelope.model_validate_json(wire)
    with pytest.raises(ValueError):
        frozen_sdk().StackCheckEnvelope.model_validate_json(wire)


def test_new_producer_does_not_change_any_original_v2_definition():
    original = json.loads(
        (ROOT / "contracts/schemas/public_api_v2.json").read_text(encoding="utf-8")
    )
    assert all(
        EXTENSIONS["$defs"][name] == definition for name, definition in original["$defs"].items()
    )
