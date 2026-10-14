"""R01 HTTP边界；显式内存fixture只验证路由，不计持久化或live。"""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from time import sleep

import pytest
from fastapi.testclient import TestClient

from ai_intel.api.app import create_application
from ai_intel.api.authentication import (
    AuthenticationSessionService,
    InMemoryUserDirectory,
    InvalidCredentialsError,
    LoginRateLimitedError,
    UserAccount,
)
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


def test_non_ascii_csrf_is_rejected_without_revoking_session() -> None:
    client = fixture_client()
    client.post(
        "/v1/auth/login",
        json={"username": "fixture-analyst", "password": "synthetic-password"},
        headers={"Origin": ORIGIN},
    )
    response = client.post(
        "/v1/auth/logout", headers=[(b"Origin", ORIGIN.encode()), (b"X-CSRF-Token", b"\xff")]
    )
    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/problem+json")
    assert client.get("/v1/auth/me").status_code == 200


@pytest.mark.parametrize(
    ("path", "expected_status", "expected_code"),
    [
        ("/v1/auth/missing", 404, "not_found"),
        ("/v1/auth/login", 405, "method_not_allowed"),
    ],
)
def test_routing_errors_follow_problem_contract(
    path: str, expected_status: int, expected_code: str
) -> None:
    response = fixture_client().get(path)
    assert response.status_code == expected_status
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["error"]["code"] == expected_code
    if expected_status == 405:
        assert response.headers["Allow"] == "POST"


def test_concurrent_login_reserves_attempt_before_directory_io() -> None:
    class SlowDirectory(InMemoryUserDirectory):
        def find_by_username(self, username: str) -> UserAccount | None:
            sleep(0.05)
            return None

    service = AuthenticationSessionService(SlowDirectory(), (ORIGIN,), False)
    barrier = Barrier(8)

    def login_attempt(_: int) -> int:
        barrier.wait(timeout=5)
        try:
            service.login("missing-fixture", "synthetic-password", ORIGIN, "same-client")
        except LoginRateLimitedError:
            return 429
        except InvalidCredentialsError:
            return 401
        raise AssertionError("missing user unexpectedly logged in")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(login_attempt, range(8)))
    assert results.count(401) == 5
    assert results.count(429) == 3


def test_successful_login_releases_only_its_own_rate_reservation() -> None:
    service = AuthenticationSessionService(InMemoryUserDirectory(), (ORIGIN,), False)
    service.create_precreated_user("fixture-user", "synthetic-password", "tenant-a", Role.ANALYST)
    for _ in range(6):
        session, _ = service.login("fixture-user", "synthetic-password", ORIGIN, "same-client")
        service.logout(session)
    for _ in range(4):
        with pytest.raises(InvalidCredentialsError):
            service.login("missing-fixture", "synthetic-password", ORIGIN, "same-client")
    service.login("fixture-user", "synthetic-password", ORIGIN, "same-client")
    with pytest.raises(InvalidCredentialsError):
        service.login("missing-fixture", "synthetic-password", ORIGIN, "same-client")
    with pytest.raises(LoginRateLimitedError):
        service.login("fixture-user", "synthetic-password", ORIGIN, "same-client")


def test_me_reads_one_account_and_its_session_bound_csrf() -> None:
    class CountingDirectory(InMemoryUserDirectory):
        reads = 0

        def find_by_id(self, user_id: str) -> UserAccount | None:
            self.reads += 1
            return super().find_by_id(user_id)

    directory = CountingDirectory()
    service = AuthenticationSessionService(directory, (ORIGIN,), False)
    service.create_precreated_user("fixture-user", "synthetic-password", "tenant-a", Role.ANALYST)
    client = TestClient(
        create_application(
            service,
            settings=ApplicationSettings(
                app_env="test", data_mode="fixture", allowed_origins=(ORIGIN,)
            ),
        )
    )
    login = client.post(
        "/v1/auth/login",
        json={"username": "fixture-user", "password": "synthetic-password"},
        headers={"Origin": ORIGIN},
    )
    snapshot = client.get("/v1/auth/me")
    assert snapshot.json()["csrf_token"] == login.json()["csrf_token"]
    assert snapshot.json()["user_id"] == login.json()["user_id"]
    assert snapshot.json()["tenant_id"] == "tenant-a"
    assert directory.reads == 1
