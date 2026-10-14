"""T40 前置: /auth 路由合同测试(错误映射/Cookie 属性/CSRF 下发)。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from ai_intel.api.app import create_application
from ai_intel.api.authentication import (
    AuthenticationSessionService,
    InMemoryUserDirectory,
)
from ai_intel.domain.access import Role


def build_service() -> AuthenticationSessionService:
    directory = InMemoryUserDirectory()
    service = AuthenticationSessionService(
        directory, ("http://localhost:5173",), cookie_secure=False
    )
    service.create_precreated_user("analyst", "correct horse", "tenant-1", Role.ANALYST)
    return service


def test_auth_routes_login_me_csrf_logout_contract() -> None:
    service = build_service()
    client = TestClient(create_application(service))
    login = client.post(
        "/auth/login",
        json={"username": "analyst", "password": "correct horse"},
        headers={"origin": "http://localhost:5173"},
    )
    assert login.status_code == 200
    body = login.json()
    assert isinstance(body["user_id"], str) and body["user_id"]
    assert body["csrf_token"]
    assert "ai_intel_session" in login.cookies
    me = client.get("/auth/me")
    assert me.status_code == 200 and me.json()["role"] == "analyst"
    csrf = client.get("/auth/csrf")
    assert csrf.status_code == 200 and csrf.json()["header_name"] == "X-CSRF-Token"
    logout = client.post(
        "/auth/logout",
        headers={"origin": "http://localhost:5173", "X-CSRF-Token": body["csrf_token"]},
    )
    assert logout.status_code == 200
    after = client.get("/auth/me")
    assert after.status_code == 401 and after.json()["error"]["code"] in (
        "session_expired",
        "unauthenticated",
    )


def test_auth_routes_error_mapping_no_false_success() -> None:
    service = build_service()
    client = TestClient(create_application(service))
    bad = client.post(
        "/auth/login",
        json={"username": "analyst", "password": "wrong"},
        headers={"origin": "http://localhost:5173"},
    )
    assert bad.status_code == 401 and bad.json()["error"]["retryable"] is False
    anonymous = client.get("/auth/me")
    assert anonymous.status_code == 401
    assert anonymous.json()["error"]["code"] == "unauthenticated"
    assert "csrf_token" not in anonymous.text


def test_default_auth_routes_are_registered_with_honest_missing_dependencies() -> None:
    client = TestClient(create_application())
    assert client.get("/auth/me").status_code == 401
    response = client.post(
        "/auth/login",
        json={"username": "analyst", "password": "synthetic"},
        headers={"origin": "http://localhost:5173"},
    )
    assert response.status_code == 503
