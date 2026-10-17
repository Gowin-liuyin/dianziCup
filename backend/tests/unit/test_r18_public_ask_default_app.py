"""Default application routing and frozen request documentation without a database or model."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_intel.api import question_routes
from ai_intel.api.app import create_application
from ai_intel.infrastructure.settings import ApplicationSettings


def test_default_app_reuses_one_question_service_and_documents_exact_public_request(monkeypatch):
    calls = []

    def configured_questions(engine, settings):
        calls.append((engine, settings))
        return None

    monkeypatch.setattr(question_routes, "build_question_service", configured_questions)
    application = create_application(
        settings=ApplicationSettings(app_env="test", data_mode="fixture")
    )
    assert len(calls) == 1
    with TestClient(application) as client:
        response = client.post("/api/v1/ask", json={"question": "q", "mode": "library"})
    assert response.status_code == 401
    document = application.openapi()
    operation = document["paths"]["/api/v1/ask"]["post"]
    request = operation["requestBody"]
    contract_path = (
        Path(__file__).resolve().parents[3] / "contracts/schemas/public_api_extensions_v1.json"
    )
    expected = json.loads(contract_path.read_text(encoding="utf-8"))["$defs"]["AskRequest"]
    assert request["required"] is True
    assert request["content"]["application/json"]["schema"] == expected
    assert any(
        parameter["in"] == "header"
        and parameter["name"] == "Idempotency-Key"
        and parameter["required"]
        for parameter in operation["parameters"]
    )


@pytest.mark.parametrize(
    "body",
    [
        b'{"question":"q"}',
        b'{"question":"q","mode":"library","conversation_id":null}',
        b'{"question":"q","mode":"library","event_ids":["invalid"]}',
        b'{"question":"q","mode":"library","mode":"auto"}',
        b'{"question":"q","mode":"library","x":' + b"[" * 20000 + b"0" + b"]" * 20000 + b"}",
    ],
    ids=["missing_mode", "null_conversation", "invalid_uuid", "duplicate_mode", "deep_json"],
)
def test_default_public_ask_rejects_invalid_inputs_before_database_or_generation(body):
    settings = ApplicationSettings(app_env="test", data_mode="fixture")
    with TestClient(create_application(settings=settings)) as client:
        response = client.post(
            "/api/v1/ask",
            content=body,
            headers={
                "Authorization": "Bearer explicit-synthetic-fixture-only",
                "Content-Type": "application/json",
                "Idempotency-Key": "explicit-fixture-request",
            },
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "suffix,headers",
    [
        ("", {}),
        ("?access_token=explicit-fixture", {"Authorization": "Bearer explicit-fixture"}),
        (
            "",
            {
                "Authorization": "Bearer explicit-fixture",
                "Cookie": "ai_intel_session=explicit-fixture",
            },
        ),
    ],
)
def test_default_public_ask_rejects_missing_or_mixed_credentials(suffix, headers):
    settings = ApplicationSettings(app_env="test", data_mode="fixture")
    with TestClient(create_application(settings=settings)) as client:
        response = client.post(
            "/api/v1/ask" + suffix,
            json={"question": "q", "mode": "library"},
            headers={**headers, "Idempotency-Key": "explicit-fixture-request"},
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"
    assert response.headers["cache-control"] == "no-store"


def test_default_public_ask_has_explicit_database_failure_without_a_fake_answer():
    settings = ApplicationSettings(app_env="test", data_mode="fixture")
    with TestClient(create_application(settings=settings)) as client:
        response = client.post(
            "/api/v1/ask",
            json={"question": "q", "mode": "library"},
            headers={
                "Authorization": "Bearer explicit-fixture",
                "Idempotency-Key": "explicit-fixture-request",
            },
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "question_database_unavailable"
    assert "answer_id" not in response.json()
