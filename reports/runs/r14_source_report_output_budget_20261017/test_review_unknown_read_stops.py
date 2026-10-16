"""Independent graph-level regressions for unknown read reservations and later IO."""

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from test_r14_shared_read_consumers import consumer_fixture

from ai_intel.investigation.graph import build_investigation_graph
from ai_intel.investigation.workflow_service import _initial_state

__all__ = ["consumer_fixture"]


@pytest.mark.parametrize(
    "unknown_key", ["tool:collector:get_advisory", "tool:assessor:get_inventory"]
)
def test_prior_unknown_read_prevents_later_reporter_change_io(consumer_fixture, unknown_key):
    fixture = consumer_fixture
    fixture.records[unknown_key] = {"error_code": "operation_outcome_unknown"}
    graph = build_investigation_graph("B2b", fixture.runtime.run_role, InMemorySaver())
    result = graph.invoke(
        _initial_state(fixture.runtime.input_sha256),
        {"configurable": {"thread_id": "review-prior-unknown"}},
    )
    assert "operation_outcome_unknown" in {
        receipt["reason_code"] for receipt in result["receipts"]
    }
    assert all(call.tool_name != "find_changes" for _, call in fixture.calls)
