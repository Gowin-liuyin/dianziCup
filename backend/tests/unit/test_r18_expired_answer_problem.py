"""Expired-answer HTTP failures retain the public code without changing the internal cause."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine

from ai_intel.answering.service import QuestionFailure
from ai_intel.api import app as application_module
from ai_intel.api import question_routes
from ai_intel.api.app import create_application
from ai_intel.api.auth_routes import CSRF_HEADER_NAME
from ai_intel.api.authentication import AuthenticationSessionService, InMemoryUserDirectory
from ai_intel.domain.access import Role
from ai_intel.infrastructure.settings import ApplicationSettings

ORIGIN = "http://localhost:5173"


@pytest.mark.parametrize("prefix", ["/v1", "/api/v1"])
@pytest.mark.parametrize(
    ("internal_code", "public_code"),
    [("answer_lease_expired", "answer_failed"), ("question_model_failed", "question_model_failed")],
)
def test_question_failure_preserves_stable_public_problem(
    monkeypatch, prefix, internal_code, public_code, register_sensitive_failure_value
):
    engine = create_engine("sqlite://")
    monkeypatch.setattr(application_module, "build_engine", lambda settings: engine)

    class FixtureExpiredQuestion:
        """Only the HTTP error mapping is exercised; no model or SQL request is performed."""

        def ask(self, payload, scope_provider, key, *, session_token):
            scope_provider()
            raise QuestionFailure(internal_code, 409)

    monkeypatch.setattr(
        question_routes, "build_question_service", lambda engine, settings: FixtureExpiredQuestion()
    )
    authentication = AuthenticationSessionService(InMemoryUserDirectory(), (ORIGIN,), False)
    password = SecretStr(str(uuid4()))
    register_sensitive_failure_value(password)
    authentication.create_precreated_user(
        "fixture-expired-answer-user", password.get_secret_value(), "tenant-a", Role.VIEWER
    )
    settings = ApplicationSettings(
        app_env="test", data_mode="fixture", database_url=SecretStr("sqlite://")
    )
    try:
        with TestClient(create_application(authentication, settings=settings)) as client:
            login = client.post(
                "/v1/auth/login",
                json={
                    "username": "fixture-expired-answer-user",
                    "password": password.get_secret_value(),
                },
                headers={"Origin": ORIGIN},
            )
            assert login.status_code == 200
            response = client.post(
                prefix + "/questions",
                json={
                    "question": "fixture expired answer",
                    "event_ids": [str(uuid4())],
                    "mode": "library",
                },
                headers={"Origin": ORIGIN, CSRF_HEADER_NAME: login.json()["csrf_token"]},
            )
            assert response.status_code == 409
            assert response.json()["error"]["code"] == public_code
            assert response.headers["content-type"].startswith("application/problem+json")
    finally:
        engine.dispose()
