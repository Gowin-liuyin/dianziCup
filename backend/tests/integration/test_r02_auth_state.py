"""独立真实PG认证状态：进程、并发、当前身份、过期和事务回滚。"""

from __future__ import annotations

import hashlib
import multiprocessing
import secrets
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from multiprocessing.connection import Connection
from threading import Barrier, Event
from time import sleep

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from ai_intel.api.auth_state import (
    PgAuthenticationStateStore,
    auth_audit_events,
    auth_login_attempts,
    auth_sessions,
)
from ai_intel.api.authentication import (
    AuthenticationSessionService,
    DatabaseUserDirectory,
    InvalidCredentialsError,
    LoginRateLimitedError,
    SessionExpiredError,
    UserAccount,
)
from ai_intel.domain.access import Role
from ai_intel.knowledge.models import users

ORIGIN = "http://127.0.0.1:25173"
pytestmark = pytest.mark.real_pg


@dataclass
class AuthCase:
    engine: Engine
    username: str
    password: str = field(repr=False)
    tenant_id: str
    service: AuthenticationSessionService
    account: UserAccount


@dataclass(frozen=True)
class AuthProcessPayload:
    """进程管道载荷的repr隐藏凭据，即使启动失败也不能写进pytest参数日志。"""

    username: str = ""
    password: str = field(default="", repr=False)
    client_key: str = ""
    session_token: str = field(default="", repr=False)


def build_service(engine: Engine) -> AuthenticationSessionService:
    return AuthenticationSessionService(
        DatabaseUserDirectory(engine),
        (ORIGIN,),
        False,
        state_store=PgAuthenticationStateStore(engine),
    )


@pytest.fixture
def pg_auth(migrated_engine: Engine) -> AuthCase:
    unique = str(uuid.uuid4())
    service = build_service(migrated_engine)
    username = f"test-r02-auth-{unique}"
    password = secrets.token_urlsafe(24)
    tenant_id = f"test-tenant-{unique}"
    account = service.create_precreated_user(username, password, tenant_id, Role.ANALYST)
    return AuthCase(migrated_engine, username, password, tenant_id, service, account)


def count_user_sessions(case: AuthCase) -> int:
    with case.engine.connect() as connection:
        return connection.execute(
            select(func.count())
            .select_from(auth_sessions)
            .where(auth_sessions.c.user_id == case.account.user_id)
        ).scalar_one()


def _process_session(pipe: Connection, action: str) -> None:
    """子进程通过专用环境获取连接；明文token仅走进程管道，不进入日志。"""
    import os

    engine = create_engine(os.environ["TEST_DATABASE_URL"], connect_args={"connect_timeout": 3})
    service = build_service(engine)
    try:
        payload = pipe.recv()
        assert isinstance(payload, AuthProcessPayload)
        if action == "issue":
            token, _ = service.login(payload.username, payload.password, ORIGIN, payload.client_key)
            pipe.send(token)
        elif action == "read_revoke":
            principal = service.validate_session(payload.session_token)
            service.logout(payload.session_token)
            pipe.send(principal.user_id)
        elif action == "attempt":
            try:
                service.login(payload.username, payload.password, ORIGIN, payload.client_key)
            except InvalidCredentialsError:
                pipe.send(401)
            except LoginRateLimitedError:
                pipe.send(429)
            else:
                pipe.send(200)
        elif action == "synthetic_startup_failure":
            raise RuntimeError("controlled authentication child startup failure")
    finally:
        engine.dispose()
        pipe.close()


def process_roundtrip(action: str, payload: AuthProcessPayload) -> tuple[int, object]:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=_process_session, args=(child, action))
    process.start()
    child.close()
    try:
        parent.send(payload)
        assert parent.poll(30), "authentication child did not respond"
        result = parent.recv()
    finally:
        parent.close()
        process.join(timeout=30)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
    assert process.exitcode == 0
    assert process.pid is not None
    return process.pid, result


def test_issue_read_revoke_across_two_independent_processes(
    pg_auth: AuthCase, record_property: Callable[[str, object], None]
) -> None:
    issuing_pid, token = process_roundtrip(
        "issue", AuthProcessPayload(pg_auth.username, pg_auth.password, pg_auth.username)
    )
    assert isinstance(token, str)
    revoking_pid, user_id = process_roundtrip(
        "read_revoke", AuthProcessPayload(session_token=token)
    )
    assert issuing_pid != revoking_pid
    record_property("issuing_pid", issuing_pid)
    record_property("revoking_pid", revoking_pid)
    assert user_id == pg_auth.account.user_id
    with pytest.raises(SessionExpiredError):
        pg_auth.service.validate_session(token)
    assert count_user_sessions(pg_auth) == 1
    pg_auth.service.logout(token)
    with pg_auth.engine.connect() as connection:
        count = connection.execute(
            select(func.count())
            .select_from(auth_audit_events)
            .where(
                auth_audit_events.c.actor_user_id == pg_auth.account.user_id,
                auth_audit_events.c.event_type == "logout",
            )
        ).scalar_one()
    assert count == 1


def test_snapshot_single_join_and_current_role_change(pg_auth: AuthCase) -> None:
    token, record = pg_auth.service.login(
        pg_auth.username, pg_auth.password, ORIGIN, pg_auth.username
    )
    statements: list[str] = []

    def collect_statement(conn, cursor, statement, parameters, context, executemany) -> None:
        statements.append(statement)

    event.listen(pg_auth.engine, "before_cursor_execute", collect_statement)
    try:
        principal, snapshot = build_service(pg_auth.engine).authenticated_session(token)
    finally:
        event.remove(pg_auth.engine, "before_cursor_execute", collect_statement)
    assert len(statements) == 1
    assert "JOIN users" in statements[0]
    assert principal.user_id == pg_auth.account.user_id
    assert bool(snapshot.csrf_token == record.csrf_token)
    with pg_auth.engine.begin() as connection:
        connection.execute(
            users.update().where(users.c.user_id == principal.user_id).values(role="viewer")
        )
    assert build_service(pg_auth.engine).validate_session(token).role == Role.VIEWER


def test_expiry_boundary_rejects_without_deleting_history(pg_auth: AuthCase) -> None:
    issued_at = datetime.now(UTC)
    now = [issued_at]
    service = AuthenticationSessionService(
        DatabaseUserDirectory(pg_auth.engine),
        (ORIGIN,),
        False,
        clock=lambda: now[0],
        state_store=PgAuthenticationStateStore(pg_auth.engine),
    )
    token, _ = service.login(pg_auth.username, pg_auth.password, ORIGIN, pg_auth.username)
    now[0] = issued_at + timedelta(seconds=1799)
    assert service.validate_session(token).user_id == pg_auth.account.user_id
    now[0] = issued_at + timedelta(seconds=1800)
    with pytest.raises(SessionExpiredError):
        service.validate_session(token)
    assert count_user_sessions(pg_auth) == 1


def test_eight_concurrent_requests_share_five_pg_reservations(pg_auth: AuthCase) -> None:
    class SlowMissingDirectory(DatabaseUserDirectory):
        def find_by_username(self, username: str) -> UserAccount | None:
            sleep(0.1)
            return None

    services = [
        AuthenticationSessionService(
            SlowMissingDirectory(pg_auth.engine),
            (ORIGIN,),
            False,
            state_store=PgAuthenticationStateStore(pg_auth.engine),
        )
        for _ in range(8)
    ]
    barrier = Barrier(8)

    def attempt(index: int) -> int:
        barrier.wait(timeout=5)
        try:
            services[index].login("test-missing", "synthetic-password", ORIGIN, pg_auth.username)
        except InvalidCredentialsError:
            return 401
        except LoginRateLimitedError:
            return 429
        raise AssertionError("missing user logged in")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))
    assert results.count(401) == 5
    assert results.count(429) == 3


def test_failure_limit_persists_across_independent_processes(pg_auth: AuthCase) -> None:
    for _ in range(5):
        _, status = process_roundtrip(
            "attempt", AuthProcessPayload("test-missing", "synthetic-password", pg_auth.username)
        )
        assert status == 401
    _, status = process_roundtrip(
        "attempt", AuthProcessPayload("test-missing", "synthetic-password", pg_auth.username)
    )
    assert status == 429


def test_child_startup_failure_trace_hides_live_test_credentials(
    pg_auth: AuthCase, capfd: pytest.CaptureFixture[str]
) -> None:
    token, _ = pg_auth.service.login(pg_auth.username, pg_auth.password, ORIGIN, pg_auth.username)
    payload = AuthProcessPayload(
        pg_auth.username, pg_auth.password, pg_auth.username, session_token=token
    )
    with pytest.raises(EOFError) as failure:
        process_roundtrip("synthetic_startup_failure", payload)
    captured = capfd.readouterr()
    failure_text = str(failure.getrepr(showlocals=False)) + captured.err + repr(payload)
    safe = pg_auth.password not in failure_text and token not in failure_text
    assert safe, "controlled process failure exposed authentication test credentials"
    assert "controlled authentication child startup failure" in captured.err
    assert "AuthProcessPayload" in failure_text


def test_success_preserves_another_instances_inflight_reservation(pg_auth: AuthCase) -> None:
    waiting = Event()
    release = Event()

    class HoldingDirectory(DatabaseUserDirectory):
        def find_by_username(self, username: str) -> UserAccount | None:
            account = super().find_by_username(username)
            waiting.set()
            assert release.wait(timeout=10), "controlled directory was not released"
            return account

    slow_service = AuthenticationSessionService(
        HoldingDirectory(pg_auth.engine),
        (ORIGIN,),
        False,
        state_store=PgAuthenticationStateStore(pg_auth.engine),
    )
    client_hash = hashlib.sha256(pg_auth.username.encode()).hexdigest()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            slow_service.login, pg_auth.username, pg_auth.password, ORIGIN, pg_auth.username
        )
        try:
            assert waiting.wait(timeout=5), "login did not commit its reservation"
            pg_auth.service.login(pg_auth.username, pg_auth.password, ORIGIN, pg_auth.username)
            with pg_auth.engine.connect() as connection:
                remaining = connection.execute(
                    select(func.count())
                    .select_from(auth_login_attempts)
                    .where(auth_login_attempts.c.client_key_hash == client_hash)
                ).scalar_one()
            assert remaining == 1
        finally:
            release.set()
        future.result(timeout=10)
    with pg_auth.engine.connect() as connection:
        remaining = connection.execute(
            select(func.count())
            .select_from(auth_login_attempts)
            .where(auth_login_attempts.c.client_key_hash == client_hash)
        ).scalar_one()
    assert remaining == 0


def test_success_releases_only_own_attempt_and_preserves_other_failures(pg_auth: AuthCase) -> None:
    for _ in range(6):
        token, _ = pg_auth.service.login(
            pg_auth.username, pg_auth.password, ORIGIN, pg_auth.username
        )
        build_service(pg_auth.engine).logout(token)
    for _ in range(4):
        with pytest.raises(InvalidCredentialsError):
            pg_auth.service.login("test-missing", "synthetic-password", ORIGIN, pg_auth.username)
    pg_auth.service.login(pg_auth.username, pg_auth.password, ORIGIN, pg_auth.username)
    with pytest.raises(InvalidCredentialsError):
        pg_auth.service.login("test-missing", "synthetic-password", ORIGIN, pg_auth.username)
    with pytest.raises(LoginRateLimitedError):
        pg_auth.service.login(pg_auth.username, pg_auth.password, ORIGIN, pg_auth.username)


def test_attempt_window_boundary_releases_expired_failures(pg_auth: AuthCase) -> None:
    now = [datetime.now(UTC)]
    service = AuthenticationSessionService(
        DatabaseUserDirectory(pg_auth.engine),
        (ORIGIN,),
        False,
        clock=lambda: now[0],
        state_store=PgAuthenticationStateStore(pg_auth.engine),
    )
    for _ in range(5):
        with pytest.raises(InvalidCredentialsError):
            service.login("test-missing", "synthetic-password", ORIGIN, pg_auth.username)
    now[0] += timedelta(seconds=899)
    with pytest.raises(LoginRateLimitedError):
        service.login(pg_auth.username, pg_auth.password, ORIGIN, pg_auth.username)
    now[0] += timedelta(seconds=1)
    service.login(pg_auth.username, pg_auth.password, ORIGIN, pg_auth.username)


def test_audit_failure_rolls_back_session_and_own_release(pg_auth: AuthCase) -> None:
    def reject_audit(conn, cursor, statement, parameters, context, executemany) -> None:
        if statement.startswith("INSERT INTO auth_audit_events"):
            raise SQLAlchemyError("synthetic audit failure")

    event.listen(pg_auth.engine, "before_cursor_execute", reject_audit)
    try:
        with pytest.raises(SQLAlchemyError, match="synthetic audit failure"):
            pg_auth.service.login(pg_auth.username, pg_auth.password, ORIGIN, pg_auth.username)
    finally:
        event.remove(pg_auth.engine, "before_cursor_execute", reject_audit)
    assert count_user_sessions(pg_auth) == 0
    client_hash = hashlib.sha256(pg_auth.username.encode()).hexdigest()
    with pg_auth.engine.connect() as connection:
        remaining = connection.execute(
            select(func.count())
            .select_from(auth_login_attempts)
            .where(auth_login_attempts.c.client_key_hash == client_hash)
        ).scalar_one()
    assert remaining == 1


def test_session_hash_only_is_stored(pg_auth: AuthCase) -> None:
    token, record = pg_auth.service.login(
        pg_auth.username, pg_auth.password, ORIGIN, pg_auth.username
    )
    with pg_auth.engine.connect() as connection:
        stored = connection.execute(
            select(auth_sessions.c.session_hash).where(
                auth_sessions.c.user_id == pg_auth.account.user_id
            )
        ).scalar_one()
    assert bool(stored == hashlib.sha256(token.encode()).hexdigest())
    assert bool(stored != token)
    assert bool(stored == record.session_id)
