"""R01 HTTP边界；显式内存fixture只验证路由，不计持久化或live。"""

from fastapi.testclient import TestClient

from ai_intel.api.app import create_application
from ai_intel.api.authentication import AuthenticationSessionService, InMemoryUserDirectory
from ai_intel.domain.access import Role
from ai_intel.infrastructure.settings import ApplicationSettings

ORIGIN = "http://127.0.0.1:25173"


def fixture_client() -> TestClient:
    service = AuthenticationSessionService(InMemoryUserDirectory(), (ORIGIN,), False)
    service.create_precreated_user(
        "fixture-analyst", "synthetic-password", "fixture-tenant", Role.ANALYST
    )
    settings = ApplicationSettings(app_env="test", data_mode="fixture", allowed_origins=(ORIGIN,))
    return TestClient(create_application(service, settings=settings))


def test_default_application_registers_authentication_without_false_readiness() -> None:
    client = TestClient(create_application(settings=ApplicationSettings(app_env="test")))
    assert client.get("/v1/auth/me").status_code == 401
    response = client.get("/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["dependencies"]["database"]["state"] == "not_configured"


def test_logout_requires_session_bound_csrf_and_origin() -> None:
    client = fixture_client()
    response = client.post(
        "/v1/auth/login",
        json={"username": "fixture-analyst", "password": "synthetic-password"},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200
    csrf = response.json()["csrf_token"]
    assert client.post("/v1/auth/logout").status_code == 403
    assert client.get("/v1/auth/me").status_code == 200
    assert (
        client.post(
            "/v1/auth/logout", headers={"Origin": "https://untrusted.invalid", "X-CSRF-Token": csrf}
        ).status_code
        == 403
    )
    assert (
        client.post("/v1/auth/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf}).status_code
        == 200
    )
    assert client.get("/v1/auth/me").status_code == 401


def test_disallowed_login_origin_returns_safe_problem() -> None:
    client = fixture_client()
    response = client.post(
        "/v1/auth/login",
        json={"username": "fixture-analyst", "password": "synthetic-password"},
        headers={"Origin": "https://untrusted.invalid"},
    )
    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["error"]["code"] == "csrf_rejected"
    assert response.json()["trace_id"]


def test_strict_login_validation_never_echoes_sensitive_input() -> None:
    client = fixture_client()
    secret_input = "synthetic-secret-value-please-hide"
    for payload in [
        {"username": [], "password": secret_input},
        {"username": "fixture-analyst", "password": {"unsafe": secret_input}},
        {
            "username": "fixture-analyst",
            "password": secret_input,
            "tenant_id": "other-tenant",
            "role": "system_admin",
        },
    ]:
        response = client.post("/v1/auth/login", json=payload, headers={"Origin": ORIGIN})
        assert response.status_code == 422
        assert secret_input not in response.text
        assert "other-tenant" not in response.text
        assert response.headers["content-type"].startswith("application/problem+json")


def test_me_returns_authenticated_scope_and_explicit_fixture_mode() -> None:
    client = fixture_client()
    client.post(
        "/v1/auth/login",
        json={"username": "fixture-analyst", "password": "synthetic-password"},
        headers={"Origin": ORIGIN},
    )
    response = client.get("/v1/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "fixture-tenant"
    assert body["role"] == "analyst"
    assert body["permission_version"] == 1
    assert body["data_mode"] == "fixture"
    assert "read:asset" in body["permissions"]
    assert "password" not in response.text and "session_token" not in response.text
