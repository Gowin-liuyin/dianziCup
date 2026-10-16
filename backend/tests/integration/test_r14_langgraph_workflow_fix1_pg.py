"""Original independent crash-boundary oracles; real PG and explicit model wire fixture."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, update
from test_r14_langgraph_workflow_pg import (
    claim,
    evidence_request,
    fixture_factory,
    principal_session,
    service,
)
from test_r14_langgraph_workflow_pg import (
    workflow_resources as workflow_resources,
)

from ai_intel.api.actor_references import InvalidActorReferenceError
from ai_intel.api.auth_state import auth_sessions
from ai_intel.api.authentication import SessionExpiredError
from ai_intel.domain.access import CrossTenantAccessError
from ai_intel.investigation.graph_contracts import WorkflowBudget
from ai_intel.investigation.workflow_service import _WorkflowRuntime, investigation_operations
from ai_intel.knowledge.models import scope_epochs, users

pytestmark = pytest.mark.real_pg


class ReviewProcessLoss(BaseException):
    """A deterministic process-loss boundary after external IO but before node receipt."""


@pytest.mark.parametrize(
    "confirmed", [False, True], ids=["model_outcome_unknown", "model_succeeded"]
)
def test_review_interrupted_qa_node_preserves_model_outcome_and_recovery(
    workflow_resources, tmp_path, monkeypatch, register_sensitive_failure_value, confirmed
):
    engine, _, _ = workflow_resources
    _, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)
    calls = []
    subject = service(workflow_resources, token, fixture_factory(monkeypatch, request, calls))
    job_id = subject.enqueue(request, WorkflowBudget(), idempotency_key="review-model-loss")
    context = claim(engine, job_id)
    subject.execute(context, pause_after=("graph_writer",))
    original_complete = _WorkflowRuntime.complete_operation

    def lose_after_model(self, key, output, status="succeeded"):
        if key == "model:qa" and "value" in output:
            if confirmed:
                original_complete(self, key, output, status)
            raise ReviewProcessLoss()
        return original_complete(self, key, output, status)

    with monkeypatch.context() as loss:
        loss.setattr(_WorkflowRuntime, "complete_operation", lose_after_model)
        with pytest.raises(ReviewProcessLoss):
            subject.execute(context)
    assert len(calls) == 1
    with engine.connect() as connection:
        rows = dict(
            connection.execute(
                select(
                    investigation_operations.c.operation_key, investigation_operations.c.status
                ).where(investigation_operations.c.job_id == str(job_id))
            ).all()
        )
    assert rows["node:qa"] == "reserved"
    assert rows["model:qa"] == ("succeeded" if confirmed else "reserved")
    resumed = subject.execute(context)
    with engine.connect() as connection:
        charged = connection.scalar(
            select(func.sum(investigation_operations.c.model_calls)).where(
                investigation_operations.c.job_id == str(job_id)
            )
        )
    if confirmed:
        assert len(calls) == 2 and charged == 2
        assert resumed.answer is not None
    else:
        assert len(calls) == 1 and charged == 1 and resumed.answer is None
        assert resumed.stop_reason == "model_outcome_unknown"
        assert "model_outcome_unknown" in resumed.missing_requirements


@pytest.mark.parametrize("change", ["session", "role", "epoch"])
def test_confirmed_paid_qa_recovery_rechecks_current_authority(
    workflow_resources, tmp_path, monkeypatch, register_sensitive_failure_value, change
):
    engine, _, _ = workflow_resources
    user_id, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)
    calls = []
    subject = service(workflow_resources, token, fixture_factory(monkeypatch, request, calls))
    context = claim(
        engine, subject.enqueue(request, WorkflowBudget(), idempotency_key="paid-revoked")
    )
    subject.execute(context, pause_after=("graph_writer",))
    original_complete = _WorkflowRuntime.complete_operation

    def lose_after_confirmed_model(self, key, output, status="succeeded"):
        original_complete(self, key, output, status)
        if key == "model:qa" and "value" in output:
            raise ReviewProcessLoss()

    with monkeypatch.context() as loss:
        loss.setattr(_WorkflowRuntime, "complete_operation", lose_after_confirmed_model)
        with pytest.raises(ReviewProcessLoss):
            subject.execute(context)
    assert len(calls) == 1
    with engine.begin() as connection:
        if change == "session":
            connection.execute(
                update(auth_sessions)
                .where(auth_sessions.c.user_id == user_id)
                .values(revoked_at=datetime.now(UTC))
            )
        elif change == "role":
            connection.execute(
                update(users).where(users.c.user_id == user_id).values(role="viewer")
            )
        else:
            connection.execute(
                update(scope_epochs)
                .where(scope_epochs.c.scope_key == "public")
                .values(epoch=scope_epochs.c.epoch + 1)
            )
    if change == "epoch":
        result = subject.execute(context)
        assert result.status == "stale" and result.answer is None and result.evidence_ids == ()
    else:
        with pytest.raises(
            (SessionExpiredError, InvalidActorReferenceError, CrossTenantAccessError)
        ):
            subject.execute(context)
    assert len(calls) == 1
    with engine.connect() as connection:
        assert (
            connection.scalar(
                select(func.sum(investigation_operations.c.model_calls)).where(
                    investigation_operations.c.job_id == context.job_id
                )
            )
            == 1
        )
