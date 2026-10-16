"""Real isolated PostgreSQL services with synthetic source facts, never external live evidence."""

import hashlib
import secrets
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, event, select, text, update
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema
from test_r10_evidence_graph_pg import VERSION, publish_event, publish_fact

from ai_intel.api.auth_state import auth_sessions
from ai_intel.api.authentication import Principal
from ai_intel.api.knowledge_read_service import sources
from ai_intel.domain.access import Role
from ai_intel.domain.values import VisibilityScope
from ai_intel.infrastructure.database import run_migrations
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.tool_contracts import ReadEvidenceArguments, ReadEvidenceCall
from ai_intel.investigation.tool_gateway import BudgetLimits, PostgresEvidenceReader, ToolGateway
from ai_intel.knowledge.models import document_revisions, documents, evidence, users
from ai_intel.knowledge.persistence_models import claims

pytestmark = pytest.mark.real_pg


@pytest.fixture()
def r14_engine(
    isolated_test_database_url: str,
    register_sensitive_failure_value: Callable[[SecretStr], None],
) -> Iterator[Engine]:
    register_sensitive_failure_value(SecretStr(isolated_test_database_url))
    url = make_url(isolated_test_database_url)
    if url.password:
        register_sensitive_failure_value(SecretStr(url.password))
    assert url.database == "test_dianzi_r14_tools_fix1_20261016"
    schema = "test_r14_tools_fix1_" + uuid4().hex
    base = create_engine(url, poolclass=NullPool, hide_parameters=True)
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=5000"}
    )
    run_migrations(isolated.render_as_string(hide_password=False))
    engine = create_engine(isolated, poolclass=NullPool, hide_parameters=True)
    try:
        yield engine
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


def seed_principal(
    engine: Engine,
    register_sensitive_failure_value: Callable[[SecretStr], None],
    *,
    tenant: str = "owner",
    role: Role = Role.ANALYST,
) -> tuple[Principal, str]:
    user_id = str(uuid4())
    token = secrets.token_urlsafe(32)
    register_sensitive_failure_value(SecretStr(token))
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            users.insert().values(
                user_id=user_id,
                username="fixture-r14-" + uuid4().hex,
                password_hash="fixture-unused-password-hash",
                tenant_id=tenant,
                role=role.value,
                created_at=now,
            )
        )
        connection.execute(
            auth_sessions.insert().values(
                session_hash=hashlib.sha256(token.encode()).hexdigest(),
                user_id=user_id,
                csrf_token="fixture-unused-csrf",
                issued_at=now,
                expires_at=now + timedelta(minutes=5),
            )
        )
    return Principal(user_id, tenant, role), token


def limits(seconds: float = 8) -> BudgetLimits:
    return BudgetLimits(
        max_calls=8,
        max_concurrent_calls=1,
        max_request_bytes=4096,
        max_total_input_bytes=32768,
        max_result_bytes=8192,
        max_total_output_bytes=65536,
        deadline_monotonic=time.monotonic() + seconds,
    )


def source_call(engine: Engine, path: Path, *, private: bool = False) -> tuple[bytes, str]:
    event_id = uuid4()
    visibility = VisibilityScope(visibility="tenant", tenant_id="owner") if private else None
    submission = publish_fact(engine, path, event_id, VERSION, scope=visibility)
    publish_event(engine, event_id, [submission], scope=visibility)
    span_id = submission.evidence_links[0].evidence_id.value
    call = ReadEvidenceCall(
        tool_name="read_evidence",
        goal_id=uuid4(),
        arguments=ReadEvidenceArguments(
            event_id=event_id,
            evidence_id=UUID(span_id),
            revision_id=UUID(submission.revision_id.value),
        ),
    )
    return call.model_dump_json().encode(), submission.record.claim_id.value


def test_real_pg_current_supported_read_uses_both_business_services(
    r14_engine,
    tmp_path,
    register_sensitive_failure_value,
) -> None:
    call, _ = source_call(r14_engine, tmp_path)
    principal, token = seed_principal(r14_engine, register_sensitive_failure_value)
    with r14_engine.connect() as connection:
        subject = ToolGateway(
            principal,
            uuid4(),
            limits(),
            evidence_reader=PostgresEvidenceReader(connection, token, "fixture"),
        )
        result = subject.execute(AgentRole.QA, call)
        assert result.status == "succeeded" and result.data is not None and result.is_synthetic
        assert result.evidence_ids and result.observed_at == result.data.first_observed_at
        assert result.observed_at is None
        assert not connection.in_transaction()


def test_real_pg_private_read_is_only_available_to_asset_role(
    r14_engine,
    tmp_path,
    register_sensitive_failure_value,
) -> None:
    call, _ = source_call(r14_engine, tmp_path, private=True)
    principal, token = seed_principal(r14_engine, register_sensitive_failure_value)
    with r14_engine.connect() as connection:
        subject = ToolGateway(
            principal,
            uuid4(),
            limits(),
            evidence_reader=PostgresEvidenceReader(connection, token, "fixture"),
        )
        assert subject.execute(AgentRole.ASSESSOR, call).status == "succeeded"
        result = subject.execute(AgentRole.QA, call)
        assert result.status == "denied" and result.data is None and result.evidence_ids == ()


@pytest.mark.parametrize("tenant,role", [("other", Role.ANALYST), ("owner", Role.VIEWER)])
def test_real_pg_cross_tenant_and_missing_permission_never_return_private_fields(
    r14_engine,
    tmp_path,
    register_sensitive_failure_value,
    tenant,
    role,
) -> None:
    call, _ = source_call(r14_engine, tmp_path, private=True)
    principal, token = seed_principal(
        r14_engine, register_sensitive_failure_value, tenant=tenant, role=role
    )
    with r14_engine.connect() as connection:
        subject = ToolGateway(
            principal,
            uuid4(),
            limits(),
            evidence_reader=PostgresEvidenceReader(connection, token, "fixture"),
        )
        result = subject.execute(AgentRole.ASSESSOR, call)
        assert result.status == "denied" and result.data is None and result.evidence_ids == ()
        assert "fixture-package" not in result.model_dump_json()


@pytest.mark.parametrize("partial", [False, True])
def test_real_pg_success_or_partial_replay_rechecks_current_authentication(
    r14_engine,
    tmp_path,
    register_sensitive_failure_value,
    partial,
) -> None:
    call, claim_id = source_call(r14_engine, tmp_path, private=True)
    if partial:
        with r14_engine.begin() as connection:
            connection.execute(
                update(claims).where(claims.c.claim_id == claim_id).values(is_current=False)
            )
    principal, token = seed_principal(r14_engine, register_sensitive_failure_value)
    with r14_engine.connect() as connection:
        subject = ToolGateway(
            principal,
            uuid4(),
            limits(),
            evidence_reader=PostgresEvidenceReader(connection, token, "fixture"),
        )
        first = subject.execute(AgentRole.ASSESSOR, call)
        assert first.status == ("partial" if partial else "succeeded")
        assert first.data is not None
        with r14_engine.begin() as writer:
            writer.execute(
                update(users).where(users.c.user_id == principal.user_id).values(role="viewer")
            )
        result = subject.execute(AgentRole.ASSESSOR, call)
        assert result.status == "denied" and result.data is None and result.evidence_ids == ()


def test_real_pg_revision_withdrawal_yields_historical_partial_and_not_a_current_fact(
    r14_engine,
    tmp_path,
    register_sensitive_failure_value,
) -> None:
    call, _ = source_call(r14_engine, tmp_path)
    principal, token = seed_principal(r14_engine, register_sensitive_failure_value)
    with r14_engine.connect() as connection:
        subject = ToolGateway(
            principal,
            uuid4(),
            limits(),
            evidence_reader=PostgresEvidenceReader(connection, token, "fixture"),
        )
        assert subject.execute(AgentRole.QA, call).status == "succeeded"
        revision_id = str(ReadEvidenceCall.model_validate_json(call).arguments.revision_id)
        with r14_engine.begin() as writer:
            writer.execute(
                update(document_revisions)
                .where(document_revisions.c.revision_id == revision_id)
                .values(is_current=False)
            )
        result = subject.execute(AgentRole.QA, call)
        assert result.status == "partial" and result.data is not None
        assert result.error_code == "evidence_not_current_supported"


def test_real_pg_corrupt_evidence_hash_is_failed_and_failure_is_not_retried(
    r14_engine,
    tmp_path,
    register_sensitive_failure_value,
) -> None:
    call, _ = source_call(r14_engine, tmp_path)
    span_id = str(ReadEvidenceCall.model_validate_json(call).arguments.evidence_id)
    with r14_engine.begin() as writer:
        writer.execute(
            update(evidence).where(evidence.c.evidence_id == span_id).values(quote_sha256="0" * 64)
        )
    principal, token = seed_principal(r14_engine, register_sensitive_failure_value)
    with r14_engine.connect() as connection:
        subject = ToolGateway(
            principal,
            uuid4(),
            limits(),
            evidence_reader=PostgresEvidenceReader(connection, token, "fixture"),
        )
        first = subject.execute(AgentRole.QA, call)
        assert first.status == "failed" and first.error_code == "tool_output_invalid"
        replay = subject.execute(AgentRole.CRITIC, call)
        assert replay.status == "failed" and replay.usage.cached and replay.usage.service_calls == 0


def test_real_pg_wrong_revision_is_failed_without_returning_the_other_revision(
    r14_engine,
    tmp_path,
    register_sensitive_failure_value,
) -> None:
    original, _ = source_call(r14_engine, tmp_path)
    parsed = ReadEvidenceCall.model_validate_json(original)
    changed = parsed.model_copy(
        update={"arguments": parsed.arguments.model_copy(update={"revision_id": uuid4()})}
    )
    principal, token = seed_principal(r14_engine, register_sensitive_failure_value)
    with r14_engine.connect() as connection:
        subject = ToolGateway(
            principal,
            uuid4(),
            limits(),
            evidence_reader=PostgresEvidenceReader(connection, token, "fixture"),
        )
        result = subject.execute(AgentRole.QA, changed.model_dump_json().encode())
        assert result.status == "failed" and result.data is None and result.evidence_ids == ()


def test_real_pg_revoked_session_never_serves_evidence(
    r14_engine,
    tmp_path,
    register_sensitive_failure_value,
) -> None:
    call, _ = source_call(r14_engine, tmp_path)
    principal, token = seed_principal(r14_engine, register_sensitive_failure_value)
    with r14_engine.begin() as writer:
        writer.execute(
            update(auth_sessions)
            .where(auth_sessions.c.user_id == principal.user_id)
            .values(revoked_at=datetime.now(UTC))
        )
    with r14_engine.connect() as connection:
        subject = ToolGateway(
            principal,
            uuid4(),
            limits(),
            evidence_reader=PostgresEvidenceReader(connection, token, "fixture"),
        )
        result = subject.execute(AgentRole.QA, call)
        assert result.status == "denied" and result.data is None


def test_real_pg_active_transaction_is_not_silently_reused(
    r14_engine,
    tmp_path,
    register_sensitive_failure_value,
) -> None:
    call, _ = source_call(r14_engine, tmp_path)
    principal, token = seed_principal(r14_engine, register_sensitive_failure_value)
    with r14_engine.connect() as connection, connection.begin():
        subject = ToolGateway(
            principal,
            uuid4(),
            limits(),
            evidence_reader=PostgresEvidenceReader(connection, token, "fixture"),
        )
        result = subject.execute(AgentRole.QA, call)
        assert result.status == "not_configured" and result.data is None


def test_real_pg_lock_wait_is_interrupted_by_remaining_deadline(
    r14_engine,
    tmp_path,
    register_sensitive_failure_value,
) -> None:
    call, _ = source_call(r14_engine, tmp_path)
    principal, token = seed_principal(r14_engine, register_sensitive_failure_value)
    with r14_engine.connect() as holder, holder.begin(), r14_engine.connect() as connection:
        holder.execute(
            select(users.c.user_id).where(users.c.user_id == principal.user_id).with_for_update()
        ).all()
        subject = ToolGateway(
            principal,
            uuid4(),
            limits(0.15),
            evidence_reader=PostgresEvidenceReader(connection, token, "fixture"),
        )
        started = time.monotonic()
        result = subject.execute(AgentRole.QA, call)
        elapsed = time.monotonic() - started
        assert result.status == "budget_exhausted" and result.error_code == "deadline_exhausted"
        assert elapsed < 0.7 and result.data is None and not connection.in_transaction()


@pytest.mark.parametrize("parent", ["source", "document"])
@pytest.mark.parametrize("timing", ["before_fence", "after_fence"])
def test_real_pg_historical_parent_acl_is_rechecked_and_locked(
    r14_engine,
    tmp_path,
    register_sensitive_failure_value,
    parent,
    timing,
) -> None:
    call, claim_id = source_call(r14_engine, tmp_path, private=True)
    parsed = ReadEvidenceCall.model_validate_json(call)
    with r14_engine.begin() as writer:
        writer.execute(update(claims).where(claims.c.claim_id == claim_id).values(is_current=False))
        row = writer.execute(
            select(documents.c.document_id, documents.c.source_id)
            .select_from(document_revisions.join(documents))
            .where(document_revisions.c.revision_id == str(parsed.arguments.revision_id))
        ).one()
    relation, predicate = (
        (sources, sources.c.source_id == row.source_id)
        if parent == "source"
        else (documents, documents.c.document_id == row.document_id)
    )
    principal, token = seed_principal(r14_engine, register_sensitive_failure_value)
    metadata_reads = 0
    evidence_reads = 0
    outcomes: list[str] = []

    def mutate_parent(connection, cursor, statement, parameters, context, executemany):
        nonlocal metadata_reads, evidence_reads
        metadata_query = statement.startswith("SELECT documents.source_id, documents.document_id,")
        evidence_query = statement.startswith("SELECT evidence.evidence_id,")
        if metadata_query:
            metadata_reads += 1
        if evidence_query:
            evidence_reads += 1
        before_fence = timing == "before_fence" and evidence_query and evidence_reads == 1
        after_fence = timing == "after_fence" and metadata_query and metadata_reads == 2
        if not before_fence and not after_fence:
            return
        try:
            with r14_engine.begin() as writer:
                writer.execute(text("SET LOCAL lock_timeout = '100ms'"))
                writer.execute(
                    update(relation).where(predicate).values(visibility="tenant", tenant_id="other")
                )
                outcomes.append("changed")
        except DBAPIError as blocked:
            outcomes.append(str(getattr(blocked.orig, "sqlstate", None)))

    with r14_engine.connect() as connection:
        event.listen(connection, "after_cursor_execute", mutate_parent)
        try:
            subject = ToolGateway(
                principal,
                uuid4(),
                limits(),
                evidence_reader=PostgresEvidenceReader(connection, token, "fixture"),
            )
            result = subject.execute(AgentRole.ASSESSOR, call)
        finally:
            event.remove(connection, "after_cursor_execute", mutate_parent)
    assert evidence_reads >= 1 and metadata_reads == 2
    if timing == "before_fence":
        assert outcomes == ["changed"] and result.status == "denied"
        assert result.data is None and result.evidence_ids == ()
        assert "fixture-package" not in result.model_dump_json()
    else:
        assert outcomes == ["55P03"] and result.status == "partial"
        assert result.data is not None and result.error_code == "evidence_not_current_supported"
