"""Real isolated PG public HTTP lifecycle; model and semantic IO remain explicit fixtures."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select, update
from test_r05_question_api_pg import question_api as question_api
from test_r18_question_credential_pg import vector_database as vector_database

from ai_intel.answering import service as question_service
from ai_intel.api.auth_routes import CSRF_HEADER_NAME, SESSION_COOKIE_NAME
from ai_intel.api.credential_models import api_key_rate_buckets, api_keys
from ai_intel.api.credentials import ApiKeyRateLimitedError, PgApiKeyService, SessionCredential
from ai_intel.api.public_ask_routes import build_public_ask_router
from ai_intel.api.question_contracts import QuestionAnswerResponse
from ai_intel.domain.access import READ_PUBLIC
from ai_intel.knowledge.models import evidence, scope_epochs
from ai_intel.retrieval.persistence_models import grounded_answers

pytestmark = pytest.mark.real_pg


@pytest.fixture
def public_ask_pg(question_api, register_sensitive_failure_value):
    api = question_api
    api["client"].app.include_router(
        build_public_ask_router(lambda: api["auth"], api["engine"], api["settings"]),
        prefix="/api/v1",
    )
    session = SessionCredential(SecretStr(api["client"].cookies[SESSION_COOKIE_NAME]))
    issued = PgApiKeyService(api["engine"]).issue_key(session, frozenset({READ_PUBLIC}))
    register_sensitive_failure_value(issued.token)
    api["session"] = session
    api["key"] = issued
    api["key_headers"] = {
        "Authorization": "Bearer " + issued.token.get_secret_value(),
        "Idempotency-Key": "fixture-public-pg-ask",
    }
    api["client"].cookies.clear()
    return api


def submit(api, *, payload=None, headers=None, client=None):
    return (client or api["client"]).post(
        "/api/v1/ask", json=payload or api["payload"], headers=headers or api["key_headers"]
    )


def usage(api, key_id=None):
    with api["engine"].connect() as connection:
        return connection.scalar(
            select(func.coalesce(func.sum(api_key_rate_buckets.c.request_count), 0)).where(
                api_key_rate_buckets.c.key_id == (key_id or api["key"].metadata.key_id),
                api_key_rate_buckets.c.operation == "ask",
            )
        )


def rows(api):
    with api["engine"].connect() as connection:
        return [dict(row) for row in connection.execute(select(grounded_answers)).mappings()]


def test_public_new_replay_conflict_and_old_cookie_read_share_one_answer_and_quota(public_ask_pg):
    api = public_ask_pg
    response = submit(api)
    assert response.status_code == 200, response.text
    answer = QuestionAnswerResponse.model_validate_json(response.content)
    assert answer.data_mode == "fixture" and answer.citations and answer.claims
    assert len(api["wire"].calls) == 2 and usage(api) == 1
    persisted = rows(api)
    replay = submit(api)
    assert replay.status_code == 200 and replay.json() == response.json()
    conflict = submit(api, payload={**api["payload"], "question": "另一公开问题"})
    assert (
        conflict.status_code == 409 and conflict.json()["error"]["code"] == "idempotency_conflict"
    )
    assert usage(api) == 1 and rows(api) == persisted and len(api["wire"].calls) == 2
    old_read = api["client"].get(
        "/api/v1/answers/" + str(answer.answer_id),
        headers={"Cookie": SESSION_COOKIE_NAME + "=" + api["session"].token.get_secret_value()},
    )
    assert old_read.status_code == 200 and old_read.json() == response.json()


def test_real_quota_failure_rolls_back_new_answer_and_count(public_ask_pg, monkeypatch):
    api = public_ask_pg
    original = question_service.consume_api_key_rate_limit

    def fail_after_reservation(connection, credential, now, *, operation):
        assert operation == "ask" and connection.in_transaction()
        assert connection.scalar(select(func.count()).select_from(grounded_answers)) == 1
        original(connection, credential, now, operation=operation)
        raise ApiKeyRateLimitedError(17)

    monkeypatch.setattr(question_service, "consume_api_key_rate_limit", fail_after_reservation)
    response = submit(api)
    assert response.status_code == 429 and response.headers["Retry-After"] == "17"
    assert response.json()["error"]["code"] == "rate_limited"
    assert usage(api) == 0 and rows(api) == [] and api["wire"].calls == []


def test_real_expired_reservation_uses_stable_public_alias_and_rolls_back(
    public_ask_pg, monkeypatch
):
    api = public_ask_pg
    monkeypatch.setattr(question_service, "ANSWER_RESERVATION_SECONDS", -1)
    response = submit(api)
    assert response.status_code == 409 and response.json()["error"]["code"] == "answer_failed"
    assert "answer_lease_expired" not in response.text
    assert usage(api) == 0 and rows(api) == [] and api["wire"].calls == []


@pytest.mark.parametrize("change", ["revoked", "expired"])
def test_current_key_invalid_before_submission_has_no_answer_or_io(public_ask_pg, change):
    api = public_ask_pg
    with api["engine"].begin() as connection:
        connection.execute(
            update(api_keys)
            .where(api_keys.c.key_id == api["key"].metadata.key_id)
            .values(**{"revoked_at" if change == "revoked" else "expires_at": datetime.now(UTC)})
        )
    response = submit(api)
    assert response.status_code == 401 and response.json()["error"]["code"] == "unauthenticated"
    assert usage(api) == 0 and rows(api) == [] and api["wire"].calls == []


def test_revocation_during_model_io_denies_publication_and_retains_real_attempts(public_ask_pg):
    api = public_ask_pg

    def revoke():
        PgApiKeyService(api["engine"]).revoke_key(api["session"], api["key"].metadata.key_id)

    api["wire"].before_verification = revoke
    response = submit(api)
    assert response.status_code == 401 and response.json()["error"]["code"] == "unauthenticated"
    assert usage(api) == 1 and rows(api)[0]["response"]["kind"] == "failed"
    assert rows(api)[0]["model_trace"]["attempts"] and len(api["wire"].calls) == 2


def test_two_owners_same_idempotency_key_have_distinct_answers_and_no_cross_read(
    public_ask_pg, register_sensitive_failure_value
):
    api = public_ask_pg
    first = submit(api)
    assert first.status_code == 200
    other, _identity = api["login"](tenant="fixture-other-tenant")
    other_session = SessionCredential(SecretStr(other.cookies[SESSION_COOKIE_NAME]))
    issued = PgApiKeyService(api["engine"]).issue_key(other_session, frozenset({READ_PUBLIC}))
    register_sensitive_failure_value(issued.token)
    other.cookies.clear()
    second = submit(
        api,
        client=other,
        headers={
            **api["key_headers"],
            "Authorization": "Bearer " + issued.token.get_secret_value(),
        },
    )
    assert second.status_code == 200 and second.json()["answer_id"] != first.json()["answer_id"]
    assert len(rows(api)) == 2 and usage(api) == 1 and usage(api, issued.metadata.key_id) == 1
    denied = other.get(
        "/api/v1/answers/" + first.json()["answer_id"],
        headers={"Cookie": SESSION_COOKIE_NAME + "=" + other_session.token.get_secret_value()},
    )
    assert denied.status_code == 404 and "answer_text" not in denied.json()


def test_cookie_current_origin_csrf_and_factory_produce_same_public_dto(public_ask_pg):
    api = public_ask_pg
    response = submit(
        api,
        headers={
            "Cookie": SESSION_COOKIE_NAME + "=" + api["session"].token.get_secret_value(),
            "Origin": api["headers"]["Origin"],
            CSRF_HEADER_NAME: api["identity"]["csrf_token"],
            "Idempotency-Key": "fixture-public-cookie-ask",
        },
    )
    assert response.status_code == 200
    answer = QuestionAnswerResponse.model_validate_json(response.content)
    assert answer.citations and answer.data_mode == "fixture"
    assert usage(api) == 0 and len(api["wire"].calls) == 2


@pytest.mark.parametrize("change", ["epoch", "integrity"])
def test_current_evidence_change_is_rechecked_on_replay_without_more_model_io(
    public_ask_pg, change
):
    api = public_ask_pg
    first = submit(api)
    assert first.status_code == 200
    identifier = first.json()["citations"][0]["evidence_id"]
    with api["engine"].begin() as connection:
        if change == "epoch":
            connection.execute(update(scope_epochs).values(epoch=scope_epochs.c.epoch + 1))
        else:
            connection.execute(
                update(evidence)
                .where(evidence.c.evidence_id == identifier)
                .values(verified_at=None)
            )
    replay = submit(api)
    if change == "epoch":
        assert replay.status_code == 200 and replay.json()["freshness"] == "stale"
    else:
        assert replay.status_code == 503
        assert replay.json()["error"]["code"] == "answer_evidence_integrity_unavailable"
        assert "answer_text" not in replay.json()
    assert len(api["wire"].calls) == 2 and usage(api) == 1


def test_independent_route_instances_pending_replay_do_not_double_charge(public_ask_pg):
    api = public_ask_pg
    reached, release = Event(), Event()

    def pause():
        reached.set()
        assert release.wait(10)

    api["wire"].before_verification = pause
    app = FastAPI()
    app.include_router(
        build_public_ask_router(lambda: api["auth"], api["engine"], api["settings"]),
        prefix="/api/v1",
    )
    with TestClient(app) as second_client, ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(submit, api)
        try:
            assert reached.wait(10)
            pending = submit(api, client=second_client)
            assert pending.status_code == 409
            assert pending.json()["error"]["code"] == "answer_in_progress"
            assert len(rows(api)) == 1 and usage(api) == 1
        finally:
            release.set()
        completed = first.result(timeout=10)
    assert completed.status_code == 200 and usage(api) == 1 and len(api["wire"].calls) == 2


@pytest.mark.parametrize(
    "updates",
    [
        {"event_ids": []},
        {
            "event_ids": [
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
            ]
        },
        {"asset_ids": ["00000000-0000-0000-0000-000000000001"]},
        {"conversation_id": "00000000-0000-0000-0000-000000000001"},
        {"known_at": "2026-10-17T00:00:00Z"},
        {"valid_at": "2026-10-17T00:00:00Z"},
        {"mode": "investigate"},
    ],
)
def test_unsupported_async_or_historical_scope_preserves_real_service_gap(public_ask_pg, updates):
    api = public_ask_pg
    response = submit(api, payload={**api["payload"], **updates})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "question_scope_not_supported"
    assert usage(api) == 0 and rows(api) == [] and api["wire"].calls == []
