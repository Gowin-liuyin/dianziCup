"""All nine role entries reject hidden reserved outcomes before starting new operations."""

import copy

import pytest
from test_r14_shared_read_consumers import consumer_fixture

from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.graph_contracts import RoleReceipt, json_object
from ai_intel.investigation.workflow_service import _initial_state

__all__ = ["consumer_fixture"]


@pytest.mark.parametrize("role", list(AgentRole))
@pytest.mark.parametrize(
    "reason,key",
    [
        ("operation_outcome_unknown", "tool:compare_versions"),
        ("model_outcome_unknown", "model:qa"),
    ],
)
def test_every_role_resolves_hidden_incoming_unknown_before_reservation(
    consumer_fixture, role, reason, key
):
    fixture = consumer_fixture
    receipt = RoleReceipt(
        role=AgentRole.ASSESSOR,
        status="partial",
        reason_code="assessment_adapter_not_configured",
        evidence_ids=(),
        operation_keys=(key,),
        output={"inventory": None},
    )
    initial = {
        **_initial_state("a" * 64),
        "status": "partial",
        "stop_reason": "evidence_unavailable",
        "receipts": [json_object(receipt)],
    }
    unchanged = copy.deepcopy(initial)
    fixture.records[key] = {"error_code": reason}
    result = fixture.runtime.run_role(role, initial)
    assert result["status"] == "partial" and result["stop_reason"] == reason
    assert result["receipts"][-1]["reason_code"] == reason
    assert initial == unchanged
    assert fixture.calls == [] and fixture.reservations == []
    assert fixture.records == {key: {"error_code": reason}}
