"""Isolated read-result fixtures retain PG status and immutable historical operation payloads."""

import copy
from contextlib import contextmanager

import pytest
from test_r14_shared_read_consumers import consumer_fixture

from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.graph_contracts import RoleReceipt, json_object
from ai_intel.investigation.workflow_service import _initial_state

__all__ = ["consumer_fixture"]


@pytest.mark.parametrize("status", ["partial", "failed", "waiting_approval"])
@pytest.mark.parametrize("later_reporter", [False, True])
@pytest.mark.parametrize(
    "reason,key",
    [("operation_outcome_unknown", "tool:compare_versions"), ("model_outcome_unknown", "model:qa")],
)
def test_read_result_uses_reserved_receipt_without_rewriting_pg_status_or_history(
    consumer_fixture, monkeypatch, status, later_reporter, reason, key
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
    old = {
        **_initial_state("a" * 64),
        "status": "partial",
        "stop_reason": "evidence_unavailable",
        "receipts": [json_object(receipt)],
    }
    if later_reporter:
        old["receipts"].append(
            json_object(
                RoleReceipt(
                    role=AgentRole.REPORTER,
                    status="partial",
                    reason_code="report_export_adapter_not_configured",
                    evidence_ids=(),
                    operation_keys=(),
                    output={},
                )
            )
        )
    saved = {"state": old}
    unchanged = copy.deepcopy(saved)
    fixture.records[key] = {"error_code": reason}
    guards = []

    class ReadOnlyResult:
        def scalars(self):
            return self

        def all(self):
            return [saved]

    class ReadOnlySession:
        def execute(self, statement):
            assert statement.is_select
            return ReadOnlyResult()

    @contextmanager
    def transaction():
        yield ReadOnlySession()

    def guard_session(session):
        guards.append(session)
        fixture.runtime.job_status = status

    monkeypatch.setattr(fixture.runtime, "transaction", transaction)
    monkeypatch.setattr(fixture.runtime, "guard_session", guard_session)
    result = fixture.runtime.read_result()
    assert len(guards) == 1
    assert result.status == status and result.stop_reason == reason
    assert result.receipts[0].reason_code == reason
    assert result.answer is None
    assert saved == unchanged and fixture.records[key] == {"error_code": reason}
    assert fixture.calls == [] and fixture.reservations == []
