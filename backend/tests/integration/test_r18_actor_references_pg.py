"""Owned real PG actor/job fences; synthetic owner table models the server PG reader port."""

from __future__ import annotations

import hashlib
import multiprocessing
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from multiprocessing.connection import Connection as ProcessPipe
from threading import Event
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import Column, MetaData, Table, Text, create_engine, insert, select, text, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.pool import NullPool
from test_r18_api_key_credentials_pg import NOW, PgCase
from test_r18_api_key_credentials_pg import owned_database as owned_database
from test_r18_api_key_credentials_pg import pg_case as pg_case

from ai_intel.api.actor_references import (
    ActorJobOwner,
    ActorReference,
    InvalidActorReferenceError,
    actor_reference_from_payload,
    actor_reference_payload,
    create_actor_reference,
    lock_actor_job_scope,
    lock_actor_reference_scope,
)
from ai_intel.api.auth_state import auth_sessions, lock_authenticated_scope
from ai_intel.api.authentication import SessionExpiredError
from ai_intel.api.credential_models import api_keys
from ai_intel.api.credentials import ApiKeyCredential
from ai_intel.domain.access import AccessScope, Role
from ai_intel.knowledge.models import job_runs, metadata, users

pytestmark = pytest.mark.real_pg
owner_rows = Table(
    "synthetic_actor_job_owners",
    MetaData(),
    Column("job_id", Text, primary_key=True),
    Column("user_id", Text, nullable=False),
    Column("tenant_id", Text),
    Column("authorized_role", Text, nullable=False),
    Column("actor_reference", JSONB, nullable=False),
)


class PgOwnerPort:
    def lock_actor_job_owner(self, connection: Connection, job_id: str) -> ActorJobOwner | None:
        row = (
            connection.execute(
                select(owner_rows).where(owner_rows.c.job_id == job_id).with_for_update()
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return ActorJobOwner(
            row["user_id"], row["tenant_id"], Role(row["authorized_role"]), row["actor_reference"]
        )


@dataclass(frozen=True)
class JobCase:
    engine: Engine
    job_id: str
    reference: ActorReference


@pytest.fixture
def job_case(pg_case: PgCase) -> Iterator[JobCase]:
    job_id = str(uuid4())
    with pg_case.engine.begin() as connection:
        metadata.create_all(connection, tables=[job_runs])
        owner_rows.create(connection)
        reference = create_actor_reference(connection, pg_case.session, NOW)
        connection.execute(
            insert(job_runs).values(
                job_id=job_id,
                tenant_id=reference.tenant_id,
                job_type="synthetic_actor_resume",
                status="queued",
                payload_ref="pg:job:" + job_id,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        connection.execute(
            insert(owner_rows).values(
                job_id=job_id,
                user_id=reference.user_id,
                tenant_id=reference.tenant_id,
                authorized_role=reference.role.value,
                actor_reference=actor_reference_payload(reference),
            )
        )
    yield JobCase(pg_case.engine, job_id, reference)


def test_two_tenants_two_users_pg_json_roundtrip_denies_other_owner(
    pg_case: PgCase,
    job_case: JobCase,
) -> None:
    with job_case.engine.begin() as connection:
        stored = connection.scalar(select(owner_rows.c.actor_reference))
        restored = actor_reference_from_payload(stored)
        current = lock_actor_job_scope(
            connection, restored, NOW, job_id=job_case.job_id, owner_port=PgOwnerPort()
        )
        other = create_actor_reference(connection, pg_case.other_session, NOW)
        assert other.user_id != current.user_id and other.tenant_id != current.tenant_id
        assert lock_authenticated_scope(connection, restored, NOW) == current
    with job_case.engine.begin() as connection, pytest.raises(InvalidActorReferenceError):
        lock_actor_job_scope(
            connection, other, NOW, job_id=job_case.job_id, owner_port=PgOwnerPort()
        )


def _resume_worker(pipe: ProcessPipe) -> None:
    database_url, schema, job_id = pipe.recv()
    if not isinstance(database_url, SecretStr):
        pipe.send(("failure", "invalid test resource"))
        return
    engine = create_engine(
        database_url.get_secret_value(),
        hide_parameters=True,
        poolclass=NullPool,
        connect_args={"connect_timeout": 5, "options": "-c statement_timeout=8000"},
        execution_options={"schema_translate_map": {None: schema}},
    )
    try:
        with engine.begin() as connection:
            stored = connection.scalar(
                select(owner_rows.c.actor_reference).where(owner_rows.c.job_id == job_id)
            )
            reference = actor_reference_from_payload(stored)
            scope = lock_actor_job_scope(
                connection, reference, NOW, job_id=job_id, owner_port=PgOwnerPort()
            )
            pipe.send(("allowed", scope.user_id, scope.tenant_id))
    except InvalidActorReferenceError:
        pipe.send(("denied",))
    except Exception as failure:
        pipe.send(("failure", type(failure).__name__))
    finally:
        engine.dispose()
        pipe.close()


def _resume_in_fresh_process(pg_case: PgCase, job_case: JobCase) -> tuple[str, ...]:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=_resume_worker, args=(child,))
    try:
        process.start()
        child.close()
        parent.send((pg_case.database_url, pg_case.schema, job_case.job_id))
        assert parent.poll(15), "fresh worker did not return bounded authorization result"
        result = parent.recv()
        process.join(timeout=5)
        assert process.exitcode == 0
        return result
    finally:
        parent.close()
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)


def test_distinct_worker_process_restores_pg_actor_and_rejects_later_revocation(
    pg_case: PgCase,
    job_case: JobCase,
) -> None:
    assert _resume_in_fresh_process(pg_case, job_case) == (
        "allowed",
        job_case.reference.user_id,
        job_case.reference.tenant_id,
    )
    with job_case.engine.begin() as connection:
        connection.execute(
            update(auth_sessions)
            .where(auth_sessions.c.session_hash == job_case.reference.session_hash)
            .values(revoked_at=NOW)
        )
    assert _resume_in_fresh_process(pg_case, job_case) == ("denied",)


def test_real_owner_role_changed_while_waiting_is_denied(job_case: JobCase) -> None:
    reader_pid: list[int] = []

    def authenticate() -> AccessScope:
        with job_case.engine.begin() as connection:
            reader_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
            return lock_actor_job_scope(
                connection,
                job_case.reference,
                NOW,
                job_id=job_case.job_id,
                owner_port=PgOwnerPort(),
            )

    with job_case.engine.begin() as holding, ThreadPoolExecutor(max_workers=1) as executor:
        holding.execute(
            update(users).where(users.c.user_id == job_case.reference.user_id).values(role="viewer")
        )
        future = executor.submit(authenticate)
        _wait_for_pg_lock(holding, reader_pid)
        holding.commit()
        with pytest.raises(InvalidActorReferenceError):
            future.result(timeout=6)


@pytest.mark.parametrize("change", ["revoke", "expire", "role", "tenant"])
def test_queued_job_resume_rechecks_committed_session_changes(
    job_case: JobCase, change: str
) -> None:
    with job_case.engine.begin() as connection:
        if change in {"revoke", "expire"}:
            values = {"revoked_at": NOW} if change == "revoke" else {"expires_at": NOW}
            connection.execute(
                update(auth_sessions)
                .where(auth_sessions.c.session_hash == job_case.reference.session_hash)
                .values(**values)
            )
        else:
            values = {"role": "viewer"} if change == "role" else {"tenant_id": "synthetic-changed"}
            connection.execute(
                update(users).where(users.c.user_id == job_case.reference.user_id).values(**values)
            )
    with job_case.engine.begin() as connection, pytest.raises(InvalidActorReferenceError):
        lock_actor_job_scope(
            connection, job_case.reference, NOW, job_id=job_case.job_id, owner_port=PgOwnerPort()
        )


@pytest.mark.parametrize("change", ["revoke", "expire", "version", "role", "scopes"])
def test_key_resume_rechecks_current_key_and_user(pg_case: PgCase, change: str) -> None:
    issued = pg_case.issue()
    with pg_case.engine.begin() as connection:
        reference = create_actor_reference(connection, ApiKeyCredential(issued.token), NOW)
    with pg_case.engine.begin() as connection:
        if change == "role":
            connection.execute(
                update(users).where(users.c.user_id == reference.user_id).values(role="viewer")
            )
        else:
            values = {"revoked_at": NOW}
            if change == "expire":
                values = {"expires_at": NOW + timedelta(microseconds=1)}
            elif change == "version":
                values = {"version": reference.credential_version + 1}
            elif change == "scopes":
                values = {"scopes": ["read:public"]}
            connection.execute(
                update(api_keys).where(api_keys.c.key_id == reference.key_id).values(**values)
            )
    with pg_case.engine.begin() as connection, pytest.raises(InvalidActorReferenceError):
        lock_actor_reference_scope(connection, reference, NOW + timedelta(seconds=1))


@pytest.mark.parametrize("change", ["owner", "tenant", "job_tenant", "stored_reference"])
def test_mismatched_pg_owner_job_or_reference_denied(job_case: JobCase, change: str) -> None:
    with job_case.engine.begin() as connection:
        if change == "job_tenant":
            connection.execute(
                update(job_runs)
                .where(job_runs.c.job_id == job_case.job_id)
                .values(tenant_id="synthetic-other-tenant")
            )
        else:
            values: dict[str, object] = {"user_id": "synthetic-other-owner"}
            if change == "tenant":
                values = {"tenant_id": "synthetic-other-tenant"}
            elif change == "stored_reference":
                payload = actor_reference_payload(job_case.reference)
                payload["session_hash"] = "a" * 64
                values = {"actor_reference": payload}
            connection.execute(
                update(owner_rows).where(owner_rows.c.job_id == job_case.job_id).values(**values)
            )
    with job_case.engine.begin() as connection, pytest.raises(InvalidActorReferenceError):
        lock_actor_job_scope(
            connection, job_case.reference, NOW, job_id=job_case.job_id, owner_port=PgOwnerPort()
        )


def _wait_for_pg_lock(holding: Connection, reader_pid: list[int]) -> None:
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        holding.execute(text("SELECT pg_stat_clear_snapshot()"))
        if (
            reader_pid
            and holding.scalar(
                text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"),
                {"pid": reader_pid[0]},
            )
            == "Lock"
        ):
            return
        time.sleep(0.01)
    raise AssertionError("reader did not reach a real PG lock wait")


@pytest.mark.parametrize("target", ["user", "job", "owner"])
def test_real_lock_wait_expiring_reference_is_denied(job_case: JobCase, target: str) -> None:
    reader_pid: list[int] = []
    expires_at = datetime.now(UTC) + timedelta(seconds=1)
    with job_case.engine.begin() as connection:
        connection.execute(
            update(auth_sessions)
            .where(auth_sessions.c.session_hash == job_case.reference.session_hash)
            .values(expires_at=expires_at)
        )

    def authenticate() -> AccessScope:
        with job_case.engine.begin() as connection:
            reader_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
            return lock_actor_job_scope(
                connection,
                job_case.reference,
                datetime.now(UTC),
                job_id=job_case.job_id,
                owner_port=PgOwnerPort(),
            )

    table = users if target == "user" else job_runs if target == "job" else owner_rows
    predicate = (
        users.c.user_id == job_case.reference.user_id
        if target == "user"
        else (table.c.job_id == job_case.job_id)
    )
    with job_case.engine.begin() as holding, ThreadPoolExecutor(max_workers=1) as executor:
        holding.execute(select(table).where(predicate).with_for_update())
        future = executor.submit(authenticate)
        _wait_for_pg_lock(holding, reader_pid)
        remaining = (expires_at - datetime.now(UTC)).total_seconds() + 0.05
        if remaining > 0:
            Event().wait(remaining)
        holding.commit()
        with pytest.raises(InvalidActorReferenceError):
            future.result(timeout=6)


def test_real_cookie_user_lock_wait_expiry_is_rejected(pg_case: PgCase) -> None:
    reader_pid: list[int] = []
    expires_at = datetime.now(UTC) + timedelta(seconds=1)
    session_hash = hashlib.sha256(pg_case.session.token.get_secret_value().encode()).hexdigest()
    with pg_case.engine.begin() as connection:
        connection.execute(
            update(auth_sessions)
            .where(auth_sessions.c.session_hash == session_hash)
            .values(expires_at=expires_at)
        )

    def authenticate() -> AccessScope:
        with pg_case.engine.begin() as connection:
            reader_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
            return lock_authenticated_scope(
                connection, pg_case.session.token.get_secret_value(), datetime.now(UTC)
            )

    with pg_case.engine.begin() as holding, ThreadPoolExecutor(max_workers=1) as executor:
        user_id = holding.scalar(
            select(auth_sessions.c.user_id).where(auth_sessions.c.session_hash == session_hash)
        )
        holding.execute(select(users).where(users.c.user_id == user_id).with_for_update())
        future = executor.submit(authenticate)
        _wait_for_pg_lock(holding, reader_pid)
        remaining = (expires_at - datetime.now(UTC)).total_seconds() + 0.05
        if remaining > 0:
            Event().wait(remaining)
        holding.commit()
        with pytest.raises(SessionExpiredError):
            future.result(timeout=6)
