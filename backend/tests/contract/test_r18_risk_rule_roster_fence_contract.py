"""The new roster fence preserves frozen wire and canonical shared-lock ownership."""

import ast
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from tests.contract.test_r18_current_risk_summary_contract import SCHEMA, frozen_sdk
from tests.unit.test_public_write_adapters import fixture_request
from tests.unit.test_r18_current_risk_summary import producer_fixture

from ai_intel.api.public_risk_summary import build_current_stack_envelope
from ai_intel.domain.enums import AssessmentStatus

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("change", ["new_rule", "retired", "version", "overflow"])
@pytest.mark.parametrize(
    "status", [AssessmentStatus.SUPPORTED_APPLICABILITY, AssessmentStatus.EXCLUDED_WITH_EVIDENCE]
)
def test_scope_drift_never_emits_a_frozen_complete_or_none_confirmed_wire(
    monkeypatch, change, status
):
    receipt, service, knowledge = producer_fixture(monkeypatch, status=status)
    rule = receipt.prepared.inputs.rule
    gap = None
    if change == "new_rule":
        final = (rule, rule.model_copy(update={"rule_id": str(uuid4())}))
    elif change == "retired":
        final = ()
    elif change == "version":
        final = (rule.model_copy(update={"version": rule.version + 1}),)
    else:
        final, gap = (), "published_rule_query_limit_exceeded"
    monkeypatch.setattr(
        "ai_intel.api.public_risk_summary._current_rule_scope",
        Mock(side_effect=[((rule,), None), (final, gap)]),
    )
    envelope = build_current_stack_envelope(fixture_request(), service, knowledge)
    wire = envelope.model_dump_json(exclude_unset=True)
    SCHEMA.validate(envelope.model_dump(mode="json", exclude_unset=True))
    client = frozen_sdk().StackCheckEnvelope.model_validate_json(wire)
    assert client.risk_summary.coverage != "complete"
    assert client.risk_summary.confirmation != "none_confirmed"
    assert client.risk_summary.unknown_component_indices == (0,)
    if change in {"retired", "version"}:
        assert client.result.results[0].freshness == "stale"
        assert not client.risk_summary.findings


def test_producer_roster_reader_does_not_introduce_its_own_rule_mutex_or_publication_lock():
    source = ast.parse(
        (ROOT / "backend/src/ai_intel/api/public_risk_summary.py").read_text(encoding="utf-8")
    )
    reader = next(
        node
        for node in source.body
        if isinstance(node, ast.FunctionDef) and node.name == "_current_rule_scope"
    )
    calls = [node for node in ast.walk(reader) if isinstance(node, ast.Call)]
    assert not any(
        isinstance(node.func, ast.Attribute) and node.func.attr == "with_for_update"
        for node in calls
    )
    assert not any(
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and "knowledge-publication:" in node.value
        for node in ast.walk(reader)
    )
    build = next(
        node
        for node in source.body
        if isinstance(node, ast.FunctionDef) and node.name == "build_current_stack_envelope"
    )
    roster_calls = [
        node
        for node in ast.walk(build)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_current_rule_scope"
    ]
    assert len(roster_calls) == 2
