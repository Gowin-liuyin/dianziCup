"""Real PG transactions protect historical audit text against concurrent ACL writers."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from uuid import UUID

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from tests.security.test_r07_input_audit_security_pg import private_recorded_workflow

from ai_intel.api.auth_state import auth_sessions
from ai_intel.knowledge.models import document_revisions, users
from ai_intel.knowledge.persistence_models import event_documents
from r07_input_audit_helpers import audit_engine as audit_engine

pytestmark = pytest.mark.real_pg
PARENT_TABLES = ("sources", "documents", "document_revisions")


@pytest.mark.parametrize("parent", (*PARENT_TABLES, "events"))
def test_committed_parent_writer_is_rechecked_after_reader_waits(
    audit_engine, tmp_path, monkeypatch, parent
):
    service, scope, session_hash, _, step, _ = private_recorded_workflow(
        audit_engine, tmp_path, monkeypatch
    )

    def read():
        with Session(audit_engine) as session, session.begin():
            return service.read_input_audit(
                session,
                scope,
                UUID(step["job_id"]),
                actor_session_hash=session_hash,
                at=service.clock(),
            )

    with ThreadPoolExecutor(max_workers=1) as worker, audit_engine.connect() as writer:
        transaction = writer.begin()
        writer.execute(
            text("UPDATE " + parent + " SET visibility='tenant',tenant_id='synthetic-revoked'")
        )
        reader = worker.submit(read)
        try:
            with pytest.raises(TimeoutError):
                reader.result(timeout=0.2)
        finally:
            transaction.commit()
        with pytest.raises(PermissionError):
            reader.result(timeout=5)


@pytest.mark.parametrize("authority", ["session", "user", "event", "workflow"])
def test_reader_retains_authority_locks_until_private_text_has_been_returned(
    audit_engine, tmp_path, monkeypatch, authority
):
    service, scope, session_hash, receipt, step, _ = private_recorded_workflow(
        audit_engine, tmp_path, monkeypatch
    )
    original = service._read_input_audit_record
    observed = []
    statements = {
        "session": "UPDATE auth_sessions SET revoked_at=now() WHERE session_hash=:id",
        "user": "UPDATE users SET role='viewer' WHERE user_id=:id",
        "event": "UPDATE events SET tenant_id='synthetic-revoked' WHERE event_id=:id",
        "workflow": "UPDATE enrichment_workflows SET actor_user_id=actor_user_id "
        "WHERE workflow_id=:id",
    }
    identities = {
        "session": session_hash,
        "user": scope.user_id,
        "event": str(receipt.workflow_id),
        "workflow": str(receipt.workflow_id),
    }
    with audit_engine.connect() as connection:
        identities["event"] = connection.scalar(
            text("SELECT event_id FROM enrichment_workflows WHERE workflow_id=:id"),
            {"id": str(receipt.workflow_id)},
        )

    def concurrent_writer(session, workflow, step_row):
        with pytest.raises(OperationalError), audit_engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout='200ms'"))
            connection.execute(text(statements[authority]), {"id": identities[authority]})
        observed.append("writer_blocked")
        return original(session, workflow, step_row)

    monkeypatch.setattr(service, "_read_input_audit_record", concurrent_writer)
    with Session(audit_engine) as session, session.begin():
        result = service.read_input_audit(
            session,
            scope,
            UUID(step["job_id"]),
            actor_session_hash=session_hash,
            at=service.clock(),
        )
    assert result.record.input_selections[0].texts and observed == ["writer_blocked"]


@pytest.mark.parametrize("parent", PARENT_TABLES)
def test_noncurrent_unlinked_history_keeps_current_nonnull_parent_acl(
    audit_engine, tmp_path, monkeypatch, parent
):
    service, scope, session_hash, _, step, calls = private_recorded_workflow(
        audit_engine, tmp_path, monkeypatch
    )
    with audit_engine.begin() as connection:
        for table in PARENT_TABLES:
            connection.execute(
                text("UPDATE " + table + " SET visibility='tenant',tenant_id=:tenant"),
                {"tenant": scope.tenant_id},
            )
        connection.execute(update(document_revisions).values(is_current=False))
        connection.execute(update(event_documents).values(active=False))
        assert (
            connection.scalar(
                select(document_revisions.c.revision_id).where(document_revisions.c.is_current)
            )
            is None
        )
        assert (
            connection.scalar(select(event_documents.c.revision_id).where(event_documents.c.active))
            is None
        )
    with Session(audit_engine) as session, session.begin():
        result = service.read_input_audit(
            session,
            scope,
            UUID(step["job_id"]),
            actor_session_hash=session_hash,
            at=service.clock(),
        )
    assert result.audit_state == "recorded" and result.record.input_selections[0].texts
    before = sum(len(group) for group in calls)
    with audit_engine.begin() as connection:
        connection.execute(text("UPDATE " + parent + " SET tenant_id='synthetic-revoked'"))
    with pytest.raises(PermissionError), Session(audit_engine) as session:
        service.read_input_audit(
            session,
            scope,
            UUID(step["job_id"]),
            actor_session_hash=session_hash,
            at=service.clock(),
        )
    assert sum(len(group) for group in calls) == before


@pytest.mark.parametrize("authority", ["session", "user"])
def test_committed_authority_revocation_never_returns_private_text(
    audit_engine, tmp_path, monkeypatch, authority
):
    service, scope, session_hash, _, step, _ = private_recorded_workflow(
        audit_engine, tmp_path, monkeypatch
    )
    with audit_engine.begin() as connection:
        if authority == "session":
            connection.execute(
                update(auth_sessions)
                .where(auth_sessions.c.session_hash == session_hash)
                .values(revoked_at=service.clock())
            )
        else:
            connection.execute(
                update(users).where(users.c.user_id == scope.user_id).values(role="viewer")
            )
    with pytest.raises(PermissionError), Session(audit_engine) as session:
        service.read_input_audit(
            session,
            scope,
            UUID(step["job_id"]),
            actor_session_hash=session_hash,
            at=service.clock(),
        )
