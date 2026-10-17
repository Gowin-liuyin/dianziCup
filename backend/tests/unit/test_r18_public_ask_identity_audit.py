"""Default old and public question routes retain the same explicit fixture audit boundary."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from ai_intel.api.app import create_application
from ai_intel.api.authentication import AuthenticationSessionService, InMemoryUserDirectory
from ai_intel.infrastructure.settings import ApplicationSettings


@pytest.mark.parametrize("path", ["/v1/questions", "/api/v1/ask"])
def test_default_routes_audit_rejected_identity_names_without_values(path):
    authentication = AuthenticationSessionService(
        InMemoryUserDirectory(), ("http://localhost:5173",), False
    )
    submitted_value = "explicit-synthetic-identity-only"
    with TestClient(
        create_application(
            auth_service=authentication,
            settings=ApplicationSettings(app_env="test", data_mode="fixture"),
        )
    ) as client:
        response = client.post(
            path,
            json={
                "question": "fixture",
                "mode": "library",
                "tenant_id": submitted_value,
                "user_id": submitted_value,
                "role": submitted_value,
                "permissions": [submitted_value],
            },
            headers={
                "Authorization": "Bearer explicit-fixture",
                "Idempotency-Key": "fixture-identity-audit",
            },
        )
    assert response.status_code == 422
    events = authentication.audit_events()
    assert len(events) == 1
    assert events[0]["event_type"] == "identity_spoof_attempt"
    assert events[0]["submitted_keys"] == "permissions,role,tenant_id,user_id"
    assert submitted_value not in response.text
    assert submitted_value not in str(events)


def test_public_ask_audit_database_failure_is_explicit_and_does_not_answer(monkeypatch):
    authentication = AuthenticationSessionService(
        InMemoryUserDirectory(), ("http://localhost:5173",), False
    )

    def fail_record(_submitted):
        raise OperationalError("fixture audit failure", {}, RuntimeError("fixture failure"))

    monkeypatch.setattr(authentication, "record_identity_spoof_attempt", fail_record)
    with TestClient(
        create_application(
            auth_service=authentication,
            settings=ApplicationSettings(app_env="test", data_mode="fixture"),
        )
    ) as client:
        response = client.post(
            "/api/v1/ask",
            json={"question": "fixture", "mode": "library", "tenant_id": "fixture-only"},
            headers={
                "Authorization": "Bearer explicit-fixture",
                "Idempotency-Key": "fixture-audit",
            },
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "authentication_unavailable"
    assert response.headers["cache-control"] == "no-store"
    assert "answer_id" not in response.json()
