"""Real isolated PG authorization and reservation; all semantic/model IO is explicit fixture IO."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from itertools import groupby
from threading import Event
from time import monotonic, sleep
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, event, func, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema
from test_r05_question_api_pg import question_api as question_api
from test_r05_vector_persistence import FixtureSemanticModels, load_legacy_0013_seed

from ai_intel.answering import service as question_service
from ai_intel.api.actor_references import create_actor_reference
from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.api.auth_state import lock_authenticated_scope
from ai_intel.api.credential_models import api_key_rate_buckets, api_keys
from ai_intel.api.credentials import (
    ApiKeyCredential,
    ApiKeyRateLimitedError,
    InvalidApiKeyError,
    PgApiKeyService,
    SessionCredential,
    consume_api_key_rate_limit,
)
from ai_intel.api.question_contracts import QuestionRequest
from ai_intel.api.question_routes import build_question_service
from ai_intel.domain.access import READ_PUBLIC, CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.ingestion.source_documents import source_data_mode_metadata
from ai_intel.knowledge.models import document_revisions, users
from ai_intel.retrieval.persistence_models import grounded_answers

pytestmark = pytest.mark.real_pg


@pytest.fixture
def vector_database(isolated_test_database_url, tmp_path):
    """Use only the caller's isolated DSN, with a new schema and verified cleanup ownership."""
    url = make_url(isolated_test_database_url)
    assert url.database and url.database.startswith("test_")
    base = create_engine(url, poolclass=NullPool, connect_args={"connect_timeout": 5})
    schema = "test_r05_qa_credential_" + uuid4().hex
    marker = "fixture-r18-question-credential:" + uuid4().hex
    with base.begin() as connection:
        assert connection.scalar(text("SELECT current_database()")) == url.database
        connection.execute(CreateSchema(schema))
        connection.execute(text(f"COMMENT ON SCHEMA {schema} IS '{marker}'"))
        schema_oid = connection.scalar(
            text("SELECT oid FROM pg_namespace WHERE nspname=:name"), {"name": schema}
        )
    isolated = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=5000"}
    )
    runtime = isolated.update_query_dict(
        {
            "options": (
                f"-c search_path={schema},public -c statement_timeout=15000 -c lock_timeout=5000"
            )
        }
    )
    engine = create_engine(runtime, poolclass=NullPool, connect_args={"connect_timeout": 5})
    try:
        migration_url = isolated.render_as_string(hide_password=False)
        run_migrations(migration_url, "0013_revision_source_metadata")
        load_legacy_0013_seed(engine, schema, ContentStore(tmp_path / "fixture-content"))
        run_migrations(migration_url)
        with engine.begin() as connection:
            connection.execute(
                update(document_revisions).values(
                    source_metadata=document_revisions.c.source_metadata.op("||")(
                        source_data_mode_metadata("fixture")
                    )
                )
            )
        yield engine
    finally:
        engine.dispose()
        with base.begin() as connection:
            owned = connection.execute(
                text(
                    "SELECT oid,obj_description(oid,'pg_namespace') FROM pg_namespace "
                    "WHERE nspname=:name"
                ),
                {"name": schema},
            ).one()
            assert owned == (schema_oid, marker)
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


@pytest.fixture
def credential_case(question_api, register_sensitive_failure_value):
    api = question_api
    session_credential = SessionCredential(SecretStr(api["client"].cookies[SESSION_COOKIE_NAME]))
    issued = PgApiKeyService(api["engine"]).issue_key(session_credential, frozenset({READ_PUBLIC}))
    register_sensitive_failure_value(issued.token)
    credential = ApiKeyCredential(issued.token)
    with api["engine"].begin() as connection:
        actor = create_actor_reference(connection, credential, datetime.now(UTC))
        scope = lock_authenticated_scope(connection, actor, datetime.now(UTC))
    questions = build_question_service(api["engine"], api["settings"])
    assert questions is not None
    return api, questions, actor, scope, credential, session_credential


def ask(case, key="fixture-qa-key", payload=None, questions=None, credential=None, scope=None):
    api, service, actor, current, original, _session = case
    return (questions or service).ask(
        QuestionRequest.model_validate(payload or api["payload"]),
        lambda: scope or current,
        key,
        session_token=actor,
        credential=credential or original,
    )


def usage(case):
    api, _service, actor, *_rest = case
    with api["engine"].connect() as connection:
        return connection.scalar(
            select(func.coalesce(func.sum(api_key_rate_buckets.c.request_count), 0)).where(
                api_key_rate_buckets.c.key_id == actor.key_id,
                api_key_rate_buckets.c.operation == "ask",
            )
        )


def rows(case):
    with case[0]["engine"].connect() as connection:
        return list(connection.execute(select(grounded_answers)).mappings())


def test_completed_replay_history_and_conflict_charge_one_reservation(credential_case):
    case = credential_case
    answer = ask(case)
    assert answer.data_mode == "fixture" and len(case[0]["wire"].calls) == 2
    stored = dict(rows(case)[0])
    assert ask(case).model_dump() == answer.model_dump()
    restored = question_service.read_grounded_answer(
        case[0]["engine"], case[3], answer.answer_id, session_token=case[2]
    )
    assert restored.model_dump() == answer.model_dump()
    with pytest.raises(question_service.QuestionFailure, match="idempotency_conflict"):
        ask(case, payload={**case[0]["payload"], "question": "另一问题"})
    assert usage(case) == 1 and rows(case)[0] == stored
    assert len(case[0]["wire"].calls) == 2
    assert stored["model_trace"]["fee"] == "unknown"


def test_same_owner_other_key_is_rejected_without_quota_or_answer(credential_case):
    case = credential_case
    issued = PgApiKeyService(case[0]["engine"]).issue_key(case[5], frozenset({READ_PUBLIC}))
    with pytest.raises(InvalidApiKeyError):
        ask(case, credential=ApiKeyCredential(issued.token))
    assert usage(case) == 0 and rows(case) == [] and case[0]["wire"].calls == []


@pytest.mark.parametrize("change", ["revoked", "expired", "tenant", "role"])
def test_current_credential_changes_deny_initial_query_before_io(credential_case, change):
    case = credential_case
    with case[0]["engine"].begin() as connection:
        if change in {"tenant", "role"}:
            connection.execute(
                update(users)
                .where(users.c.user_id == case[3].user_id)
                .values(
                    **(
                        {"tenant_id": "fixture-other-tenant"}
                        if change == "tenant"
                        else {"role": "analyst"}
                    )
                )
            )
        else:
            connection.execute(
                update(api_keys)
                .where(api_keys.c.key_id == case[2].key_id)
                .values(
                    **(
                        {"revoked_at": datetime.now(UTC)}
                        if change == "revoked"
                        else {"expires_at": datetime.now(UTC)}
                    )
                )
            )
    with pytest.raises(PermissionDeniedError):
        ask(case)
    assert usage(case) == 0 and rows(case) == [] and case[0]["wire"].calls == []


def test_scope_provider_cannot_supply_another_tenant(credential_case):
    case = credential_case
    other = case[3].__class__.for_authenticated_user(case[3].user_id, "other-tenant", case[3].role)
    with pytest.raises(CrossTenantAccessError):
        ask(case, scope=other)
    assert usage(case) == 0 and rows(case) == [] and case[0]["wire"].calls == []


def test_read_asset_only_key_cannot_reserve_question(credential_case):
    api, _service, _actor, _scope, _credential, _original_session = credential_case
    analyst, _identity = api["login"](role=Role.ANALYST)
    session = SessionCredential(SecretStr(analyst.cookies[SESSION_COOKIE_NAME]))
    issued = PgApiKeyService(api["engine"]).issue_key(session, frozenset({"read:asset"}))
    credential = ApiKeyCredential(issued.token)
    with api["engine"].begin() as connection:
        actor = create_actor_reference(connection, credential, datetime.now(UTC))
        scope = lock_authenticated_scope(connection, actor, datetime.now(UTC))
    denied = (api, credential_case[1], actor, scope, credential, session)
    with pytest.raises(PermissionDeniedError):
        ask(denied)
    assert rows(credential_case) == [] and usage(denied) == 0


def test_rate_rejection_rolls_back_new_answer_in_same_transaction(credential_case, monkeypatch):
    case = credential_case
    connection_ids = []

    def exhaust(connection, credential, now, *, operation):
        assert connection.in_transaction() and operation == "ask"
        assert connection.scalar(select(func.count()).select_from(grounded_answers)) == 1
        connection_ids.append(id(connection))
        consume_api_key_rate_limit(connection, credential, now, operation=operation)
        raise ApiKeyRateLimitedError(1)

    monkeypatch.setattr(question_service, "consume_api_key_rate_limit", exhaust)
    with pytest.raises(ApiKeyRateLimitedError):
        ask(case)
    assert connection_ids and usage(case) == 0 and rows(case) == []
    assert case[0]["wire"].calls == []


def test_budget_full_does_not_reserve_or_call_provider(credential_case):
    case = credential_case
    with case[0]["engine"].begin() as connection:
        for _ in range(10):
            consume_api_key_rate_limit(connection, case[4], datetime.now(UTC), operation="ask")
    with pytest.raises(ApiKeyRateLimitedError):
        ask(case)
    assert usage(case) == 10 and rows(case) == [] and case[0]["wire"].calls == []


def test_live_consumer_rejects_fixture_provenance_before_external_io(credential_case):
    case = credential_case
    settings = case[0]["settings"].model_copy(update={"data_mode": "live"})
    questions = build_question_service(case[0]["engine"], settings)
    assert questions.retriever.data_mode == questions.data_mode == "live"
    with pytest.raises(question_service.QuestionFailure, match="question_processing_failed"):
        ask(case, questions=questions)
    assert usage(case) == 1 and rows(case)[0]["response"]["kind"] == "failed"
    assert case[0]["wire"].calls == []


def test_expired_reservation_rolls_back_quota_before_any_io(credential_case, monkeypatch):
    case = credential_case
    monkeypatch.setattr(question_service, "ANSWER_RESERVATION_SECONDS", -1)
    with pytest.raises(question_service.QuestionFailure, match="answer_lease_expired"):
        ask(case)
    assert usage(case) == 0 and rows(case) == [] and case[0]["wire"].calls == []


@pytest.mark.parametrize("locked_resource", ["credential", "quota"])
def test_real_lock_wait_expiry_never_commits_reservation_or_usage(
    credential_case, monkeypatch, locked_resource
):
    case = credential_case
    expiry = datetime.now(UTC) + timedelta(seconds=2)
    if locked_resource == "credential":
        with case[0]["engine"].begin() as connection:
            connection.execute(
                update(api_keys)
                .where(api_keys.c.key_id == case[2].key_id)
                .values(expires_at=expiry)
            )
    else:
        monkeypatch.setattr(question_service, "ANSWER_RESERVATION_SECONDS", 2)
    with case[0]["engine"].connect() as blocker:
        transaction = blocker.begin()
        owner_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
        if locked_resource == "credential":
            blocker.execute(
                select(api_keys.c.key_id)
                .where(api_keys.c.key_id == case[2].key_id)
                .with_for_update()
            ).one()
        else:
            blocker.execute(text("LOCK TABLE api_key_rate_buckets IN EXCLUSIVE MODE"))
        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(ask, case)
            try:
                observation_limit = monotonic() + 1
                waiting = False
                while monotonic() < observation_limit and not first.done():
                    blocker.execute(text("SELECT pg_stat_clear_snapshot()"))
                    waiting = blocker.scalar(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                            "WHERE wait_event_type='Lock' AND :pid=ANY(pg_blocking_pids(pid)))"
                        ),
                        {"pid": owner_pid},
                    )
                    if waiting:
                        break
                    sleep(0.01)
                assert waiting, "the service must actually wait on the owned PG lock"
                release_after = monotonic() + 2.1
                while monotonic() < release_after or datetime.now(UTC) <= expiry + timedelta(
                    milliseconds=100
                ):
                    sleep(0.01)
            finally:
                transaction.commit()
            failure = (
                PermissionDeniedError
                if locked_resource == "credential"
                else question_service.QuestionFailure
            )
            with pytest.raises(failure):
                first.result(timeout=5)
    assert usage(case) == 0 and rows(case) == [] and case[0]["wire"].calls == []


def test_separate_services_concurrent_pending_replay_never_charge_twice(credential_case):
    case = credential_case
    reached, release = Event(), Event()

    def barrier():
        reached.set()
        assert release.wait(5)

    case[0]["wire"].before_verification = barrier
    second_service = build_question_service(case[0]["engine"], case[0]["settings"])
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(ask, case)
        try:
            assert reached.wait(5)
            with pytest.raises(question_service.QuestionFailure, match="answer_in_progress"):
                ask(case, questions=second_service)
            with pytest.raises(question_service.QuestionFailure, match="idempotency_conflict"):
                ask(
                    case,
                    questions=second_service,
                    payload={**case[0]["payload"], "question": "另一问题"},
                )
            assert usage(case) == 1 and len(rows(case)) == 1
        finally:
            release.set()
        answer = first.result(timeout=10)
    assert rows(case)[0]["response"] == answer.model_dump(mode="json")
    assert usage(case) == 1 and len(case[0]["wire"].calls) == 2


@pytest.mark.parametrize("revoke_after", ["passages", "query", "rerank", "draft"])
@pytest.mark.parametrize("mutation", ["revoked", "expired"])
def test_each_next_external_request_denies_revocation_and_preserves_usage(
    credential_case, revoke_after, mutation
):
    case = credential_case
    io_stages = []
    active_connections = set()

    def begin(connection):
        active_connections.add(id(connection))

    def end(connection):
        active_connections.discard(id(connection))

    def performed(stage):
        assert not active_connections, "fixture IO occurred while a DB transaction held locks"
        io_stages.append(stage)
        if stage == revoke_after:
            with case[0]["engine"].begin() as connection:
                connection.execute(
                    update(api_keys)
                    .where(api_keys.c.key_id == case[2].key_id)
                    .values(
                        **(
                            {"revoked_at": datetime.now(UTC)}
                            if mutation == "revoked"
                            else {"expires_at": datetime.now(UTC)}
                        )
                    )
                )

    class ObservedModels(FixtureSemanticModels):
        def embed_passages(self, passages):
            result = super().embed_passages(passages)
            performed("passages")
            return result

        def embed_query(self, query):
            result = super().embed_query(query)
            performed("query")
            return result

        def rerank(self, query, passages):
            result = super().rerank(query, passages)
            performed("rerank")
            return result

    original_respond = case[0]["wire"].respond

    def respond(url, body):
        result = original_respond(url, body)
        performed("draft" if len(case[0]["wire"].calls) == 1 else "verify")
        return result

    case[1].retriever.models = ObservedModels()
    case[0]["wire"].respond = respond
    for name, listener in (("begin", begin), ("commit", end), ("rollback", end)):
        event.listen(case[0]["engine"], name, listener)
    try:
        with pytest.raises(PermissionDeniedError):
            ask(case)
    finally:
        for name, listener in (("begin", begin), ("commit", end), ("rollback", end)):
            event.remove(case[0]["engine"], name, listener)
    expected = {
        "passages": ("passages",),
        "query": ("passages", "query"),
        "rerank": ("passages", "query", "rerank"),
        "draft": ("passages", "query", "rerank", "draft"),
    }
    assert tuple(stage for stage, _group in groupby(io_stages)) == expected[revoke_after]
    if revoke_after == "passages":
        assert io_stages == ["passages"]
    assert usage(case) == 1 and rows(case)[0]["response"]["kind"] == "failed"
    attempts = rows(case)[0]["model_trace"]["attempts"]
    assert len(attempts) == (1 if revoke_after == "draft" else 0)
    if attempts:
        assert attempts[0]["fee"] == "unknown" and attempts[0]["call_id"]


def test_expired_pending_replay_keeps_terminal_and_late_attempts(credential_case):
    case = credential_case
    reached, release = Event(), Event()

    def barrier():
        reached.set()
        assert release.wait(5)

    case[0]["wire"].before_verification = barrier
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(ask, case)
        try:
            assert reached.wait(5)
            original = rows(case)[0]
            with case[0]["engine"].begin() as connection:
                connection.execute(
                    update(grounded_answers).values(
                        model_trace={
                            **original["model_trace"],
                            "reservation_expires_at": "2000-01-01T00:00:00+00:00",
                        }
                    )
                )
            with pytest.raises(question_service.QuestionFailure, match="answer_failed"):
                ask(case)
        finally:
            release.set()
        with pytest.raises(question_service.QuestionFailure):
            first.result(timeout=10)
    terminal = rows(case)[0]
    assert terminal["response"] == {"kind": "failed", "error_code": "answer_interrupted"}
    assert terminal["model_trace"]["reservation_id"] == original["model_trace"]["reservation_id"]
    assert terminal["model_trace"]["usage_status"] == "recorded_after_terminal"
    assert len(terminal["model_trace"]["attempts"]) == 2 and usage(case) == 1


def test_replay_with_revoked_key_never_returns_saved_success(credential_case):
    case = credential_case
    answer = ask(case)
    original = dict(rows(case)[0])
    with case[0]["engine"].begin() as connection:
        connection.execute(
            update(api_keys)
            .where(api_keys.c.key_id == case[2].key_id)
            .values(revoked_at=datetime.now(UTC))
        )
    with pytest.raises(PermissionDeniedError):
        ask(case)
    with pytest.raises(PermissionDeniedError):
        question_service.read_grounded_answer(
            case[0]["engine"], case[3], UUID(str(answer.answer_id)), session_token=case[2]
        )
    assert rows(case)[0] == original and usage(case) == 1 and len(case[0]["wire"].calls) == 2
