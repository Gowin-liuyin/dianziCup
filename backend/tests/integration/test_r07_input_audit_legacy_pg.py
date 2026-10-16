"""Old absent versions retain exact hashes and identities without generating a new paid receipt."""

from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from sqlalchemy import insert, select, text
from sqlalchemy.orm import Session
from test_r07_job_execution_pg import children, setup

from ai_intel.enrichment import model_fields
from ai_intel.enrichment.job_contracts import EnrichmentExecutionPolicy, EventEnrichmentRequest
from ai_intel.enrichment.job_models import enrichment_job_steps, enrichment_workflows
from ai_intel.enrichment.job_service import ENRICHMENT_PARENT_JOB_TYPE, RULE_VERSION, _digest
from ai_intel.enrichment.job_types import EnrichmentJobPayload, json_payload
from ai_intel.infrastructure.outbox import IdempotencyConflictError, enqueue_job
from ai_intel.knowledge.models import job_runs
from r07_input_audit_helpers import audit_engine as audit_engine
from r07_input_audit_helpers import run

pytestmark = pytest.mark.real_pg


def old_workflow(engine, tmp_path):
    service, scope, session_hash, event_id, request, _ = setup(engine, tmp_path)
    workflow_id = uuid5(NAMESPACE_URL, "ai-intel:enrichment:" + repr((None, "legacy-audit-key")))
    policy = service.execution_policy().model_dump(mode="json", exclude={"model_input_versions"})
    binding = {
        "event_id": str(event_id),
        "actor_user_id": scope.user_id,
        "actor_session_hash": session_hash,
        "actor_tenant_id": scope.tenant_id,
        "actor_role": scope.role.value,
        "actor_permission_version": scope.permission_version,
        "request_sha256": _digest(request.model_dump(mode="json")),
        "execution_policy_sha256": _digest(policy),
        "rule_version": RULE_VERSION,
    }
    with Session(engine) as session, session.begin():
        parent_id = enqueue_job(
            session,
            None,
            ENRICHMENT_PARENT_JOB_TYPE,
            json_payload(
                EnrichmentJobPayload(workflow_id=workflow_id, binding_sha256=_digest(binding))
            ),
            service.clock(),
            idempotency_key="legacy-audit-key",
        )
        session.execute(
            insert(enrichment_workflows).values(
                **binding,
                workflow_id=str(workflow_id),
                parent_job_id=parent_id,
                visibility="public",
                tenant_id=None,
                request_payload=request.model_dump(mode="json"),
                execution_policy=policy,
                created_at=service.clock(),
            )
        )
    return service, scope, session_hash, event_id, request, workflow_id, parent_id


def test_legacy_replay_retains_absent_versions_and_original_policy_hash(
    audit_engine, tmp_path, monkeypatch
):
    service, scope, session_hash, event_id, request, workflow_id, parent_id = old_workflow(
        audit_engine, tmp_path
    )
    with audit_engine.connect() as connection:
        before = connection.scalar(
            text("SELECT to_jsonb(w) FROM enrichment_workflows w WHERE workflow_id=:wf"),
            {"wf": str(workflow_id)},
        )
    monkeypatch.setattr(model_fields, "PROMPT_VERSION", "future-prompt-version")
    with Session(audit_engine) as session, session.begin():
        receipt = service.enqueue(
            session,
            scope,
            event_id,
            request,
            actor_session_hash=session_hash,
            idempotency_key="legacy-audit-key",
            created_at=service.clock(),
        )
    with audit_engine.connect() as connection:
        after = connection.scalar(
            text("SELECT to_jsonb(w) FROM enrichment_workflows w WHERE workflow_id=:wf"),
            {"wf": str(workflow_id)},
        )
    assert before == after and "model_input_versions" not in after["execution_policy"]
    assert (
        receipt.reused
        and receipt.workflow_id == workflow_id
        and str(receipt.parent_job_id) == parent_id
    )


@pytest.mark.parametrize("mutation", ["body", "policy", "session"])
def test_legacy_same_scope_changed_binding_remains_conflicting(audit_engine, tmp_path, mutation):
    service, scope, session_hash, event_id, request, _, _ = old_workflow(audit_engine, tmp_path)
    if mutation == "body":
        request = EventEnrichmentRequest(expected_event_version=1, dimensions=("versions",))
    elif mutation == "policy":
        service.execution_policy = lambda: EnrichmentExecutionPolicy(data_mode="live")
    else:
        from datetime import timedelta

        from ai_intel.api.auth_state import auth_sessions

        session_hash = _digest("synthetic-new-session")
        with audit_engine.begin() as connection:
            connection.execute(
                insert(auth_sessions).values(
                    session_hash=session_hash,
                    user_id=scope.user_id,
                    csrf_token="synthetic-new-csrf",
                    issued_at=service.clock(),
                    expires_at=service.clock() + timedelta(hours=1),
                )
            )
    with pytest.raises(IdempotencyConflictError), Session(audit_engine) as session, session.begin():
        service.enqueue(
            session,
            scope,
            event_id,
            request,
            actor_session_hash=session_hash,
            idempotency_key="legacy-audit-key",
            created_at=service.clock(),
        )


@pytest.mark.parametrize("reserved", [False, True])
def test_legacy_model_steps_cannot_get_a_new_selector_or_wire_call(
    audit_engine, tmp_path, reserved
):
    service, scope, session_hash, _, _, workflow_id, parent_id = old_workflow(
        audit_engine, tmp_path
    )
    assert run(service, parent_id) == "succeeded"
    step = next(
        item
        for item in children(service)
        if item["workflow_id"] == str(workflow_id) and item["dimension"] == "versions"
    )

    def forbidden_client():
        raise AssertionError("legacy execution must not construct a new generation client")

    service.generation_client_factory = forbidden_client
    if reserved:
        assert service._reserve_model_call(step["job_id"], service.clock())
    assert run(service, step["job_id"]) == ("failed" if reserved else "blocked")
    with Session(audit_engine) as session:
        observed = service.read_input_audit(
            session,
            scope,
            UUID(step["job_id"]),
            actor_session_hash=session_hash,
            at=service.clock(),
        )
        code = session.scalar(
            select(job_runs.c.error_code).where(job_runs.c.job_id == step["job_id"])
        )
        persisted = (
            session.execute(
                select(enrichment_job_steps).where(enrichment_job_steps.c.job_id == step["job_id"])
            )
            .mappings()
            .one()
        )
    assert code == (
        "incomplete_interrupted" if reserved else "legacy_model_input_audit_unavailable"
    )
    assert observed.audit_state == "legacy_unavailable" and observed.record is None
    assert persisted["model_call_completed_at"] is None and persisted["model_trace"] == []


def test_old_structured_steps_keep_existing_semantics_without_model_audit(audit_engine, tmp_path):
    service, _, _, _, _, workflow_id, parent_id = old_workflow(audit_engine, tmp_path)
    assert run(service, parent_id) == "succeeded"
    step = next(
        item
        for item in children(service)
        if item["workflow_id"] == str(workflow_id) and item["dimension"] == "cvss"
    )
    assert run(service, step["job_id"]) == "succeeded"
    with Session(audit_engine) as session:
        payload = session.scalar(
            select(enrichment_job_steps.c.input_audit_payload).where(
                enrichment_job_steps.c.job_id == step["job_id"]
            )
        )
    assert payload is None
