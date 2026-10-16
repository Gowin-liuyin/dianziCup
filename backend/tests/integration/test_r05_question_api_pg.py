"""Real isolated PG/API lifecycle with explicitly synthetic semantic vectors and model wire."""

import json
import secrets
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select, text, update
from test_r05_vector_persistence import FixtureSemanticModels, public_event_id
from test_r05_vector_persistence import vector_database as vector_database

from ai_intel.api import app as application_module
from ai_intel.api import question_routes
from ai_intel.api.app import create_application
from ai_intel.api.auth_routes import CSRF_HEADER_NAME, SESSION_COOKIE_NAME
from ai_intel.api.auth_state import PgAuthenticationStateStore
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.domain.access import ROLE_PERMISSIONS, Role
from ai_intel.infrastructure.network import FetchResult, NetworkGateway
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.knowledge.models import document_revisions, evidence, scope_epochs, users
from ai_intel.knowledge.persistence_models import claims, events
from ai_intel.retrieval.persistence_models import grounded_answers
from ai_intel.retrieval.service import EventEvidenceRetriever

pytestmark = pytest.mark.real_pg
ORIGIN = "http://localhost:5173"


class FixtureGenerationWire:
    """Exercise the real GenerationClient codecs, validators and attempt metadata without IO."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.before_verification: Callable[[], None] | None = None
        self.failure_status: int | None = None

    def respond(self, url: str, body: bytes) -> FetchResult:
        submitted = json.loads(body)
        self.calls.append(submitted)
        if self.failure_status is not None:
            return FetchResult(url, self.failure_status, "application/json", b"{}")
        content = json.loads(submitted["messages"][1]["content"])
        supplied = [json.loads(item) for item in content["untrusted_evidence"]]
        if "claims_to_verify" in supplied[-1]:
            if self.before_verification is not None:
                self.before_verification()
            output = {
                "verdicts": [
                    {
                        "claim_index": 1,
                        "verdict": "supported",
                        "numbers_match": True,
                        "states_preserved": True,
                        "suggestion_only": False,
                    }
                ]
            }
        else:
            selected = supplied[0]
            output = {
                "claims": [
                    {
                        "text": selected["quote"],
                        "kind": "source_fact",
                        "support_ids": [selected["evidence_id"]],
                    }
                ],
                "citations": [{"evidence_id": selected["evidence_id"], "quote": selected["quote"]}],
            }
        payload = {
            "id": "synthetic-question-call-" + str(len(self.calls)),
            "object": "chat.completion",
            "model": "deepseek-flash",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(output, ensure_ascii=False),
                    },
                }
            ],
        }
        return FetchResult(url, 200, "application/json", json.dumps(payload).encode())


@pytest.fixture
def question_api(vector_database, monkeypatch, tmp_path, register_sensitive_failure_value):
    """Use default app PG authentication and service assembly; patch only isolated IO edges."""
    wire = FixtureGenerationWire()
    monkeypatch.setattr(application_module, "build_engine", lambda settings: vector_database)
    monkeypatch.setattr(
        question_routes, "LocalSemanticModels", lambda directory: FixtureSemanticModels()
    )

    def fixture_post(gateway, url, body, *, protocol_headers, deadline):
        return wire.respond(url, body)

    monkeypatch.setattr(NetworkGateway, "post_json", fixture_post)
    settings = ApplicationSettings(
        app_env="test",
        data_mode="fixture",
        allowed_origins=(ORIGIN,),
        database_url=SecretStr(vector_database.url.render_as_string(hide_password=False)),
        generation_api_key=SecretStr("synthetic-question-wire-only-credential"),
        semantic_model_cache_directory=tmp_path,
    )
    auth = AuthenticationSessionService(
        DatabaseUserDirectory(vector_database),
        (ORIGIN,),
        False,
        state_store=PgAuthenticationStateStore(vector_database),
    )
    application = create_application(settings=settings)
    instances = []

    def login(tenant="tenant-a", role=Role.VIEWER, app=application):
        username = "fixture-question-" + uuid4().hex
        password = SecretStr(secrets.token_urlsafe(32))
        register_sensitive_failure_value(password)
        auth.create_precreated_user(username, password.get_secret_value(), tenant, role)
        client = TestClient(app)
        response = client.post(
            "/v1/auth/login",
            json={"username": username, "password": password.get_secret_value()},
            headers={"Origin": ORIGIN},
        )
        assert response.status_code == 200
        register_sensitive_failure_value(SecretStr(client.cookies[SESSION_COOKIE_NAME]))
        register_sensitive_failure_value(SecretStr(response.json()["csrf_token"]))
        instances.append(client)
        return client, response.json()

    client, identity = login()
    yield {
        "engine": vector_database,
        "wire": wire,
        "settings": settings,
        "auth": auth,
        "client": client,
        "identity": identity,
        "login": login,
        "payload": {
            "question": "请给出这个事件的来源事实",
            "event_ids": [str(public_event_id(vector_database))],
            "mode": "library",
        },
        "headers": {
            "Origin": ORIGIN,
            CSRF_HEADER_NAME: identity["csrf_token"],
            "Idempotency-Key": "fixture-question-" + uuid4().hex,
        },
    }
    for instance in instances:
        instance.close()


def post_question(api, *, prefix="/v1", key=None, payload=None):
    headers = dict(api["headers"])
    if key is not None:
        headers["Idempotency-Key"] = key
    return api["client"].post(
        prefix + "/questions", json=payload or api["payload"], headers=headers
    )


def stored_answer(api):
    with api["engine"].connect() as connection:
        return connection.execute(select(grounded_answers)).mappings().one()


def assert_problem(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


@pytest.mark.parametrize("prefix", ["/v1", "/api/v1"])
def test_default_application_post_get_citations_and_restart(question_api, prefix):
    api = question_api
    response = post_question(api, prefix=prefix)
    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer["kind"] == "completed" and answer["data_mode"] == "fixture"
    assert answer["freshness"] == "current" and answer["limitations"]
    assert answer["latency_milliseconds"] >= 0
    assert len(api["wire"].calls) == 2
    assert answer["claims"][0]["support_ids"] == [answer["citations"][0]["evidence_id"]]
    citation = answer["citations"][0]
    quoted = api["client"].get(prefix + "/evidence/" + citation["evidence_id"])
    assert quoted.status_code == 200
    assert citation["quote"] in quoted.json()["quote_text"]
    assert quoted.json()["revision_id"] == citation["revision_id"]
    persisted = stored_answer(api)
    assert persisted["response"] == answer
    assert len(persisted["model_trace"]["attempts"]) == 2
    assert persisted["model_trace"]["fee"] == "unknown"
    restarted = TestClient(create_application(settings=api["settings"]))
    restarted.cookies.update(api["client"].cookies)
    try:
        assert restarted.get(prefix + "/answers/" + answer["answer_id"]).json() == answer
    finally:
        restarted.close()
    assert len(api["wire"].calls) == 2


def test_same_key_replay_and_conflicting_body_do_not_repeat_generation(question_api):
    api = question_api
    first = post_question(api, key="fixture-replay")
    assert first.status_code == 200, first.text
    second = post_question(api, prefix="/api/v1", key="fixture-replay")
    assert second.json() == first.json()
    conflict = post_question(
        api, key="fixture-replay", payload={**api["payload"], "question": "另一个问题"}
    )
    assert_problem(conflict, 409, "idempotency_conflict")
    assert len(api["wire"].calls) == 2
    with api["engine"].connect() as connection:
        assert connection.scalar(select(func.count()).select_from(grounded_answers)) == 1


def test_missing_empty_or_invalid_key_is_rejected_before_pg_and_generation(question_api):
    api = question_api
    authenticated_headers = {
        "Origin": ORIGIN,
        CSRF_HEADER_NAME: api["identity"]["csrf_token"],
    }
    for prefix in ("/v1", "/api/v1"):
        for key in (None, "", "fixture invalid key", "k" * 201):
            headers = dict(authenticated_headers)
            if key is not None:
                headers["Idempotency-Key"] = key
            response = api["client"].post(
                prefix + "/questions", json=api["payload"], headers=headers
            )
            assert_problem(response, 422, "invalid_key")
            assert api["wire"].calls == []
            with api["engine"].connect() as connection:
                assert connection.scalar(select(func.count()).select_from(grounded_answers)) == 0


def test_concurrent_same_key_has_one_pending_row_and_one_generation(question_api):
    api = question_api
    reached = Event()
    release = Event()

    def block_verification():
        reached.set()
        assert release.wait(10), "fixture concurrency barrier timed out"

    api["wire"].before_verification = block_verification
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(post_question, api, key="fixture-concurrent")
        try:
            assert reached.wait(10), "generation did not reach fixture barrier"
            pending = stored_answer(api)
            assert pending["response"] == {"kind": "pending"}
            restarted = TestClient(create_application(settings=api["settings"]))
            restarted.cookies.update(api["client"].cookies)
            try:
                response = restarted.get("/v1/answers/" + pending["answer_id"])
                assert_problem(response, 409, "answer_in_progress")
                repeated = restarted.post(
                    "/api/v1/questions",
                    json=api["payload"],
                    headers={**api["headers"], "Idempotency-Key": "fixture-concurrent"},
                )
                assert_problem(repeated, 409, "answer_in_progress")
            finally:
                restarted.close()
        finally:
            release.set()
        completed = future.result(timeout=15)
    assert completed.status_code == 200, completed.text
    assert stored_answer(api)["response"]["kind"] == "completed"
    assert len(api["wire"].calls) == 2


@pytest.mark.parametrize("change", ["no_evidence", "withdrawn", "noncurrent"])
def test_no_current_support_fails_before_generation(question_api, change):
    api = question_api
    with api["engine"].begin() as connection:
        if change == "no_evidence":
            connection.execute(update(evidence).values(verified_at=None))
        elif change == "withdrawn":
            connection.execute(update(claims).values(claim_status="withdrawn"))
        else:
            connection.execute(update(document_revisions).values(is_current=False))
    assert_problem(post_question(api), 503, "answer_evidence_unavailable")
    assert api["wire"].calls == []
    row = stored_answer(api)
    assert row["response"] == {"kind": "failed", "error_code": "answer_evidence_unavailable"}
    assert row["model_trace"]["attempts"] == [] and row["model_trace"]["fee"] == "unknown"


@pytest.mark.parametrize("change", ["epoch", "withdrawn", "private"])
def test_fact_change_during_generation_cannot_publish_new_answer(question_api, change):
    api = question_api

    def change_fact():
        with api["engine"].begin() as connection:
            if change == "epoch":
                connection.execute(update(scope_epochs).values(epoch=scope_epochs.c.epoch + 1))
            elif change == "withdrawn":
                connection.execute(update(claims).values(claim_status="withdrawn"))
            else:
                connection.execute(
                    update(events).values(
                        visibility="tenant", tenant_id="tenant-b", scope_key="tenant:tenant-b"
                    )
                )

    api["wire"].before_verification = change_fact
    assert_problem(post_question(api), 503, "answer_evidence_changed")
    row = stored_answer(api)
    assert row["response"]["kind"] == "failed"
    assert len(row["model_trace"]["attempts"]) == 2


def test_history_becomes_stale_without_overwriting_saved_response(question_api):
    api = question_api
    first = post_question(api, key="fixture-historical")
    assert first.status_code == 200, first.text
    original = stored_answer(api)["response"]
    with api["engine"].begin() as connection:
        connection.execute(update(scope_epochs).values(epoch=scope_epochs.c.epoch + 1))
        connection.execute(update(claims).values(claim_status="withdrawn"))
    response = api["client"].get("/api/v1/answers/" + first.json()["answer_id"])
    assert response.status_code == 200, response.text
    assert response.json() == {**original, "freshness": "stale"}
    assert stored_answer(api)["response"] == original
    assert post_question(api, key="fixture-historical").json()["freshness"] == "stale"
    assert len(api["wire"].calls) == 2


def test_generation_failure_attempt_and_unknown_fee_survive_restart(question_api):
    api = question_api
    api["wire"].failure_status = 503
    response = post_question(api, key="fixture-failed")
    assert response.status_code == 503
    row = stored_answer(api)
    assert row["response"]["kind"] == "failed"
    trace = row["model_trace"]
    assert trace["fee"] == "unknown" and len(trace["attempts"]) == 1
    assert trace["attempts"][0]["http_status"] == 503
    assert trace["attempts"][0]["fee"] == "unknown"
    assert trace["attempts"][0]["usage"]["total_tokens"] is None
    restarted = TestClient(create_application(settings=api["settings"]))
    restarted.cookies.update(api["client"].cookies)
    try:
        assert_problem(restarted.get("/v1/answers/" + row["answer_id"]), 409, "answer_failed")
        assert_problem(
            restarted.post(
                "/api/v1/questions",
                json=api["payload"],
                headers={**api["headers"], "Idempotency-Key": "fixture-failed"},
            ),
            409,
            "answer_failed",
        )
    finally:
        restarted.close()
    assert len(api["wire"].calls) == 1


@pytest.mark.parametrize("change", ["revoked", "permission", "tenant"])
def test_authentication_is_rechecked_after_generation(question_api, monkeypatch, change):
    api = question_api

    def change_authorization():
        if change == "revoked":
            api["auth"].logout(api["client"].cookies[SESSION_COOKIE_NAME])
        elif change == "permission":
            monkeypatch.setitem(ROLE_PERMISSIONS, Role.VIEWER, frozenset())
        else:
            with api["engine"].begin() as connection:
                connection.execute(
                    update(users)
                    .where(users.c.user_id == api["identity"]["user_id"])
                    .values(tenant_id="tenant-b")
                )

    api["wire"].before_verification = change_authorization
    response = post_question(api)
    assert_problem(
        response,
        {"revoked": 401, "permission": 403, "tenant": 404}[change],
        {"revoked": "session_expired", "permission": "permission_denied", "tenant": "not_found"}[
            change
        ],
    )
    assert stored_answer(api)["response"]["kind"] == "failed"
    assert len(api["wire"].calls) == 2


@pytest.mark.parametrize("tenant", ["tenant-a", "tenant-b"])
def test_answer_owner_and_tenant_are_not_visible_to_other_users(question_api, tenant):
    api = question_api
    first = post_question(api)
    assert first.status_code == 200, first.text
    other, _ = api["login"](tenant=tenant)
    assert_problem(other.get("/v1/answers/" + first.json()["answer_id"]), 404, "not_found")
    assert_problem(other.get("/api/v1/answers/" + str(uuid4())), 404, "not_found")


def test_private_event_never_reaches_model(question_api):
    api = question_api
    with api["engine"].begin() as connection:
        connection.execute(
            update(events).values(
                visibility="tenant", tenant_id="tenant-b", scope_key="tenant:tenant-b"
            )
        )
    assert_problem(post_question(api), 404, "not_found")
    assert api["wire"].calls == []


def test_config_missing_returns_503_but_saved_answer_remains_readable(question_api):
    api = question_api
    first = post_question(api)
    assert first.status_code == 200, first.text
    settings = api["settings"].model_copy(update={"generation_api_key": None})
    client = TestClient(create_application(settings=settings))
    client.cookies.update(api["client"].cookies)
    try:
        assert_problem(
            client.post("/v1/questions", json=api["payload"], headers=api["headers"]),
            503,
            "question_models_not_configured",
        )
        assert client.get("/api/v1/answers/" + first.json()["answer_id"]).json() == first.json()
    finally:
        client.close()
    assert len(api["wire"].calls) == 2


def test_unsupported_r12_scope_is_rejected_without_pg_answer_or_model(question_api):
    api = question_api
    variants = (
        {"event_ids": []},
        {"event_ids": [*api["payload"]["event_ids"], str(uuid4())]},
        {"asset_ids": [str(uuid4())]},
        {"conversation_id": str(uuid4())},
        {"known_at": "2026-10-15T08:00:00Z"},
        {"valid_at": "2026-10-15T08:00:00Z"},
        {"mode": "investigate"},
    )
    for variant in variants:
        assert_problem(
            post_question(api, payload={**api["payload"], **variant}),
            422,
            "question_scope_not_supported",
        )
    assert api["wire"].calls == []
    with api["engine"].connect() as connection:
        assert connection.scalar(select(func.count()).select_from(grounded_answers)) == 0


def test_expired_pending_replay_fails_without_charge_and_late_writer_cannot_publish(question_api):
    api = question_api
    reached = Event()
    release = Event()

    def block_verification():
        reached.set()
        assert release.wait(10), "fixture verification barrier timed out"

    api["wire"].before_verification = block_verification
    with ThreadPoolExecutor(max_workers=1) as executor:
        original_request = executor.submit(post_question, api, key="fixture-expired")
        try:
            assert reached.wait(10)
            pending = stored_answer(api)
            assert pending["response"] == {"kind": "pending"}
            reservation_id = pending["model_trace"]["reservation_id"]
            with api["engine"].begin() as connection:
                connection.execute(
                    update(grounded_answers).values(
                        model_trace={
                            **pending["model_trace"],
                            "reservation_expires_at": "2000-01-01T00:00:00+00:00",
                        }
                    )
                )
            restarted = TestClient(create_application(settings=api["settings"]))
            restarted.cookies.update(api["client"].cookies)
            try:
                replay = restarted.post(
                    "/api/v1/questions",
                    json=api["payload"],
                    headers={**api["headers"], "Idempotency-Key": "fixture-expired"},
                )
                assert_problem(replay, 409, "answer_failed")
                expired = stored_answer(api)
                assert expired["response"] == {"kind": "failed", "error_code": "answer_interrupted"}
                assert expired["model_trace"]["reservation_state"] == "expired"
                assert expired["model_trace"]["usage_status"] == "incomplete_interrupted"
                assert expired["model_trace"]["fee"] == "unknown"
                assert len(api["wire"].calls) == 2
                assert_problem(
                    restarted.get("/v1/answers/" + pending["answer_id"]), 409, "answer_failed"
                )
            finally:
                restarted.close()
        finally:
            release.set()
        assert_problem(original_request.result(timeout=15), 409, "answer_failed")
    terminal = stored_answer(api)
    assert terminal["response"] == {"kind": "failed", "error_code": "answer_interrupted"}
    assert terminal["model_trace"]["reservation_id"] == reservation_id
    assert terminal["model_trace"]["reservation_state"] == "expired"
    assert terminal["model_trace"]["usage_status"] == "recorded_after_terminal"
    assert len(terminal["model_trace"]["attempts"]) == 2
    assert all(attempt["fee"] == "unknown" for attempt in terminal["model_trace"]["attempts"])
    assert len(api["wire"].calls) == 2


@pytest.mark.parametrize("change", ["logout", "tenant"])
def test_final_auth_lock_orders_later_pg_mutation_after_answer_commit(
    question_api, monkeypatch, change
):
    api = question_api
    locked = Event()
    release = Event()
    owner_pids = []
    require_current = EventEvidenceRetriever.require_current

    def block_after_auth_lock(
        session, scope, event_id, epoch, citations, *, lock_epoch=False, data_mode="live"
    ):
        if lock_epoch:
            owner_pids.append(session.scalar(text("SELECT pg_backend_pid()")))
            locked.set()
            assert release.wait(10), "fixture final commit barrier timed out"
        return require_current(
            session, scope, event_id, epoch, citations, lock_epoch=lock_epoch, data_mode=data_mode
        )

    monkeypatch.setattr(
        EventEvidenceRetriever, "require_current", staticmethod(block_after_auth_lock)
    )
    logout_client = TestClient(create_application(settings=api["settings"]))
    logout_client.cookies.update(api["client"].cookies)

    def mutate_pg_authorization():
        if change == "logout":
            response = logout_client.post("/v1/auth/logout", headers=api["headers"])
            assert response.status_code == 200, response.text
        else:
            with api["engine"].begin() as connection:
                connection.execute(
                    update(users)
                    .where(users.c.user_id == api["identity"]["user_id"])
                    .values(tenant_id="tenant-b")
                )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            answer_request = executor.submit(post_question, api, key="fixture-final-auth-lock")
            try:
                assert locked.wait(10), "final auth lock was not reached"
                mutation = executor.submit(mutate_pg_authorization)
                deadline = time.monotonic() + 5
                blocked_by_answer = False
                while time.monotonic() < deadline:
                    with api["engine"].connect() as connection:
                        blocked_by_answer = bool(
                            connection.scalar(
                                text(
                                    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                                    "WHERE wait_event_type = 'Lock' "
                                    "AND :owner_pid = ANY(pg_blocking_pids(pid)))"
                                ),
                                {"owner_pid": owner_pids[0]},
                            )
                        )
                    if blocked_by_answer or mutation.done():
                        break
                    time.sleep(0.01)
                assert blocked_by_answer, "PG authorization mutation did not wait for answer lock"
                assert not mutation.done()
            finally:
                release.set()
            answer = answer_request.result(timeout=15)
            assert answer.status_code == 200, answer.text
            mutation.result(timeout=10)
        assert stored_answer(api)["response"] == answer.json()
        read = api["client"].get("/api/v1/answers/" + answer.json()["answer_id"])
        assert_problem(
            read,
            401 if change == "logout" else 404,
            "session_expired" if change == "logout" else "not_found",
        )
        assert len(api["wire"].calls) == 2
    finally:
        release.set()
        logout_client.close()
