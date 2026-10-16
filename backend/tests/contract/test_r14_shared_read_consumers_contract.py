"""Explicit fixture role receipts retain typed reads without promoting them to answer support."""

import json

import pytest
from test_r14_shared_read_consumers import consumer_fixture

from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.graph_contracts import RoleReceipt
from ai_intel.investigation.tool_contracts import ToolResult
from ai_intel.investigation.workflow_service import _initial_state

__all__ = ["consumer_fixture"]


@pytest.mark.parametrize(
    "role,field", [(AgentRole.COLLECTOR, "advisory"), (AgentRole.ASSESSOR, "inventory")]
)
def test_role_receipt_wire_preserves_tool_schema_mode_and_fixed_object(
    consumer_fixture, role, field
):
    runtime = consumer_fixture.runtime
    state = runtime.run_role(role, _initial_state("a" * 64))
    receipt = RoleReceipt.model_validate_json(json.dumps(state["receipts"][-1]))
    result = ToolResult.model_validate_json(json.dumps(receipt.output[field]))
    assert receipt.status == "partial" and result.evidence_ids == () and result.is_synthetic
    assert state["evidence"] == [] and runtime.projections(state) == ()
    assert result.data is not None and result.data.model_dump()["schema_version"] in {
        2,
        "r11-asset-candidate-1",
    }


def test_changes_wire_retains_empty_event_scope_and_no_final_assessment(consumer_fixture):
    runtime = consumer_fixture.runtime
    state = runtime.run_role(AgentRole.REPORTER, _initial_state("a" * 64))
    receipt = RoleReceipt.model_validate_json(json.dumps(state["receipts"][-1]))
    changes = ToolResult.model_validate_json(json.dumps(receipt.output["changes_pages"][0]))
    assert changes.searched_scope.event_id == runtime.request.event_id
    assert (
        receipt.output["changes_complete"] is True
        and receipt.output["report_export"] == "not_configured"
    )
    assert changes.evidence_ids == () and state["evidence"] == [] and state["draft"] is None
