"""Private selection is authorized internally and corrupted persistent evidence fails closed."""

from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import insert, select, text, update
from sqlalchemy.orm import Session
from tests.integration.test_r07_input_audit_receipts_pg import recorded_workflow
from tests.r07_idempotency_scope_helpers import create_actor

from ai_intel.api.auth_state import auth_sessions
from ai_intel.domain.access import AccessScope, Role
from ai_intel.enrichment.job_contracts import EnrichmentExecutionPolicy
from ai_intel.enrichment.job_models import enrichment_job_steps
from ai_intel.enrichment.job_service import EnrichmentWorkflowError, _audit_sql_digest, _digest
from ai_intel.knowledge.models import users
from ai_intel.knowledge.persistence_models import events
from r07_input_audit_helpers import audit_engine as audit_engine
from r07_input_audit_helpers import prepared_workflow, run

pytestmark = pytest.mark.real_pg


def private_recorded_workflow(engine, tmp_path, monkeypatch):
    service, scope, session_hash, event_id, request, _, _, calls = prepared_workflow(
        engine, tmp_path, monkeypatch
    )
    tenant = "synthetic-audit-private-tenant"
    private_scope = AccessScope.for_authenticated_user(scope.user_id, tenant, Role.TENANT_ADMIN)
    with engine.begin() as connection:
        connection.execute(
            update(users)
            .where(users.c.user_id == scope.user_id)
            .values(role="tenant_admin", tenant_id=tenant)
        )
        connection.execute(
            update(events)
            .where(events.c.event_id == str(event_id))
            .values(visibility="tenant", tenant_id=tenant)
        )
    service.execution_policy = lambda: EnrichmentExecutionPolicy(
        generation_enabled=True,
        generation_provider="openai",
        approved_model="fixture-model",
        private_egress_granted=True,
        data_mode="fixture",
    )
    with Session(engine) as session, session.begin():
        receipt = service.enqueue(
            session,
            private_scope,
            event_id,
            request,
            actor_session_hash=session_hash,
            idempotency_key="private-audit",
            created_at=service.clock(),
        )
    assert run(service, receipt.parent_job_id) == "succeeded"
    with Session(engine) as session:
        step = (
            session.execute(
                select(enrichment_job_steps).where(
                    enrichment_job_steps.c.workflow_id == str(receipt.workflow_id),
                    enrichment_job_steps.c.dimension == "versions",
                )
            )
            .mappings()
            .one()
        )
    assert run(service, step["job_id"]) == "partial"
    return service, private_scope, session_hash, receipt, step, calls


def test_private_selection_is_absent_from_public_dto_but_authorized_internal_read_exists(
    audit_engine, tmp_path, monkeypatch
):
    service, scope, session_hash, receipt, step, _ = private_recorded_workflow(
        audit_engine, tmp_path, monkeypatch
    )
    with Session(audit_engine) as session:
        public = service.read_workflow(
            session, scope, receipt.workflow_id, actor_session_hash=session_hash, at=service.clock()
        ).model_dump_json()
        internal = service.read_input_audit(
            session,
            scope,
            UUID(step["job_id"]),
            actor_session_hash=session_hash,
            at=service.clock(),
        )
    assert internal.audit_state == "recorded" and internal.record.input_selections[0].texts
    assert all(
        item not in public
        for item in (
            "input_audit",
            "input_selections",
            "source_versions",
            "input_context",
            "actor_session_hash",
            session_hash,
        )
    )


@pytest.mark.parametrize(
    "reader", ["other_tenant", "same_tenant_viewer", "revoked", "changed_role", "parent_acl"]
)
def test_current_scope_session_role_and_parent_acl_protect_private_selection(
    audit_engine, tmp_path, monkeypatch, reader
):
    service, scope, session_hash, _, step, _ = private_recorded_workflow(
        audit_engine, tmp_path, monkeypatch
    )
    if reader in {"other_tenant", "same_tenant_viewer"}:
        tenant = "synthetic-other" if reader == "other_tenant" else scope.tenant_id
        role = Role.TENANT_ADMIN if reader == "other_tenant" else Role.VIEWER
        scope, session_hash = create_actor(audit_engine, tenant_id=tenant, role=role)
    elif reader == "revoked":
        with audit_engine.begin() as connection:
            connection.execute(
                update(auth_sessions)
                .where(auth_sessions.c.session_hash == session_hash)
                .values(revoked_at=service.clock())
            )
    elif reader == "changed_role":
        with audit_engine.begin() as connection:
            connection.execute(
                update(users).where(users.c.user_id == scope.user_id).values(role="viewer")
            )
    else:
        with audit_engine.begin() as connection:
            connection.execute(
                text("UPDATE sources SET visibility='tenant', tenant_id='synthetic-other-parent'")
            )
    with pytest.raises(PermissionError), Session(audit_engine) as session:
        service.read_input_audit(
            session,
            scope,
            UUID(step["job_id"]),
            actor_session_hash=session_hash,
            at=service.clock(),
        )


def test_new_same_actor_session_can_read_history_without_rebinding_execution(
    audit_engine, tmp_path, monkeypatch
):
    service, scope, old_session, _, step, _, original = recorded_workflow(
        audit_engine, tmp_path, monkeypatch
    )
    new_session = _digest("synthetic-authorized-new-read-session")
    with audit_engine.begin() as connection:
        connection.execute(
            update(auth_sessions)
            .where(auth_sessions.c.session_hash == old_session)
            .values(revoked_at=service.clock())
        )
        connection.execute(
            insert(auth_sessions).values(
                session_hash=new_session,
                user_id=scope.user_id,
                csrf_token="synthetic-read-csrf",
                issued_at=service.clock(),
                expires_at=service.clock() + timedelta(hours=1),
            )
        )
    with Session(audit_engine) as session:
        observed = service.read_input_audit(
            session, scope, UUID(step["job_id"]), actor_session_hash=new_session, at=service.clock()
        )
    assert observed == original


@pytest.mark.parametrize("tamper", ["hash", "source_hash", "omission", "extra", "job_identity"])
def test_corrupt_persisted_audit_is_rejected_even_if_database_constraints_are_fault_injected(
    audit_engine, tmp_path, monkeypatch, tamper
):
    service, scope, session_hash, _, step, _, original = recorded_workflow(
        audit_engine, tmp_path, monkeypatch
    )
    payload = original.record.model_dump(mode="json")
    if tamper == "source_hash":
        payload["input_selections"][0]["source_versions"][0]["content_sha256"] = "0" * 64
    elif tamper == "omission":
        payload["input_selections"][0]["omitted_ranges"].append(
            {
                "revision_id": payload["input_selections"][0]["source_versions"][0]["revision_id"],
                "block_id": payload["input_selections"][0]["selected"][0]["block_id"],
                "start_offset": 0,
                "end_offset": 1,
                "matched_cues": [],
            }
        )
    elif tamper == "extra":
        payload["input_selections"][0]["tenant_id"] = "untrusted-body-grant"
    elif tamper == "job_identity":
        payload["job_id"] = "00000000-0000-0000-0000-000000000000"
    with audit_engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE enrichment_job_steps DISABLE TRIGGER enrichment_input_audit_guard")
        )
        connection.execute(
            text("ALTER TABLE enrichment_job_steps DROP CONSTRAINT ck_enrichment_step_input_audit")
        )
        connection.execute(
            update(enrichment_job_steps)
            .where(enrichment_job_steps.c.job_id == step["job_id"])
            .values(
                input_audit_payload=payload,
                input_audit_sha256="0" * 64 if tamper == "hash" else _audit_sql_digest(payload),
            )
        )
    with pytest.raises(EnrichmentWorkflowError) as blocked, Session(audit_engine) as session:
        service.read_input_audit(
            session,
            scope,
            UUID(step["job_id"]),
            actor_session_hash=session_hash,
            at=service.clock(),
        )
    assert blocked.value.code == "enrichment_input_audit_invalid" and blocked.value.status == 409
