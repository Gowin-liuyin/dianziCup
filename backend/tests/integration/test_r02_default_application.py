"""默认factory真实PG接线；关闭首个应用后同Cookie在第二应用有效并可撤销。"""

import secrets
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.engine import Engine

from ai_intel.api.app import create_application
from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.domain.access import Role
from ai_intel.infrastructure.settings import ApplicationSettings

pytestmark = pytest.mark.real_pg


def test_default_factory_uses_shared_pg_session_after_application_restart(
    migrated_engine: Engine,
) -> None:
    username = "test-default-r02-" + uuid4().hex
    password = SecretStr(secrets.token_urlsafe(24))
    origin = "http://127.0.0.1:25173"
    directory = DatabaseUserDirectory(migrated_engine)
    account = AuthenticationSessionService(directory, (origin,), False).create_precreated_user(
        username, password.get_secret_value(), "test-default-tenant", Role.ANALYST
    )
    settings = ApplicationSettings(
        app_env="test",
        database_url=migrated_engine.url.render_as_string(hide_password=False),
        allowed_origins=(origin,),
    )
    with TestClient(
        create_application(settings=settings), client=("test-" + uuid4().hex, 50000)
    ) as first:
        login = first.post(
            "/v1/auth/login",
            json={"username": username, "password": password.get_secret_value()},
            headers={"Origin": origin},
        )
        assert login.status_code == 200
        cookie_value = first.cookies.get(SESSION_COOKIE_NAME)
        session_cookie = SecretStr(cookie_value) if cookie_value is not None else None
        del cookie_value
    with TestClient(create_application(settings=settings)) as second:
        assert session_cookie is not None
        second.cookies.set(SESSION_COOKIE_NAME, session_cookie.get_secret_value())
        identity = second.get("/v1/auth/me")
        assert identity.status_code == 200
        assert identity.json()["user_id"] == account.user_id
        assert identity.json()["tenant_id"] == "test-default-tenant"
        logout = second.post(
            "/v1/auth/logout",
            headers={"Origin": origin, "X-CSRF-Token": identity.json()["csrf_token"]},
        )
        assert logout.status_code == 200
    with TestClient(create_application(settings=settings)) as third:
        third.cookies.set(SESSION_COOKIE_NAME, session_cookie.get_secret_value())
        assert third.get("/v1/auth/me").status_code == 401
