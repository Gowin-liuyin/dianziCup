"""Offline interleavings exercise the roster fence; real deadlock proof remains separate."""

from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from tests.unit.test_public_write_adapters import fixture_request
from tests.unit.test_r18_current_risk_summary import fixture_receipt, producer_fixture
from tests.unit.test_r18_public_component_selector import selection_fixture

from ai_intel.api.public_risk_summary import _current_rule_scope, build_current_stack_envelope
from ai_intel.assessment.rule_persistence import lock_rule_inputs
from ai_intel.domain.enums import AssessmentStatus


def test_optimistic_roster_never_locks_rule_before_canonical_source_and_publication(monkeypatch):
    _service, knowledge = selection_fixture()
    session = knowledge.session
    session.execute.return_value.mappings.return_value = []
    assert _current_rule_scope(knowledge) == ((), None)
    first = session.execute.call_args.args[0].compile(dialect=postgresql.dialect())
    assert "condition_rule_versions" in str(first) and "FOR " not in str(first)
    rule = fixture_receipt().prepared.inputs.rule
    monkeypatch.setattr(
        "ai_intel.assessment.rule_persistence._all_source_rows",
        lambda session, rule: [{"source_id": "fixture-source", "revision_id": "fixture-revision"}],
    )
    session.execute.return_value.all.return_value = []
    lock_rule_inputs(session, rule, knowledge.scope)
    statements = [
        call.args[0].compile(dialect=postgresql.dialect())
        for call in session.execute.call_args_list
    ]
    source = next(
        index
        for index, query in enumerate(statements)
        if "source:fixture-source" in query.params.values()
    )
    publication = next(
        index
        for index, query in enumerate(statements)
        if "knowledge-publication:public" in query.params.values()
    )
    rule_lock = next(
        index
        for index, query in enumerate(statements)
        if "condition_rule_versions" in str(query) and "FOR UPDATE" in str(query)
    )
    assert 0 < source < publication < rule_lock


@pytest.mark.parametrize("score", [9.8, 6.9])
def test_new_rule_before_canonical_publication_lock_never_leaves_complete_coverage(
    monkeypatch, score
):
    receipt, service, knowledge = producer_fixture(monkeypatch, score=score)
    original = receipt.prepared.inputs.rule
    added = original.model_copy(update={"rule_id": str(uuid4())})
    reader = Mock(side_effect=[((original,), None), ((original, added), None)])
    monkeypatch.setattr("ai_intel.api.public_risk_summary._current_rule_scope", reader)
    result = build_current_stack_envelope(fixture_request(), service, knowledge)
    assert result.risk_summary.confirmation == ("confirmed" if score == 9.8 else "unknown")
    assert result.risk_summary.coverage == "partial"
    assert result.risk_summary.unknown_component_indices == (0,)
    assert result.risk_summary.evaluated_components == 0
    assert "current_rule_scope_changed" in result.result.limitations
    assert result.risk_summary.findings[0].cvss_score == score
    assert reader.call_count == 2


@pytest.mark.parametrize(
    "status", [AssessmentStatus.SUPPORTED_APPLICABILITY, AssessmentStatus.EXCLUDED_WITH_EVIDENCE]
)
@pytest.mark.parametrize("change", ["retired", "new_version", "payload_changed"])
def test_changed_rule_cannot_leave_a_current_positive_or_negative(monkeypatch, status, change):
    receipt, service, knowledge = producer_fixture(monkeypatch, status=status)
    original = receipt.prepared.inputs.rule
    if change == "retired":
        final = ()
    elif change == "new_version":
        final = (original.model_copy(update={"version": original.version + 1}),)
    else:
        final = (original.model_copy(update={"supporting_claim_ids": ("changed-claim",)}),)
    monkeypatch.setattr(
        "ai_intel.api.public_risk_summary._current_rule_scope",
        Mock(side_effect=[((original,), None), (final, None)]),
    )
    result = build_current_stack_envelope(fixture_request(), service, knowledge)
    assert result.risk_summary.confirmation == "unknown"
    assert result.risk_summary.coverage == "unknown"
    assert result.risk_summary.freshness == "stale"
    assert result.risk_summary.unknown_component_indices == (0,)
    assert not result.risk_summary.findings
    assert result.result.results[0].status == "insufficient_evidence"
    assert result.result.results[0].freshness == "stale" and not result.result.results[0].citations


def test_final_scope_overflow_keeps_current_finding_and_explicit_unknown(monkeypatch):
    receipt, service, knowledge = producer_fixture(monkeypatch)
    original = receipt.prepared.inputs.rule
    monkeypatch.setattr(
        "ai_intel.api.public_risk_summary._current_rule_scope",
        Mock(side_effect=[((original,), None), ((), "published_rule_query_limit_exceeded")]),
    )
    result = build_current_stack_envelope(fixture_request(), service, knowledge)
    assert result.risk_summary.confirmation == "confirmed"
    assert result.risk_summary.coverage == "partial"
    assert result.risk_summary.unknown_component_indices == (0,)
    assert "published_rule_query_limit_exceeded" in result.result.limitations


def test_final_roster_read_follows_all_qualified_shared_assessment_reads(monkeypatch):
    receipt, service, knowledge = producer_fixture(monkeypatch)
    original = receipt.prepared.inputs.rule
    orders = []

    def read_roster(knowledge):
        orders.append(("roster", service.read_in_session.call_count))
        return (original,), None

    monkeypatch.setattr("ai_intel.api.public_risk_summary._current_rule_scope", read_roster)
    result = build_current_stack_envelope(fixture_request(), service, knowledge)
    assert result.risk_summary.coverage == "complete"
    assert orders == [("roster", 0), ("roster", 3)]
