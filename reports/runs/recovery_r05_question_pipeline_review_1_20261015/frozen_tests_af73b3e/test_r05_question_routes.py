"""Explicit in-memory authentication fixture verifies question HTTP trust boundaries only."""

import secrets
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine

from ai_intel.api import app as application_module
from ai_intel.api import question_routes
from ai_intel.api.app import create_application
from ai_intel.api.auth_routes import CSRF_HEADER_NAME, SESSION_COOKIE_NAME
from ai_intel.api.authentication import AuthenticationSessionService, InMemoryUserDirectory
from ai_intel.domain.access import ROLE_PERMISSIONS, Role
from ai_intel.infrastructure.settings import ApplicationSettings

ORIGIN = "http://localhost:5173"


@pytest.fixture
def route_fixture(monkeypatch, register_sensitive_failure_value):
    """No SQL queries or generation: rejected requests must stop before the service boundary."""
    engine = create_engine("sqlite://")
    monkeypatch.setattr(application_module, "build_engine", lambda settings: engine)
    calls = []

    class FixtureQuestions:
        def ask(self, payload, scope_provider, key):
            calls.append(payload)
            raise AssertionError("a rejected request reached the question service")

    monkeypatch.setattr(
        question_routes, "build_question_service", lambda engine, settings: FixtureQuestions()
    )
    auth = AuthenticationSessionService(InMemoryUserDirectory(), (ORIGIN,), False)
    password = SecretStr(secrets.token_urlsafe(32))
    register_sensitive_failure_value(password)
    auth.create_precreated_user(
        "fixture-route-user", password.get_secret_value(), "tenant-a", Role.VIEWER
    )
    settings = ApplicationSettings(
        app_env="test", data_mode="fixture", database_url=SecretStr("sqlite://")
    )
    client = TestClient(create_application(auth, settings=settings))
    response = client.post(
        "/v1/auth/login",
        json={"username": "fixture-route-user", "password": password.get_secret_value()},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200
    register_sensitive_failure_value(SecretStr(client.cookies[SESSION_COOKIE_NAME]))
    register_sensitive_failure_value(SecretStr(response.json()["csrf_token"]))
    yield (
        client,
        auth,
        calls,
        {
            "question": "fixture route question",
            "event_ids": [str(uuid4())],
            "mode": "library",
        },
        {"Origin": ORIGIN, CSRF_HEADER_NAME: response.json()["csrf_token"]},
    )
    client.close()
    engine.dispose()


def assert_problem(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    assert response.headers["content-type"].startswith("application/problem+json")


def test_anonymous_post_and_get_are_401_on_both_default_prefixes(route_fixture):
    client, _, calls, payload, headers = route_fixture
    client.cookies.clear()
    for prefix in ("/v1", "/api/v1"):
        assert_problem(
            client.post(prefix + "/questions", json=payload, headers=headers),
            401,
            "session_expired",
        )
        assert_problem(client.get(prefix + "/answers/" + str(uuid4())), 401, "session_expired")
    assert calls == []


def test_csrf_token_and_origin_are_both_required_before_questions(route_fixture):
    client, _, calls, payload, headers = route_fixture
    for rejected in (
        {},
        {"Origin": ORIGIN},
        {CSRF_HEADER_NAME: headers[CSRF_HEADER_NAME]},
        {**headers, CSRF_HEADER_NAME: "fixture-wrong-csrf"},
        {**headers, "Origin": "https://untrusted.example"},
    ):
        assert_problem(
            client.post("/v1/questions", json=payload, headers=rejected), 403, "csrf_rejected"
        )
    assert calls == []


def test_missing_read_permission_stops_post_and_get(route_fixture, monkeypatch):
    client, _, calls, payload, headers = route_fixture
    monkeypatch.setitem(ROLE_PERMISSIONS, Role.VIEWER, frozenset())
    assert_problem(
        client.post("/v1/questions", json=payload, headers=headers), 403, "permission_denied"
    )
    assert_problem(client.get("/api/v1/answers/" + str(uuid4())), 403, "permission_denied")
    assert calls == []


def test_revoked_session_stops_post_and_get(route_fixture):
    client, auth, calls, payload, headers = route_fixture
    auth.logout(client.cookies[SESSION_COOKIE_NAME])
    assert_problem(
        client.post("/api/v1/questions", json=payload, headers=headers), 401, "session_expired"
    )
    assert_problem(client.get("/v1/answers/" + str(uuid4())), 401, "session_expired")
    assert calls == []


def test_question_body_cannot_supply_identity_or_echo_sensitive_input(route_fixture):
    client, _, calls, payload, headers = route_fixture
    spoofed = {**payload, "tenant_id": "fixture-foreign-tenant", "role": "system_admin"}
    response = client.post("/v1/questions", json=spoofed, headers=headers)
    assert_problem(response, 422, "validation_error")
    assert "fixture-foreign-tenant" not in response.text
    assert "system_admin" not in response.text
    assert calls == []


def test_config_missing_is_explicit_without_fallback_generation(register_sensitive_failure_value):
    settings = ApplicationSettings(app_env="test", data_mode="fixture")
    assert question_routes.build_question_service(None, settings) is None
    engine = create_engine("sqlite://")
    try:
        assert question_routes.build_question_service(engine, settings) is None
    finally:
        engine.dispose()
    auth = AuthenticationSessionService(InMemoryUserDirectory(), (ORIGIN,), False)
    password = SecretStr(secrets.token_urlsafe(32))
    register_sensitive_failure_value(password)
    auth.create_precreated_user(
        "fixture-no-database", password.get_secret_value(), "tenant-a", Role.VIEWER
    )
    with TestClient(create_application(auth, settings=settings)) as client:
        login = client.post(
            "/v1/auth/login",
            json={"username": "fixture-no-database", "password": password.get_secret_value()},
            headers={"Origin": ORIGIN},
        )
        assert login.status_code == 200
        register_sensitive_failure_value(SecretStr(client.cookies[SESSION_COOKIE_NAME]))
        register_sensitive_failure_value(SecretStr(login.json()["csrf_token"]))
        response = client.post(
            "/v1/questions",
            json={"question": "配置缺失", "event_ids": [str(uuid4())], "mode": "library"},
            headers={"Origin": ORIGIN, CSRF_HEADER_NAME: login.json()["csrf_token"]},
        )
        assert_problem(response, 503, "question_database_unavailable")
