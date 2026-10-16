"""Explicit offline graph fixtures verify all scheduling boundaries stop unknown operations."""

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from test_r14_shared_read_consumers import consumer_fixture

from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.graph import build_investigation_graph
from ai_intel.investigation.workflow_service import _initial_state

__all__ = ["consumer_fixture"]


@pytest.mark.parametrize("strategy", ["B2", "B2b", "B3"])
@pytest.mark.parametrize(
    "unknown_key", ["tool:collector:get_advisory", "tool:assessor:get_inventory"]
)
def test_unknown_read_stops_before_every_later_role_and_model(
    consumer_fixture, strategy, unknown_key
):
    fixture = consumer_fixture
    fixture.runtime.request = fixture.runtime.request.model_copy(update={"strategy": strategy})
    fixture.records[unknown_key] = {"error_code": "operation_outcome_unknown"}
    roles = []

    def execute(role, state):
        roles.append(role)
        return fixture.runtime.run_role(role, state)

    graph = build_investigation_graph(strategy, execute, InMemorySaver())
    result = graph.invoke(
        _initial_state(fixture.runtime.input_sha256),
        {"configurable": {"thread_id": "fixture-unknown-stop"}},
    )
    last_role = AgentRole.COLLECTOR if "collector" in unknown_key else AgentRole.ASSESSOR
    assert roles == list(AgentRole)[: list(AgentRole).index(last_role) + 1]
    assert result["status"] == "partial" and result["stop_reason"] == "operation_outcome_unknown"
    assert result["receipts"][-1]["role"] == last_role.value
    assert [call.tool_name for _, call in fixture.calls] == (
        [] if last_role == AgentRole.COLLECTOR else ["get_advisory"]
    )
    assert not any(kind == "model" for _, kind, _ in fixture.reservations)
    assert not any(key.startswith("node:reporter") for key, _, _ in fixture.reservations)


@pytest.mark.parametrize("strategy", ["B2", "B2b", "B3"])
@pytest.mark.parametrize("reason", ["operation_outcome_unknown", "model_outcome_unknown"])
def test_restored_unknown_receipt_stops_before_first_callback(consumer_fixture, strategy, reason):
    initial = _initial_state("a" * 64)
    initial["status"] = "partial"
    initial["stop_reason"] = "collection_adapter_not_configured"
    initial["receipts"] = [{"reason_code": reason}]
    calls = []

    def execute(role, state):
        calls.append(role)
        raise AssertionError("restored unknown outcome must stop before a new role")

    graph = build_investigation_graph(strategy, execute, InMemorySaver())
    result = graph.invoke(initial, {"configurable": {"thread_id": "fixture-restored-unknown"}})
    assert calls == [] and result["status"] == "partial" and result["stop_reason"] == reason
    assert consumer_fixture.reservations == [] and consumer_fixture.calls == []


@pytest.mark.parametrize("role", list(AgentRole))
def test_direct_role_entry_stops_prior_unknown_before_new_operation(consumer_fixture, role):
    fixture = consumer_fixture
    initial = {
        **_initial_state("a" * 64),
        "status": "partial",
        "stop_reason": "evidence_unavailable",
        "receipts": [{"reason_code": "operation_outcome_unknown"}],
    }
    result = fixture.runtime.run_role(role, initial)
    assert result["status"] == "partial" and result["stop_reason"] == "operation_outcome_unknown"
    assert fixture.reservations == [] and fixture.calls == []
