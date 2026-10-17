"""Explicit fixture HTTP boundaries; SQLite and service doubles cannot prove PG authorization."""

import json
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError

from ai_intel.answering.service import QuestionFailure
from ai_intel.api import public_ask_routes
from ai_intel.api.actor_references import actor_reference_from_payload
from ai_intel.api.auth_routes import CSRF_HEADER_NAME, SESSION_COOKIE_NAME
from ai_intel.api.authentication import AuthenticationSessionService, InMemoryUserDirectory
from ai_intel.api.credentials import (
    ApiKeyCredential,
    ApiKeyRateLimitedError,
    InvalidApiKeyError,
    SessionCredential,
)
from ai_intel.api.question_contracts import QuestionAnswerResponse
from ai_intel.domain.access import CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.infrastructure.settings import ApplicationSettings

ORIGIN = "http://localhost:5173"
STAMP = datetime(2026, 10, 17, tzinfo=UTC)
PAYLOAD = {"question": "公开证据是什么？", "event_ids": [str(UUID(int=1))], "mode": "library"}


def fixture_answer():
    identifier = str(UUID(int=2))
    return QuestionAnswerResponse.model_validate(
        {
            "kind": "completed",
            "answer_id": str(UUID(int=3)),
            "answer_text": "合成来源引文",
            "claims": [
                {"text": "合成来源引文", "kind": "source_fact", "support_ids": [identifier]}
            ],
            "citations": [
                {
                    "evidence_id": identifier,
                    "revision_id": str(UUID(int=4)),
                    "quote": "合成来源引文",
                    "locator": "block:1[0:6]",
                    "source_uri": "https://example.com/fixture",
                }
            ],
            "limitations": ["explicit unit fixture only"],
            "freshness": "current",
            "data_mode": "fixture",
            "started_at": STAMP,
            "completed_at": STAMP,
            "latency_milliseconds": 0,
        }
    )


@pytest.fixture
def public_ask_case(monkeypatch, register_sensitive_failure_value):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    state = {"active": 0, "auth_calls": [], "service_calls": [], "error": None, "auth_error": None}

    @event.listens_for(engine, "begin")
    def opened(connection):
        state["active"] += 1

    @event.listens_for(engine, "commit")
    @event.listens_for(engine, "rollback")
    def closed(connection):
        state["active"] -= 1

    auth = AuthenticationSessionService(InMemoryUserDirectory(), (ORIGIN,), False)
    password = secrets.token_urlsafe(32)
    register_sensitive_failure_value(SecretStr(password))
    auth.create_precreated_user("fixture-public-ask", password, "fixture-tenant", Role.VIEWER)
    session_token, session = auth.login("fixture-public-ask", password, ORIGIN, "fixture-client")
    key_token = secrets.token_urlsafe(32)
    for value in (session_token, session.csrf_token, key_token):
        register_sensitive_failure_value(SecretStr(value))
    scope = auth.build_access_scope(session_token)

    def lock_principal(connection, credential, now):
        assert connection.in_transaction() and state["active"] == 1
        assert now == STAMP
        state["auth_calls"].append(credential)
        if state["auth_error"] is not None:
            raise state["auth_error"]
        return scope

    def actor_factory(connection, credential, now):
        import hashlib

        is_key = isinstance(credential, ApiKeyCredential)
        return actor_reference_from_payload(
            {
                "credential_kind": "api_key" if is_key else "session",
                "user_id": scope.user_id,
                "tenant_id": scope.tenant_id,
                "role": scope.role.value,
                "permissions": sorted(scope.permissions),
                "permission_version": scope.permission_version,
                "permissions_digest": hashlib.sha256(
                    json.dumps(sorted(scope.permissions), separators=(",", ":")).encode()
                ).hexdigest(),
                "resource": "urn:dianzi:api:v1",
                "issued_at": STAMP.isoformat(),
                "created_at": STAMP.isoformat(),
                "session_hash": None
                if is_key
                else hashlib.sha256(session_token.encode()).hexdigest(),
                "key_id": str(UUID(int=5)) if is_key else None,
                "credential_version": 1 if is_key else None,
            }
        )

    class FixtureQuestions:
        def ask(self, payload, scope_provider, key, *, session_token, credential):
            assert state["active"] == 0
            state["service_calls"].append((payload, key, session_token, credential))
            assert scope_provider() == scope
            assert state["active"] == 0
            assert scope_provider() == scope
            assert state["active"] == 0
            if state["error"] is not None:
                raise state["error"]
            return fixture_answer()

    monkeypatch.setattr(public_ask_routes, "_database_now", lambda connection: STAMP)
    monkeypatch.setattr(public_ask_routes, "lock_authenticated_principal", lock_principal)
    monkeypatch.setattr(public_ask_routes, "create_actor_reference", actor_factory)
    monkeypatch.setattr(
        public_ask_routes, "build_question_service", lambda engine, settings: FixtureQuestions()
    )
    app = FastAPI()
    settings = ApplicationSettings(app_env="test", data_mode="fixture")
    app.include_router(public_ask_routes.build_public_ask_router(lambda: auth, engine, settings))
    with TestClient(app) as client:
        yield {
            "client": client,
            "auth": auth,
            "engine": engine,
            "state": state,
            "session_token": session_token,
            "key_token": key_token,
            "cookie_headers": {
                "Cookie": SESSION_COOKIE_NAME + "=" + session_token,
                "Origin": ORIGIN,
                CSRF_HEADER_NAME: session.csrf_token,
                "Idempotency-Key": "fixture-public-ask",
            },
            "key_headers": {
                "Authorization": "Bearer " + key_token,
                "Idempotency-Key": "fixture-public-ask",
            },
            "scope": scope,
        }
    engine.dispose()


def assert_problem(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("kind", ["cookie", "key"])
def test_shared_service_receives_current_actor_and_same_credential_outside_transaction(
    public_ask_case, kind
):
    case = public_ask_case
    response = case["client"].post("/ask", json=PAYLOAD, headers=case[kind + "_headers"])
    assert response.status_code == 200
    assert response.json() == fixture_answer().model_dump(mode="json")
    assert response.headers["cache-control"] == "no-store"
    calls = case["state"]["auth_calls"]
    assert len(calls) == 3 and all(credential is calls[0] for credential in calls)
    payload, key, actor, credential = case["state"]["service_calls"][0]
    assert str(payload.event_ids[0]) == PAYLOAD["event_ids"][0]
    assert key == "fixture-public-ask" and credential is calls[0]
    assert isinstance(credential, SessionCredential if kind == "cookie" else ApiKeyCredential)
    assert actor.user_id == case["scope"].user_id and actor.tenant_id == "fixture-tenant"
    assert actor.credential_kind == ("session" if kind == "cookie" else "api_key")
    assert case["session_token"] not in response.text and case["key_token"] not in response.text
    capture = os.environ.get("PUBLIC_ASK_WIRE_CAPTURE")
    if capture and kind == "key":
        Path(capture).write_text(response.text, encoding="utf-8")


@pytest.mark.parametrize(
    "omitted", ["Origin", CSRF_HEADER_NAME, "both", "foreign_origin", "wrong_csrf"]
)
def test_cookie_origin_and_csrf_reject_before_pg_or_model(public_ask_case, omitted):
    headers = dict(public_ask_case["cookie_headers"])
    if omitted == "both":
        headers.pop("Origin")
        headers.pop(CSRF_HEADER_NAME)
    elif omitted == "foreign_origin":
        headers["Origin"] = "https://example.com/foreign"
    elif omitted == "wrong_csrf":
        headers[CSRF_HEADER_NAME] = "fixture-wrong-csrf"
    else:
        headers.pop(omitted)
    assert_problem(
        public_ask_case["client"].post("/ask", json=PAYLOAD, headers=headers), 403, "csrf_rejected"
    )
    assert public_ask_case["state"]["auth_calls"] == []


@pytest.mark.parametrize("header", ["Origin", CSRF_HEADER_NAME])
def test_duplicate_cookie_write_headers_fail_closed(public_ask_case, header):
    headers = list(public_ask_case["cookie_headers"].items())
    headers.append((header, public_ask_case["cookie_headers"][header]))
    assert_problem(
        public_ask_case["client"].post("/ask", json=PAYLOAD, headers=headers), 403, "csrf_rejected"
    )
    assert public_ask_case["state"]["service_calls"] == []


@pytest.mark.parametrize(
    "scenario",
    [
        "anonymous",
        "duplicate_authorization",
        "mixed",
        "duplicate_cookie",
        "bad_scheme",
        "query_key",
    ],
)
def test_ambiguous_or_query_credentials_fail_closed(public_ask_case, scenario):
    case = public_ask_case
    headers = list(case["key_headers"].items())
    path = "/ask"
    if scenario == "anonymous":
        headers = [("Idempotency-Key", "fixture-key")]
    elif scenario == "duplicate_authorization":
        headers.append(("Authorization", case["key_headers"]["Authorization"]))
    elif scenario == "mixed":
        headers.append(("Cookie", case["cookie_headers"]["Cookie"]))
    elif scenario == "duplicate_cookie":
        headers = list(case["cookie_headers"].items())
        headers.append(("Cookie", case["cookie_headers"]["Cookie"]))
    elif scenario == "bad_scheme":
        headers[0] = ("Authorization", "Basic fixture-credential")
    else:
        path += "?api_key=fixture-query-credential"
    response = case["client"].post(path, json=PAYLOAD, headers=headers)
    assert_problem(response, 401, "unauthenticated")
    assert "fixture-query-credential" not in response.text
    assert case["state"]["auth_calls"] == [] and case["state"]["service_calls"] == []


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (InvalidApiKeyError("private auth detail"), 401, "unauthenticated"),
        (ApiKeyRateLimitedError(37), 429, "rate_limited"),
        (PermissionDeniedError("private role detail"), 403, "permission_denied"),
        (CrossTenantAccessError("private owner detail"), 404, "not_found"),
        (QuestionFailure("answer_lease_expired", 409), 409, "answer_failed"),
        (QuestionFailure("idempotency_conflict", 409), 409, "idempotency_conflict"),
        (QuestionFailure("question_scope_not_supported", 422), 422, "question_scope_not_supported"),
        (QuestionFailure("question_capacity_busy", 429), 429, "question_capacity_busy"),
        (
            OperationalError("private SQL", {}, Exception("private DB detail")),
            503,
            "question_database_unavailable",
        ),
    ],
)
def test_shared_errors_preserve_public_categories_without_sensitive_detail(
    public_ask_case, error, status, code
):
    case = public_ask_case
    case["state"]["error"] = error
    response = case["client"].post("/ask", json=PAYLOAD, headers=case["key_headers"])
    assert_problem(response, status, code)
    assert "private" not in response.text and "answer_lease_expired" not in response.text
    if isinstance(error, ApiKeyRateLimitedError):
        assert response.headers["retry-after"] == "37"
    assert case["state"]["active"] == 0


def test_real_factory_missing_database_or_models_is_explicit(monkeypatch, public_ask_case):
    case = public_ask_case
    from ai_intel.api.question_routes import build_question_service

    monkeypatch.setattr(public_ask_routes, "build_question_service", build_question_service)
    settings = ApplicationSettings(app_env="test", data_mode="fixture")
    for engine, code in (
        (None, "question_database_unavailable"),
        (case["engine"], "question_models_not_configured"),
    ):
        app = FastAPI()
        app.include_router(
            public_ask_routes.build_public_ask_router(lambda: case["auth"], engine, settings)
        )
        with TestClient(app) as client:
            assert_problem(
                client.post("/ask", json=PAYLOAD, headers=case["key_headers"]), 503, code
            )
    assert case["state"]["service_calls"] == []
