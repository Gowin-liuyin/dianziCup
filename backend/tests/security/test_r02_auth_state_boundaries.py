"""真实隔离PG的认证授权、安全失败和审计事务边界，不计外源模型live。"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from ai_intel.api.app import create_application
from ai_intel.api.auth_state import PgAuthenticationStateStore, auth_sessions
from ai_intel.api.authentication import (
    AuditEventError,
    AuthenticationSessionService,
    CsrfRejectionError,
    DatabaseUserDirectory,
    InvalidCredentialsError,
    UserAccount,
)
from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from ai_intel.infrastructure.settings import ApplicationSettings

ORIGIN = "http://127.0.0.1:25173"
pytestmark = pytest.mark.real_pg


@dataclass
class SecurityCase:
    engine: Engine
    username: str
    password: str = field(repr=False)
    service: AuthenticationSessionService
    account: UserAccount


@pytest.fixture
def security_case(migrated_engine: Engine) -> SecurityCase:
    username = f"test-r02-security-{uuid.uuid4()}"
    password = secrets.token_urlsafe(24)
    service = AuthenticationSessionService(
        DatabaseUserDirectory(migrated_engine),
        (ORIGIN,),
        False,
        state_store=PgAuthenticationStateStore(migrated_engine),
    )
    account = service.create_precreated_user(username, password, username, Role.TENANT_ADMIN)
    return SecurityCase(migrated_engine, username, password, service, account)


def client_for(service: AuthenticationSessionService) -> TestClient:
    return TestClient(
        create_application(
            service,
            settings=ApplicationSettings(
                app_env="test",
                data_mode="live",
                allowed_origins=(ORIGIN,),
            ),
        )
    )


def test_audit_tenant_isolation_and_unknown_user_system_admin_only(
    security_case: SecurityCase,
) -> None:
    case = security_case
    other_username = f"test-other-{uuid.uuid4()}"
    other = case.service.create_precreated_user(
        other_username, case.password, other_username, Role.TENANT_ADMIN
    )
    case.service.login(case.username, case.password, ORIGIN, case.username)
    case.service.login(other_username, case.password, ORIGIN, other_username)
    for name in (case.username, "test-missing"):
        with pytest.raises(InvalidCredentialsError):
            case.service.login(name, "synthetic-wrong-password", ORIGIN, f"{case.username}-{name}")
    own_scope = AccessScope.for_authenticated_user(
        case.account.user_id, case.account.tenant_id, Role.TENANT_ADMIN
    )
    own = case.service.read_audit_events(own_scope).events
    assert len(own) == 2
    assert all(item.actor_user_id == case.account.user_id for item in own)
    other_scope = AccessScope.for_authenticated_user(
        other.user_id, other.tenant_id, Role.TENANT_ADMIN
    )
    assert len(case.service.read_audit_events(other_scope).events) == 1
    admin = AccessScope.for_authenticated_user("test-system-admin", None, Role.SYSTEM_ADMIN)
    all_events = case.service.read_audit_events(admin, limit=100).events
    assert any(item.tenant_id is None and item.event_type == "login_failed" for item in all_events)
    with pytest.raises(AuditEventError, match="access scope"):
        case.service.audit_events()
    with pytest.raises(PermissionDeniedError):
        case.service.read_audit_events(
            AccessScope.for_authenticated_user("analyst", case.account.tenant_id, Role.ANALYST)
        )
    with pytest.raises(PermissionDeniedError):
        case.service.read_audit_events(
            AccessScope.for_authenticated_user("tenantless", None, Role.TENANT_ADMIN)
        )


def test_audit_keyset_pagination_is_bounded_stable_and_has_no_secrets(
    security_case: SecurityCase,
) -> None:
    case = security_case
    for _ in range(4):
        token, _ = case.service.login(case.username, case.password, ORIGIN, case.username)
        case.service.logout(token)
    scope = AccessScope.for_authenticated_user(
        case.account.user_id, case.account.tenant_id, Role.TENANT_ADMIN
    )
    first = case.service.read_audit_events(scope, limit=3)
    second = case.service.read_audit_events(scope, limit=3, cursor=first.next_cursor)
    third = case.service.read_audit_events(scope, limit=3, cursor=second.next_cursor)
    assert [len(page.events) for page in (first, second, third)] == [3, 3, 2]
    assert len({item.audit_id for page in (first, second, third) for item in page.events}) == 8
    assert third.next_cursor is None
    text_events = repr(first.events + second.events + third.events)
    assert bool(case.password not in text_events)
    assert bool(token not in text_events)
    for limit in (0, 101, True):
        with pytest.raises(ValueError, match="between 1 and 100"):
            case.service.read_audit_events(scope, limit=limit)
    with pytest.raises(ValueError, match="invalid audit cursor"):
        case.service.read_audit_events(scope, cursor="untrusted-cursor")


def test_pg_csrf_non_ascii_and_origin_rejections_preserve_session(
    security_case: SecurityCase,
) -> None:
    case = security_case
    token, record = case.service.login(case.username, case.password, ORIGIN, case.username)
    for csrf, origin in (
        ("非ASCII", ORIGIN),
        ("", ORIGIN),
        (record.csrf_token, "https://untrusted.invalid"),
    ):
        with pytest.raises(CsrfRejectionError):
            case.service.validate_write_request(token, csrf, origin)
    assert case.service.validate_session(token).user_id == case.account.user_id


def test_pg_failure_http_is_fixed_503_without_memory_fallback(security_case: SecurityCase) -> None:
    case = security_case
    token, _ = case.service.login(case.username, case.password, ORIGIN, case.username)
    bad_engine = create_engine(case.engine.url.set(port=1), connect_args={"connect_timeout": 1})
    bad_service = AuthenticationSessionService(
        DatabaseUserDirectory(bad_engine),
        (ORIGIN,),
        False,
        state_store=PgAuthenticationStateStore(bad_engine),
    )
    client = client_for(bad_service)
    client.cookies.set("ai_intel_session", token)
    try:
        responses = [
            client.get("/v1/auth/me"),
            client.get("/v1/auth/csrf"),
            client.post(
                "/v1/auth/login",
                json={"username": case.username, "password": case.password},
                headers={"Origin": ORIGIN},
            ),
            client.post(
                "/v1/auth/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": "synthetic-csrf"}
            ),
        ]
        for response in responses:
            assert response.status_code == 503
            assert response.headers["content-type"].startswith("application/problem+json")
            assert response.json()["error"]["code"] == "authentication_unavailable"
            assert bool(case.password not in response.text)
            assert bool(token not in response.text)
            assert "postgresql" not in response.text
    finally:
        client.close()
        bad_engine.dispose()
    assert case.service.validate_session(token).user_id == case.account.user_id


def test_logout_audit_failure_rolls_back_revocation(security_case: SecurityCase) -> None:
    case = security_case
    token, record = case.service.login(case.username, case.password, ORIGIN, case.username)

    def reject_audit(conn, cursor, statement, parameters, context, executemany) -> None:
        if statement.startswith("INSERT INTO auth_audit_events"):
            raise SQLAlchemyError("synthetic audit failure")

    event.listen(case.engine, "before_cursor_execute", reject_audit)
    try:
        with pytest.raises(SQLAlchemyError, match="synthetic audit failure"):
            case.service.logout(token)
    finally:
        event.remove(case.engine, "before_cursor_execute", reject_audit)
    with case.engine.connect() as connection:
        revoked = connection.execute(
            select(auth_sessions.c.revoked_at).where(
                auth_sessions.c.session_hash == record.session_id
            )
        ).scalar_one()
    assert revoked is None
    assert case.service.validate_session(token).user_id == case.account.user_id


def test_me_current_scope_and_forged_identity_422(security_case: SecurityCase) -> None:
    case = security_case
    client = client_for(case.service)
    login = client.post(
        "/v1/auth/login",
        json={"username": case.username, "password": case.password},
        headers={"Origin": ORIGIN},
    )
    assert login.status_code == 200
    snapshot = client.get("/v1/auth/me")
    assert snapshot.status_code == 200
    assert bool(snapshot.json()["csrf_token"] == login.json()["csrf_token"])
    assert snapshot.json()["tenant_id"] == case.account.tenant_id
    forged = client.post(
        "/v1/auth/login",
        json={
            "username": case.username,
            "password": case.password,
            "role": "system_admin",
            "tenant_id": "other-tenant",
        },
        headers={"Origin": ORIGIN},
    )
    assert forged.status_code == 422
    assert "other-tenant" not in forged.text
    assert bool(case.password not in forged.text)
    assert client.get("/v1/auth/me").json()["role"] == "tenant_admin"
