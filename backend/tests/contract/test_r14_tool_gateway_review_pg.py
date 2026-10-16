"""Reviewer real-PG negatives pass through actual auth, graph and knowledge services."""

import time
from uuid import uuid4

import pytest
from sqlalchemy import event, select, text, update
from test_r14_tool_gateway_pg import limits, seed_principal, source_call
from test_r14_tool_gateway_pg import r14_engine as r14_engine

from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.tool_contracts import ReadEvidenceCall
from ai_intel.investigation.tool_gateway import PostgresEvidenceReader, ToolGateway
from ai_intel.knowledge.models import document_revisions, documents
from ai_intel.knowledge.persistence_models import claims

pytestmark = pytest.mark.real_pg


def test_review_real_pg_fresh_claim_change_before_fence_never_emits_stale_success(
    r14_engine, tmp_path, register_sensitive_failure_value
) -> None:
    call, claim_id = source_call(r14_engine, tmp_path)
    principal, token = seed_principal(r14_engine, register_sensitive_failure_value)
    changed = False

    def change_after_evidence_read(connection, cursor, statement, parameters, context, executemany):
        nonlocal changed
        if not changed and statement.startswith("SELECT evidence.evidence_id,"):
            changed = True
            with r14_engine.begin() as writer:
                writer.execute(
                    update(claims).where(claims.c.claim_id == claim_id).values(is_current=False)
                )

    with r14_engine.connect() as connection:
        event.listen(connection, "after_cursor_execute", change_after_evidence_read)
        try:
            subject = ToolGateway(
                principal,
                uuid4(),
                limits(),
                evidence_reader=PostgresEvidenceReader(connection, token, "fixture"),
            )
            result = subject.execute(AgentRole.QA, call)
        finally:
            event.remove(connection, "after_cursor_execute", change_after_evidence_read)
        assert not connection.in_transaction()
    assert changed and result.status == "partial" and result.error_code == "graph_snapshot_changed"
    assert result.data is None and result.evidence_ids == ()


def test_review_real_pg_replay_denied_after_parent_acl_change_and_public_role_downgrade(
    r14_engine, tmp_path, register_sensitive_failure_value
) -> None:
    call, _ = source_call(r14_engine, tmp_path, private=True)
    principal, token = seed_principal(r14_engine, register_sensitive_failure_value)
    parsed = ReadEvidenceCall.model_validate_json(call)
    with r14_engine.connect() as connection:
        subject = ToolGateway(
            principal,
            uuid4(),
            limits(),
            evidence_reader=PostgresEvidenceReader(connection, token, "fixture"),
        )
        assert subject.execute(AgentRole.ASSESSOR, call).status == "succeeded"
        public = subject.execute(AgentRole.CRITIC, call)
        assert public.status == "denied" and public.data is None and public.evidence_ids == ()
        with r14_engine.begin() as writer:
            writer.execute(
                update(document_revisions)
                .where(document_revisions.c.revision_id == str(parsed.arguments.revision_id))
                .values(visibility="tenant", tenant_id="other")
            )
        replay = subject.execute(AgentRole.ASSESSOR, call)
        assert replay.status == "denied" and replay.data is None and not replay.usage.cached
        assert "fixture-package" not in replay.model_dump_json()


def test_review_real_pg_unknown_parent_identity_is_not_treated_as_authorized_evidence(
    r14_engine, tmp_path, register_sensitive_failure_value
) -> None:
    call, claim_id = source_call(r14_engine, tmp_path)
    parsed = ReadEvidenceCall.model_validate_json(call)
    with r14_engine.begin() as writer:
        writer.execute(update(claims).where(claims.c.claim_id == claim_id).values(is_current=False))
        source_id = writer.scalar(
            select(documents.c.source_id)
            .select_from(document_revisions.join(documents))
            .where(document_revisions.c.revision_id == str(parsed.arguments.revision_id))
        )
        row = (
            writer.execute(
                text("SELECT * FROM sources WHERE source_id=:source_id"), {"source_id": source_id}
            )
            .mappings()
            .one()
        )
        copied = dict(row)
        copied["source_id"] = "review-invalid-parent"
        copied["name"] = "review-invalid-parent"
        columns = ", ".join(copied)
        parameters = ", ".join(":" + key for key in copied)
        writer.execute(
            text("INSERT INTO sources (" + columns + ") VALUES (" + parameters + ")"), copied
        )
        writer.execute(
            update(documents)
            .where(documents.c.source_id == source_id)
            .values(source_id="review-invalid-parent")
        )
    principal, token = seed_principal(r14_engine, register_sensitive_failure_value)
    with r14_engine.connect() as connection:
        subject = ToolGateway(
            principal,
            uuid4(),
            limits(),
            evidence_reader=PostgresEvidenceReader(connection, token, "fixture"),
        )
        result = subject.execute(AgentRole.QA, call)
        assert result.status == "failed" and result.error_code == "tool_output_invalid"
        assert result.data is None and result.evidence_ids == ()
        assert not connection.in_transaction()


def test_review_real_pg_query_time_is_bounded_not_only_lock_time(
    r14_engine, tmp_path, register_sensitive_failure_value
) -> None:
    call, _ = source_call(r14_engine, tmp_path)
    principal, token = seed_principal(r14_engine, register_sensitive_failure_value)
    injected = False

    def slow_auth_query(connection, cursor, statement, parameters, context, executemany):
        nonlocal injected
        if not injected and statement.startswith("SELECT auth_sessions.user_id,"):
            injected = True
            return "SELECT pg_sleep(1)", ()
        return statement, parameters

    with r14_engine.connect() as connection:
        reader = PostgresEvidenceReader(connection, token, "fixture")
        subject = ToolGateway(principal, uuid4(), limits(0.15), evidence_reader=reader)
        event.listen(connection, "before_cursor_execute", slow_auth_query, retval=True)
        try:
            started = time.monotonic()
            result = subject.execute(AgentRole.QA, call)
            elapsed = time.monotonic() - started
        finally:
            event.remove(connection, "before_cursor_execute", slow_auth_query)
        assert (
            injected
            and result.status == "budget_exhausted"
            and result.error_code == "deadline_exhausted"
        )
        assert elapsed < 0.7 and result.data is None and not connection.in_transaction()
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0022_sbom_sidecars"
        )
