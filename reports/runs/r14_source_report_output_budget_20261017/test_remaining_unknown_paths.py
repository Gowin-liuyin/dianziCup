"""Independent regressions cover unknown outcomes inside one role and cached old nodes."""

import pytest
import json
from pathlib import Path
from langgraph.checkpoint.memory import InMemorySaver
from test_r14_shared_read_consumers import consumer_fixture

from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.graph import build_investigation_graph
from ai_intel.investigation.tool_contracts import CompareVersionsArguments
from ai_intel.investigation.workflow_service import _initial_state

__all__ = ["consumer_fixture"]


def test_unknown_version_comparison_prevents_same_role_inventory_io(consumer_fixture):
    fixture = consumer_fixture
    fixture.runtime.request = fixture.runtime.request.model_copy(update={
        "version_comparison": CompareVersionsArguments(
            left_version="1.0", right_version="2.0", scheme="pep440", ecosystem="pypi"
        )
    })
    fixture.records["tool:compare_versions"] = {"error_code": "operation_outcome_unknown"}
    result = fixture.runtime.run_role(AgentRole.ASSESSOR, _initial_state("a" * 64))
    assert fixture.calls == []
    assert not any(key == "tool:assessor:get_inventory" for key, _, _ in fixture.reservations)
    assert result["stop_reason"] == "operation_outcome_unknown"


@pytest.mark.parametrize("strategy", ["B2", "B2b", "B3"])
def test_cached_old_assessor_node_restores_unknown_stop_reason(consumer_fixture, strategy):
    fixture = consumer_fixture
    fixture.runtime.request = fixture.runtime.request.model_copy(update={"strategy": strategy})
    old = _initial_state("a" * 64)
    old["status"] = "partial"
    old["stop_reason"] = "evidence_unavailable"
    sample = json.loads(Path(__file__).with_name("original_graph_unknown_samples.json").read_text())[1]
    receipts = sample["role_receipts"]
    assessor_index = next(index for index, receipt in enumerate(receipts) if receipt["role"] == "assessor")
    old["receipts"] = receipts[:assessor_index + 1]
    fixture.records["node:assessor"] = {"state": old}
    graph = build_investigation_graph(strategy, fixture.runtime.run_role, InMemorySaver())
    result = graph.invoke(
        _initial_state("a" * 64), {"configurable": {"thread_id": "review-cached-assessor"}}
    )
    assert result["status"] == "partial"
    assert result["stop_reason"] == "operation_outcome_unknown"
    assert all(call.tool_name != "find_changes" for _, call in fixture.calls)
