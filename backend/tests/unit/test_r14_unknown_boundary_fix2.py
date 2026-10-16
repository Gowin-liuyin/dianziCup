"""Explicit offline fixtures exercise unknown IO boundaries and immutable receipt recovery."""

import hashlib
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from test_r14_shared_read_consumers import consumer_fixture

from ai_intel.api.knowledge_contracts import EvidenceResponse
from ai_intel.domain.access import PermissionDeniedError
from ai_intel.infrastructure.models.generation import GenerationRequest
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.graph import (
    build_investigation_graph,
    normalize_unknown_operation_state,
)
from ai_intel.investigation.graph_contracts import PlannerDecision, RoleReceipt, json_object
from ai_intel.investigation.tool_contracts import (
    CompareVersionsArguments,
    CompareVersionsCall,
    FindChangesArguments,
    FindChangesCall,
    GetAdvisoryArguments,
    GetAdvisoryCall,
    GetInventoryArguments,
    GetInventoryCall,
    ReadEvidenceArguments,
    ReadEvidenceCall,
)
from ai_intel.investigation.workflow_service import WorkflowChangedError, _initial_state
from ai_intel.workers.jobs import JobLeaseLostError

__all__ = ["consumer_fixture"]


def make_tool_call(fixture, tool_name):
    request = fixture.runtime.request
    goal_id = UUID(fixture.runtime.context.job_id)
    if tool_name == "get_advisory":
        return GetAdvisoryCall(
            tool_name=tool_name,
            goal_id=goal_id,
            arguments=GetAdvisoryArguments(event_id=request.event_id),
        )
    if tool_name == "get_inventory":
        return GetInventoryCall(
            tool_name=tool_name,
            goal_id=goal_id,
            arguments=GetInventoryArguments(
                asset_id=request.asset_id, snapshot_id=request.asset_snapshot_id
            ),
        )
    if tool_name == "find_changes":
        return FindChangesCall(
            tool_name=tool_name,
            goal_id=goal_id,
            arguments=FindChangesArguments(event_id=request.event_id),
        )
    if tool_name == "compare_versions":
        return CompareVersionsCall(
            tool_name=tool_name,
            goal_id=goal_id,
            arguments=CompareVersionsArguments(
                left_version="1.0", right_version="2.0", scheme="pep440", ecosystem="pypi"
            ),
        )
    return ReadEvidenceCall(
        tool_name=tool_name,
        goal_id=goal_id,
        arguments=ReadEvidenceArguments(
            event_id=request.event_id, evidence_id=uuid4(), revision_id=uuid4()
        ),
    )


@pytest.mark.parametrize("reason", ["operation_outcome_unknown", "model_outcome_unknown"])
@pytest.mark.parametrize(
    "tool_name",
    ["get_advisory", "get_inventory", "find_changes", "compare_versions", "read_evidence"],
)
def test_every_tool_stops_before_lookup_when_prior_operation_is_unknown(
    consumer_fixture, monkeypatch, reason, tool_name
):
    fixture = consumer_fixture
    fixture.runtime.last_operation_error = reason

    def forbidden_lookup(key):
        raise AssertionError("unknown boundary must stop before a later operation lookup")

    monkeypatch.setattr(fixture.runtime, "lookup", forbidden_lookup)
    assert (
        fixture.runtime.tool(
            AgentRole.ORCHESTRATOR, make_tool_call(fixture, tool_name), "tool:fixture-later"
        )
        is None
    )
    assert fixture.runtime.last_operation_error == reason
    assert fixture.reservations == [] and fixture.calls == []


@pytest.mark.parametrize("reason", ["operation_outcome_unknown", "model_outcome_unknown"])
def test_model_stops_before_lookup_and_factory_when_prior_operation_is_unknown(
    consumer_fixture, monkeypatch, reason
):
    fixture = consumer_fixture
    fixture.runtime.last_operation_error = reason

    def forbidden_lookup(key):
        raise AssertionError("unknown boundary must stop before a later model lookup")

    monkeypatch.setattr(fixture.runtime, "lookup", forbidden_lookup)
    request = GenerationRequest(
        system_text="explicit fixture",
        question="fixture question",
        evidence_texts=(),
        prompt_version="fixture-1",
        schema_version="fixture-1",
        model_version="fixture-1",
        max_output_tokens=100,
        allow_format_repair=False,
    )
    assert (
        fixture.runtime.model(
            AgentRole.ORCHESTRATOR, request, PlannerDecision, "model:fixture-later"
        )
        is None
    )
    assert fixture.runtime.last_operation_error == reason
    assert fixture.reservations == [] and fixture.calls == []


@pytest.mark.parametrize("strategy", ["B2", "B2b"])
def test_triage_unknown_first_evidence_stops_before_second_read(consumer_fixture, strategy):
    fixture = consumer_fixture
    refs = tuple(
        ReadEvidenceArguments(
            event_id=fixture.runtime.request.event_id, evidence_id=uuid4(), revision_id=uuid4()
        )
        for _ in range(2)
    )
    fixture.runtime.request = fixture.runtime.request.model_copy(
        update={"strategy": strategy, "evidence_refs": refs}
    )
    key = "tool:triage:" + str(refs[0].evidence_id)
    fixture.records[key] = {"error_code": "operation_outcome_unknown"}
    result = fixture.runtime.run_role(AgentRole.TRIAGE, _initial_state("a" * 64))
    assert result["status"] == "partial" and result["stop_reason"] == "operation_outcome_unknown"
    assert result["receipts"][-1]["operation_keys"] == [key]
    assert result["receipts"][-1]["reason_code"] == "operation_outcome_unknown"
    assert fixture.calls == [] and all(kind == "node" for _, kind, _ in fixture.reservations)


def test_critic_unknown_read_is_partial_without_false_support_change_or_model(consumer_fixture):
    fixture = consumer_fixture
    reference = ReadEvidenceArguments(
        event_id=fixture.runtime.request.event_id, evidence_id=uuid4(), revision_id=uuid4()
    )
    fixture.runtime.request = fixture.runtime.request.model_copy(
        update={"evidence_refs": (reference,)}
    )
    quote = "explicit fixture source"
    evidence = EvidenceResponse(
        span_id=reference.evidence_id,
        revision_id=reference.revision_id,
        block_id=None,
        start_offset=0,
        end_offset=len(quote),
        quote_text=quote,
        quote_sha256=hashlib.sha256(quote.encode()).hexdigest(),
        locator_kind="text",
        page_number=None,
        json_pointer=None,
        verified_at=None,
        source_uri=None,
        source_published_at=None,
        source_modified_at=None,
        first_observed_at=None,
        ingested_at=None,
        data_mode="fixture",
    )
    key = "tool:critic:" + str(reference.evidence_id)
    fixture.records[key] = {"error_code": "operation_outcome_unknown"}
    initial = {
        **_initial_state("a" * 64),
        "draft": {},
        "verified": True,
        "evidence": [json_object(evidence)],
    }
    result = fixture.runtime.run_role(AgentRole.CRITIC, initial)
    assert result["status"] == "partial" and result["stop_reason"] == "operation_outcome_unknown"
    assert result["draft"] is None and result["verified"] is False
    assert result["receipts"][-1]["reason_code"] == "operation_outcome_unknown"
    assert result["receipts"][-1]["operation_keys"] == [key]
    assert fixture.calls == [] and all(kind == "node" for _, kind, _ in fixture.reservations)


@pytest.mark.parametrize(
    "reason,key",
    [("operation_outcome_unknown", "tool:compare_versions"), ("model_outcome_unknown", "model:qa")],
)
@pytest.mark.parametrize("strategy", ["B2", "B2b", "B3"])
def test_completed_node_recovers_unknown_from_pg_receipt_without_rewriting_old_node(
    consumer_fixture, strategy, reason, key
):
    fixture = consumer_fixture
    fixture.runtime.request = fixture.runtime.request.model_copy(update={"strategy": strategy})
    receipt = RoleReceipt(
        role=AgentRole.ASSESSOR,
        status="partial",
        reason_code="assessment_adapter_not_configured",
        evidence_ids=(),
        operation_keys=(key,),
        output={},
    )
    old = {
        **_initial_state("a" * 64),
        "status": "partial",
        "stop_reason": "evidence_unavailable",
        "receipts": [json_object(receipt)],
    }
    original_node = {"state": old}
    fixture.records["node:assessor"] = original_node
    fixture.records[key] = {"error_code": reason}
    calls = []

    def execute(role, state):
        calls.append(role)
        return fixture.runtime.run_role(role, state)

    graph = build_investigation_graph(strategy, execute, InMemorySaver())
    result = graph.invoke(
        _initial_state("a" * 64), {"configurable": {"thread_id": "fixture-old-hidden-unknown"}}
    )
    assert result["status"] == "partial" and result["stop_reason"] == reason
    assert calls[-1] == AgentRole.ASSESSOR
    assert fixture.records["node:assessor"] is original_node
    assert original_node["state"]["stop_reason"] == "evidence_unavailable"
    assert (
        original_node["state"]["receipts"][0]["reason_code"] == "assessment_adapter_not_configured"
    )
    assert not any(call.tool_name == "find_changes" for _, call in fixture.calls)
    assert not any(kind == "model" for _, kind, _ in fixture.reservations)


@pytest.mark.parametrize(
    "status,stop_reason",
    [
        ("failed", "answer_citation_invalid"),
        ("waiting_approval", "permission_required"),
        ("stale", "current_support_changed"),
        ("partial", "critical_conflict"),
    ],
)
def test_unknown_normalization_preserves_confirmed_safety_outcomes(status, stop_reason):
    state = {
        **_initial_state("a" * 64),
        "status": status,
        "stop_reason": stop_reason,
        "receipts": [{"reason_code": "operation_outcome_unknown"}],
    }
    result = normalize_unknown_operation_state(state)
    assert result["status"] == status and result["stop_reason"] == stop_reason


@pytest.mark.parametrize(
    "error",
    [
        PermissionDeniedError("fixture revoked"),
        JobLeaseLostError("fixture lease lost"),
        WorkflowChangedError("scope_epoch_changed"),
    ],
)
def test_real_guard_errors_precede_unknown_recovery(consumer_fixture, monkeypatch, error):
    fixture = consumer_fixture

    def rejected_guard(**kwargs):
        raise error

    monkeypatch.setattr(fixture.runtime, "guard", rejected_guard)
    state = {**_initial_state("a" * 64), "receipts": [{"reason_code": "operation_outcome_unknown"}]}
    with pytest.raises(type(error)):
        fixture.runtime.run_role(AgentRole.ASSESSOR, state)
    assert fixture.reservations == [] and fixture.calls == []
