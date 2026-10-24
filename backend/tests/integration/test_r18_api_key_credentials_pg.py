"""Synthetic users in owned PG tables; this is not API or production migration acceptance."""

from __future__ import annotations

import hashlib
import multiprocessing
import secrets
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from multiprocessing.connection import Connection as ProcessPipe
from typing import Literal
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, event, func, insert, select, text, update
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool

from ai_intel.api.auth_state import auth_sessions
from ai_intel.api.authentication import SessionExpiredError
from ai_intel.api.credential_models import api_key_rate_buckets, api_keys
from ai_intel.api.credentials import (
    ApiKeyCredential,
    ApiKeyNotFoundError,
    ApiKeyRateLimitedError,
    InvalidApiKeyError,
    IssuedApiKey,
    PgApiKeyService,
    SessionCredential,
    consume_api_key_rate_limit,
    lock_authenticated_principal,
)
from ai_intel.domain.access import AccessScope, CrossTenantAccessError, PermissionDeniedError
from ai_intel.knowledge.models import metadata, users

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 16, 1, 0, 12, tzinfo=UTC)


@dataclass(frozen=True)
class PgCase:
    engine: Engine
    schema: str
    database_url: SecretStr
    session: SessionCredential
    other_session: SessionCredential
    admin_session: SessionCredential
    service: PgApiKeyService

    def issue(
        self, scopes: frozenset[str] = frozenset({"read:public", "read:asset"})
    ) -> IssuedApiKey:
        return self.service.issue_key(self.session, scopes)


@dataclass(frozen=True)
class ProcessInput:
    database_url: SecretStr
    schema: str
    now: datetime
    credential: ApiKeyCredential | SessionCredential
    operation: Literal["read", "ask"] = "read"
    attempts: int = 1
    key_id: str = ""
    action: str = ""


@pytest.fixture
def owned_database(
    isolated_test_database_url: str,
    register_sensitive_failure_value: Callable[[SecretStr], None],
) -> Iterator[tuple[SecretStr, str]]:
    """Own only a fresh schema in the caller's validated test database; never migrate it."""
    original = make_url(isolated_test_database_url).set(drivername="postgresql+psycopg")
    database_url = SecretStr(original.render_as_string(hide_password=False))
    register_sensitive_failure_value(database_url)
    if original.password:
        register_sensitive_failure_value(SecretStr(original.password))
    schema = "r18c_" + uuid4().hex
    engine = create_engine(
        database_url.get_secret_value(),
        hide_parameters=True,
        poolclass=NullPool,
        connect_args={
            "connect_timeout": 5,
            "options": "-c statement_timeout=12000 -c lock_timeout=8000",
        },
    )
    schema_created = False
    try:
        with engine.begin() as connection:
            database_name, username = connection.execute(
                text("SELECT current_database(), current_user")
            ).one()
            if database_name != original.database or username != original.username:
                raise RuntimeError("isolated PostgreSQL resource identity rejected")
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            metadata.create_all(
                connection.execution_options(schema_translate_map={None: schema}),
                tables=[users, auth_sessions, api_keys, api_key_rate_buckets],
            )
        schema_created = True
        yield database_url, schema
    finally:
        try:
            if schema_created:
                with engine.begin() as connection:
                    connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        finally:
            engine.dispose()


@pytest.fixture
def pg_case(
    owned_database: tuple[SecretStr, str],
    register_sensitive_failure_value: Callable[[SecretStr], None],
) -> Iterator[PgCase]:
    database_url, schema = owned_database
    register_sensitive_failure_value(database_url)
    password = make_url(database_url.get_secret_value()).password
    if password:
        register_sensitive_failure_value(SecretStr(password))
    engine = create_engine(
        database_url.get_secret_value(),
        hide_parameters=True,
        poolclass=NullPool,
        connect_args={
            "connect_timeout": 5,
            "options": "-c statement_timeout=12000 -c lock_timeout=8000",
        },
        execution_options={"schema_translate_map": {None: schema}},
    )
    marker = secrets.token_hex(6)
    credentials = tuple(SessionCredential(SecretStr(secrets.token_urlsafe(32))) for _ in range(3))
    for credential in credentials:
        register_sensitive_failure_value(credential.token)
    try:
        with engine.begin() as connection:
            for index, credential in enumerate(credentials):
                connection.execute(
                    insert(users).values(
                        user_id=f"user-{marker}-{index}",
                        username=f"test-user-{marker}-{index}",
                        password_hash="synthetic-not-for-login",
                        tenant_id=None if index == 2 else f"tenant-{marker}-{index}",
                        role="system_admin" if index == 2 else "analyst",
                        created_at=NOW,
                    )
                )
                connection.execute(
                    insert(auth_sessions).values(
                        session_hash=hashlib.sha256(
                            credential.token.get_secret_value().encode()
                        ).hexdigest(),
                        user_id=f"user-{marker}-{index}",
                        csrf_token="synthetic-not-for-http",
                        issued_at=NOW,
                        expires_at=datetime.now(UTC) + timedelta(days=1),
                        revoked_at=None,
                    )
                )
        yield PgCase(
            engine,
            schema,
            database_url,
            credentials[0],
            credentials[1],
            credentials[2],
            PgApiKeyService(engine, lambda: NOW),
        )
    finally:
        engine.dispose()


def _child_engine(payload: ProcessInput) -> Engine:
    return create_engine(
        payload.database_url.get_secret_value(),
        hide_parameters=True,
        poolclass=NullPool,
        connect_args={
            "connect_timeout": 5,
            "options": "-c statement_timeout=12000 -c lock_timeout=8000",
        },
        execution_options={"schema_translate_map": {None: payload.schema}},
    )


def _rate_worker(pipe: ProcessPipe) -> None:
    payload = pipe.recv()
    assert isinstance(payload, ProcessInput)
    assert isinstance(payload.credential, ApiKeyCredential)
    engine = _child_engine(payload)
    try:
        pipe.send("ready")
        assert pipe.recv() == "go"
        accepted = limited = 0
        for _ in range(payload.attempts):
            try:
                with engine.begin() as connection:
                    consume_api_key_rate_limit(
                        connection, payload.credential, payload.now, operation=payload.operation
                    )
                accepted += 1
            except ApiKeyRateLimitedError:
                limited += 1
        pipe.send((accepted, limited))
    finally:
        engine.dispose()
        pipe.close()


def _mutation_worker(pipe: ProcessPipe) -> None:
    payload = pipe.recv()
    assert isinstance(payload, ProcessInput)
    engine = _child_engine(payload)
    try:
        if payload.action == "revoke_service":
            assert isinstance(payload.credential, SessionCredential)

            def report_started(connection: Connection) -> None:
                """Report the service's actual connection, leaving its transaction unstarted."""
                pid = connection.scalar(text("SELECT pg_backend_pid()"))
                connection.rollback()
                pipe.send(("started", pid))

            event.listen(engine, "engine_connect", report_started, once=True)
            PgApiKeyService(engine, lambda: payload.now).revoke_key(
                payload.credential, payload.key_id
            )
            pipe.send("committed")
            return
        with engine.begin() as connection:
            pid = connection.scalar(text("SELECT pg_backend_pid()"))
            pipe.send(("started", pid))
            if payload.action == "revoke_hold":
                connection.execute(
                    update(api_keys)
                    .where(api_keys.c.key_id == payload.key_id)
                    .values(revoked_at=payload.now, version=api_keys.c.version + 1)
                )
            else:
                owner = connection.scalar(
                    select(api_keys.c.user_id).where(api_keys.c.key_id == payload.key_id)
                )
                connection.execute(
                    update(users).where(users.c.user_id == owner).values(role="viewer")
                )
            pipe.send("locked")
            assert pipe.recv() == "release"
        pipe.send("committed")
    finally:
        engine.dispose()
        pipe.close()


def _wait_for_pg_lock(engine: Engine, pid: int) -> None:
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        with engine.connect() as connection:
            waiting = connection.scalar(
                text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"), {"pid": pid}
            )
        if waiting == "Lock":
            return
        time.sleep(0.02)
    raise AssertionError("worker did not reach an actual PostgreSQL lock wait")


def test_issuance_only_once_hash_persistence_owner_and_session_compatibility(
    pg_case: PgCase,
    register_sensitive_failure_value: Callable[[SecretStr], None],
) -> None:
    issued = pg_case.issue()
    register_sensitive_failure_value(issued.token)
    token = issued.token.get_secret_value()
    assert len(token.removeprefix("dzk_")) >= 43
    assert token not in repr(issued)
    with pg_case.engine.begin() as connection:
        scope = lock_authenticated_principal(connection, ApiKeyCredential(issued.token), NOW)
        session_scope = lock_authenticated_principal(connection, pg_case.session, NOW)
        stored = (
            connection.execute(select(api_keys).where(api_keys.c.key_id == issued.metadata.key_id))
            .mappings()
            .one()
        )
    assert scope.user_id == session_scope.user_id == issued.metadata.user_id
    assert scope.permissions == frozenset({"read:asset", "read:public"})
    assert stored["token_hash"] == hashlib.sha256(token.encode()).hexdigest()
    assert token not in repr(dict(stored))
    assert issued.metadata.expires_at == NOW + timedelta(days=30)
    listed = PgApiKeyService(pg_case.engine, lambda: NOW).list_keys(pg_case.session)
    assert issued.metadata in listed
    assert token not in repr(listed)
    with pg_case.engine.begin() as connection, pytest.raises(SessionExpiredError):
        lock_authenticated_principal(connection, SessionCredential(issued.token), NOW)


def test_two_tenants_admin_cannot_manage_other_owner_and_revocation_idempotent(
    pg_case: PgCase,
) -> None:
    issued = pg_case.issue()
    with pg_case.engine.begin() as connection:
        owner = lock_authenticated_principal(connection, ApiKeyCredential(issued.token), NOW)
        other = lock_authenticated_principal(connection, pg_case.other_session, NOW)
    with pytest.raises(CrossTenantAccessError):
        other.enforce_visible("tenant", owner.tenant_id)
    for credential in (pg_case.other_session, pg_case.admin_session):
        with pytest.raises(ApiKeyNotFoundError, match="resource not found"):
            pg_case.service.revoke_key(credential, issued.metadata.key_id)
        assert pg_case.service.list_keys(credential) == ()
    revoked = pg_case.service.revoke_key(pg_case.session, issued.metadata.key_id)
    repeated = pg_case.service.revoke_key(pg_case.session, issued.metadata.key_id)
    assert repeated == revoked
    assert revoked.version == 2 and revoked.revoked_at == NOW
    with pg_case.engine.begin() as connection, pytest.raises(InvalidApiKeyError):
        lock_authenticated_principal(connection, ApiKeyCredential(issued.token), NOW)


def test_current_role_tenant_expiry_unknown_and_no_permission_rechecked(pg_case: PgCase) -> None:
    issued = pg_case.issue()
    asset_only = pg_case.issue(frozenset({"read:asset"}))
    with pg_case.engine.begin() as connection:
        connection.execute(
            update(users)
            .where(users.c.user_id == issued.metadata.user_id)
            .values(role="viewer", tenant_id="synthetic-current-tenant")
        )
    with pg_case.engine.begin() as connection:
        scope = lock_authenticated_principal(connection, ApiKeyCredential(issued.token), NOW)
        assert scope.role.value == "viewer"
        assert scope.tenant_id == "synthetic-current-tenant"
        assert scope.permissions == frozenset({"read:public"})
        with pytest.raises(InvalidApiKeyError):
            consume_api_key_rate_limit(connection, ApiKeyCredential(asset_only.token), NOW)
        with pytest.raises(InvalidApiKeyError):
            lock_authenticated_principal(
                connection, ApiKeyCredential(issued.token), issued.metadata.expires_at
            )
        with pytest.raises(InvalidApiKeyError):
            lock_authenticated_principal(connection, ApiKeyCredential(SecretStr("unknown")), NOW)
        assert (
            connection.scalar(
                select(func.count())
                .select_from(api_key_rate_buckets)
                .where(api_key_rate_buckets.c.key_id == asset_only.metadata.key_id)
            )
            == 0
        )
    with pytest.raises(PermissionDeniedError):
        pg_case.service.issue_key(pg_case.session, frozenset({"read:asset"}))


@pytest.mark.parametrize(
    "field,value",
    [
        ("resource", "wrong-audience"),
        ("scopes", ["manage:users"]),
        ("scopes", ["read:public", "read:public"]),
        ("token_hash", "not-a-hash"),
        ("version", 0),
        ("expires_at", NOW + timedelta(days=91)),
    ],
)
def test_real_pg_constraints_reject_invalid_key_metadata(
    pg_case: PgCase,
    field: str,
    value: object,
) -> None:
    issued = pg_case.issue()
    with pytest.raises(IntegrityError), pg_case.engine.begin() as connection:
        connection.execute(
            update(api_keys)
            .where(api_keys.c.key_id == issued.metadata.key_id)
            .values({field: value})
        )


def test_expiration_limit_is_absolute_even_in_dst_session_timezone(pg_case: PgCase) -> None:
    issued = pg_case.issue()
    with pytest.raises(IntegrityError), pg_case.engine.begin() as connection:
        connection.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
        connection.execute(
            update(api_keys)
            .where(api_keys.c.key_id == issued.metadata.key_id)
            .values(expires_at=NOW + timedelta(days=90, minutes=30))
        )


@pytest.mark.parametrize("operation,limit,attempts", [("read", 60, 40), ("ask", 10, 8)])
def test_two_process_rate_buckets_and_restart_authority(
    pg_case: PgCase,
    operation: Literal["read", "ask"],
    limit: int,
    attempts: int,
) -> None:
    issued = pg_case.issue()
    credential = ApiKeyCredential(issued.token)
    context = multiprocessing.get_context("spawn")
    processes = []
    pipes = []
    try:
        for _ in range(2):
            parent, child = context.Pipe()
            process = context.Process(target=_rate_worker, args=(child,))
            process.start()
            child.close()
            processes.append(process)
            pipes.append(parent)
            parent.send(
                ProcessInput(
                    pg_case.database_url, pg_case.schema, NOW, credential, operation, attempts
                )
            )
        for pipe in pipes:
            assert pipe.poll(15) and pipe.recv() == "ready"
        for pipe in pipes:
            pipe.send("go")
        results = []
        for pipe in pipes:
            assert pipe.poll(20)
            results.append(pipe.recv())
        assert sum(accepted for accepted, _ in results) == limit
        assert sum(limited for _, limited in results) == 2 * attempts - limit
        for process in processes:
            process.join(5)
            assert process.exitcode == 0
        restarted = _child_engine(
            ProcessInput(pg_case.database_url, pg_case.schema, NOW, credential)
        )
        try:
            with pytest.raises(ApiKeyRateLimitedError), restarted.begin() as connection:
                consume_api_key_rate_limit(connection, credential, NOW, operation=operation)
            with restarted.begin() as connection:
                consume_api_key_rate_limit(
                    connection, credential, NOW + timedelta(minutes=1), operation=operation
                )
                counts: list[int] = list(
                    connection.execute(
                        select(api_key_rate_buckets.c.request_count)
                        .where(
                            api_key_rate_buckets.c.key_id == issued.metadata.key_id,
                            api_key_rate_buckets.c.operation == operation,
                        )
                        .order_by(api_key_rate_buckets.c.window_started_at)
                    ).scalars()
                )
                assert counts == [limit, 1]
        finally:
            restarted.dispose()
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(5)
        for pipe in pipes:
            pipe.close()


def test_failed_business_transaction_rolls_back_quota_and_success_commits(pg_case: PgCase) -> None:
    issued = pg_case.issue()
    credential = ApiKeyCredential(issued.token)
    with (
        pytest.raises(RuntimeError, match="synthetic failure"),
        pg_case.engine.begin() as connection,
    ):
        consume_api_key_rate_limit(connection, credential, NOW, operation="ask")
        raise RuntimeError("synthetic failure")
    with pg_case.engine.begin() as connection:
        assert (
            connection.scalar(
                select(func.count())
                .select_from(api_key_rate_buckets)
                .where(api_key_rate_buckets.c.key_id == issued.metadata.key_id)
            )
            == 0
        )
        consume_api_key_rate_limit(connection, credential, NOW, operation="ask")
    with pg_case.engine.connect() as connection:
        assert (
            connection.scalar(
                select(api_key_rate_buckets.c.request_count).where(
                    api_key_rate_buckets.c.key_id == issued.metadata.key_id
                )
            )
            == 1
        )


@pytest.mark.parametrize("action", ["revoke_service", "role_hold"])
def test_authentication_lock_orders_revocation_and_role_commits(
    pg_case: PgCase, action: str
) -> None:
    issued = pg_case.issue()
    credential = ApiKeyCredential(issued.token)
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=_mutation_worker, args=(child,))
    try:
        with pg_case.engine.begin() as connection:
            assert lock_authenticated_principal(
                connection, credential, NOW
            ).permissions == frozenset({"read:public", "read:asset"})
            process.start()
            child.close()
            parent.send(
                ProcessInput(
                    pg_case.database_url,
                    pg_case.schema,
                    NOW,
                    pg_case.session,
                    key_id=issued.metadata.key_id,
                    action=action,
                )
            )
            assert parent.poll(15)
            started, pid = parent.recv()
            assert started == "started"
            _wait_for_pg_lock(pg_case.engine, pid)
            assert not parent.poll(0.05)
        if action == "role_hold":
            assert parent.poll(10) and parent.recv() == "locked"
            parent.send("release")
        assert parent.poll(10) and parent.recv() == "committed"
        process.join(5)
        assert process.exitcode == 0
        with pg_case.engine.begin() as connection:
            if action == "revoke_service":
                with pytest.raises(InvalidApiKeyError):
                    lock_authenticated_principal(connection, credential, NOW)
            else:
                assert lock_authenticated_principal(
                    connection, credential, NOW
                ).permissions == frozenset({"read:public"})
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)
        parent.close()


@pytest.mark.parametrize("action", ["revoke_hold", "role_hold"])
def test_pending_revocation_or_role_change_wins_before_authentication(
    pg_case: PgCase,
    action: str,
) -> None:
    issued = pg_case.issue()
    credential = ApiKeyCredential(issued.token)
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=_mutation_worker, args=(child,))
    process.start()
    child.close()
    try:
        parent.send(
            ProcessInput(
                pg_case.database_url,
                pg_case.schema,
                NOW,
                credential,
                key_id=issued.metadata.key_id,
                action=action,
            )
        )
        assert parent.poll(15) and parent.recv()[0] == "started"
        assert parent.poll(10) and parent.recv() == "locked"
        with ThreadPoolExecutor(max_workers=1) as executor:
            reader_pid = []

            def authenticate() -> AccessScope:
                with pg_case.engine.begin() as connection:
                    reader_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
                    return lock_authenticated_principal(connection, credential, NOW)

            result = executor.submit(authenticate)
            deadline = time.monotonic() + 4
            while not reader_pid and time.monotonic() < deadline:
                time.sleep(0.01)
            assert reader_pid
            _wait_for_pg_lock(pg_case.engine, reader_pid[0])
            assert not result.done()
            parent.send("release")
            assert parent.poll(10) and parent.recv() == "committed"
            if action == "revoke_hold":
                with pytest.raises(InvalidApiKeyError):
                    result.result(timeout=10)
            else:
                assert result.result(timeout=10).permissions == frozenset({"read:public"})
        process.join(5)
        assert process.exitcode == 0
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)
        parent.close()


def test_explicit_transaction_and_non_session_management_fail_closed(pg_case: PgCase) -> None:
    issued = pg_case.issue()
    credential = ApiKeyCredential(issued.token)
    with (
        pg_case.engine.connect() as connection,
        pytest.raises(ValueError, match="caller transaction"),
    ):
        lock_authenticated_principal(connection, credential, NOW)
    issue: Callable[..., object] = pg_case.service.issue_key
    revoke: Callable[..., object] = pg_case.service.revoke_key
    listing: Callable[..., object] = pg_case.service.list_keys
    with pytest.raises(TypeError, match="session credential"):
        issue(credential, frozenset({"read:public"}))
    with pytest.raises(TypeError, match="session credential"):
        revoke(credential, issued.metadata.key_id)
    with pytest.raises(TypeError, match="session credential"):
        listing(credential)


@pytest.mark.parametrize("corruption", ["wrong_resource", "missing_owner"])
def test_corrupted_key_authority_fails_closed_without_consuming_a_bucket(
    pg_case: PgCase,
    corruption: str,
) -> None:
    """Owned fault injection rolls back table DDL/data and retains the original constraints."""
    issued = pg_case.issue()
    with (
        pytest.raises(RuntimeError, match="rollback fault injection"),
        pg_case.engine.begin() as conn,
    ):
        if corruption == "wrong_resource":
            conn.exec_driver_sql(
                f'ALTER TABLE "{pg_case.schema}".api_keys DROP CONSTRAINT ck_api_keys_resource'
            )
            conn.execute(
                update(api_keys)
                .where(api_keys.c.key_id == issued.metadata.key_id)
                .values(resource="wrong-audience")
            )
        else:
            conn.exec_driver_sql(
                f'ALTER TABLE "{pg_case.schema}".api_keys DROP CONSTRAINT api_keys_user_id_fkey'
            )
            conn.execute(
                update(api_keys)
                .where(api_keys.c.key_id == issued.metadata.key_id)
                .values(user_id="synthetic-missing-owner")
            )
        with pytest.raises(InvalidApiKeyError):
            consume_api_key_rate_limit(conn, ApiKeyCredential(issued.token), NOW)
        assert (
            conn.scalar(
                select(func.count())
                .select_from(api_key_rate_buckets)
                .where(api_key_rate_buckets.c.key_id == issued.metadata.key_id)
            )
            == 0
        )
        raise RuntimeError("rollback fault injection")
    with pg_case.engine.begin() as conn:
        assert (
            lock_authenticated_principal(conn, ApiKeyCredential(issued.token), NOW).user_id
            == issued.metadata.user_id
        )
