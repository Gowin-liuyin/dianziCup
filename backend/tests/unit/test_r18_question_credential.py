"""Explicit synthetic identity fixtures; no PostgreSQL or provider IO is performed."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import SecretStr
from test_r05_grounded_answer import candidate, evidence, prepared, verdict

from ai_intel.answering import service
from ai_intel.answering.grounding import GroundedAnswerGuardFailure, generate_grounded_answer
from ai_intel.api import question_routes
from ai_intel.api.actor_references import actor_reference_from_payload
from ai_intel.api.authentication import InvalidCredentialsError
from ai_intel.api.credentials import API_KEY_RESOURCE, ApiKeyCredential, SessionCredential
from ai_intel.domain.access import (
    READ_PUBLIC,
    AccessScope,
    CrossTenantAccessError,
    PermissionDeniedError,
    Role,
)
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.knowledge.revision_mode import RevisionModeUnavailableError, homogeneous_revision_mode
from ai_intel.retrieval import service as retrieval

SCOPE = AccessScope.for_authenticated_user("fixture-qa-user", "fixture-qa-tenant", Role.VIEWER)
TOKEN = SecretStr("fixture-question-session-token")


def reference(kind="api_key", key_id="fixture-key", permissions=frozenset({READ_PUBLIC})):
    now = datetime.now(UTC)
    return actor_reference_from_payload(
        {
            "credential_kind": kind,
            "user_id": SCOPE.user_id,
            "tenant_id": SCOPE.tenant_id,
            "role": SCOPE.role.value,
            "permissions": sorted(permissions),
            "permission_version": SCOPE.permission_version,
            "permissions_digest": hashlib.sha256(
                json.dumps(sorted(permissions), separators=(",", ":")).encode()
            ).hexdigest(),
            "resource": API_KEY_RESOURCE,
            "issued_at": (now - timedelta(seconds=1)).isoformat(),
            "created_at": now.isoformat(),
            "session_hash": hashlib.sha256(TOKEN.get_secret_value().encode()).hexdigest()
            if kind == "session"
            else None,
            "key_id": key_id if kind == "api_key" else None,
            "credential_version": 1 if kind == "api_key" else None,
        }
    )


@pytest.fixture
def identity_fixture(monkeypatch):
    connection = object()
    session = SimpleNamespace(connection=lambda: connection, scalar=lambda query: datetime.now(UTC))
    calls = []

    def lock_scope(actual_connection, actor, now):
        assert actual_connection is connection and now.tzinfo is not None
        calls.append(actor)
        return SCOPE

    monkeypatch.setattr(service, "lock_authenticated_scope", lock_scope)
    return session, calls


def test_cookie_original_lock_is_preserved_without_explicit_credential(identity_fixture):
    session, calls = identity_fixture
    assert service._lock_answer_scope(session, SCOPE, TOKEN.get_secret_value()) == SCOPE
    assert calls == [TOKEN.get_secret_value()]


@pytest.mark.parametrize("kind", ["session", "api_key"])
def test_explicit_credential_matches_the_same_actor_locator(identity_fixture, monkeypatch, kind):
    session, calls = identity_fixture
    actor = reference(kind)
    credential = SessionCredential(TOKEN) if kind == "session" else ApiKeyCredential(TOKEN)
    monkeypatch.setattr(service, "create_actor_reference", lambda *args: actor)
    assert service._lock_answer_scope(session, SCOPE, actor, credential=credential) == SCOPE
    assert calls == [actor]


def test_same_owner_different_key_is_rejected_before_original_actor_lock(
    identity_fixture, monkeypatch
):
    session, calls = identity_fixture
    actor = reference()
    monkeypatch.setattr(service, "create_actor_reference", lambda *args: reference(key_id="other"))
    with pytest.raises(service.InvalidApiKeyError):
        service._lock_answer_scope(session, SCOPE, actor, credential=ApiKeyCredential(TOKEN))
    assert calls == []


@pytest.mark.parametrize("actor", [TOKEN.get_secret_value(), reference("session")])
def test_api_key_cannot_be_used_as_cookie_or_session_reference(
    identity_fixture, monkeypatch, actor
):
    session, calls = identity_fixture
    monkeypatch.setattr(service, "create_actor_reference", lambda *args: reference())
    with pytest.raises(service.InvalidApiKeyError):
        service._lock_answer_scope(session, SCOPE, actor, credential=ApiKeyCredential(TOKEN))
    assert calls == []


def test_different_cookie_credential_is_rejected(identity_fixture, monkeypatch):
    session, calls = identity_fixture
    monkeypatch.setattr(service, "create_actor_reference", lambda *args: reference("session"))
    with pytest.raises(InvalidCredentialsError):
        service._lock_answer_scope(
            session, SCOPE, "another-cookie", credential=SessionCredential(TOKEN)
        )
    assert calls == []


@pytest.mark.parametrize(
    "scope",
    [
        AccessScope.for_authenticated_user("other-user", SCOPE.tenant_id, Role.VIEWER),
        AccessScope.for_authenticated_user(SCOPE.user_id, "other-tenant", Role.VIEWER),
    ],
)
def test_current_owner_or_tenant_must_match_the_supplied_scope(identity_fixture, scope):
    session, _calls = identity_fixture
    with pytest.raises(CrossTenantAccessError):
        service._lock_answer_scope(session, scope, TOKEN.get_secret_value())


def test_read_permission_is_required_from_current_locked_scope(identity_fixture, monkeypatch):
    session, _calls = identity_fixture
    denied = AccessScope(
        SCOPE.user_id, SCOPE.tenant_id, SCOPE.role, frozenset(), SCOPE.permission_version
    )
    monkeypatch.setattr(service, "lock_authenticated_scope", lambda *args: denied)
    with pytest.raises(PermissionDeniedError):
        service._lock_answer_scope(session, SCOPE, TOKEN.get_secret_value())


def test_api_key_actor_requires_explicit_bearer_before_any_session_or_io():
    questions = service.GroundedQuestionService(None, None, None, data_mode="fixture")
    with pytest.raises(service.InvalidApiKeyError):
        questions.ask(None, lambda: SCOPE, "fixture-id", session_token=reference())


@pytest.mark.parametrize("rejected_call", [1, 2])
def test_each_model_call_checks_guard_and_keeps_completed_attempts(monkeypatch, rejected_call):
    client, calls = prepared(monkeypatch, [candidate(), {"verdicts": [verdict()]}])
    original_error = PermissionDeniedError("required permission missing")
    guards = []

    def guard():
        guards.append(len(calls))
        if len(guards) == rejected_call:
            raise original_error

    with pytest.raises(GroundedAnswerGuardFailure) as failure:
        generate_grounded_answer(client, "如何修复？", (evidence(),), before_call=guard)
    assert failure.value.error is original_error
    assert guards == list(range(rejected_call))
    assert len(calls) == rejected_call - 1
    assert len(failure.value.attempts) == rejected_call - 1
    if rejected_call == 2:
        assert failure.value.attempts[0].call_id == "synthetic-call-1"
        assert failure.value.attempts[0].fee == "unknown"


def test_successful_model_calls_each_pass_fresh_guard(monkeypatch):
    client, calls = prepared(monkeypatch, [candidate(), {"verdicts": [verdict()]}])
    guards = []
    answer = generate_grounded_answer(
        client, "如何修复？", (evidence(),), before_call=lambda: guards.append(len(calls))
    )
    assert guards == [0, 1] and len(calls) == 2 and len(answer.attempts) == 2


@pytest.mark.parametrize("mode", ["fixture", "live"])
def test_question_factory_passes_trusted_setting_to_both_readers(monkeypatch, tmp_path, mode):
    monkeypatch.setattr(question_routes, "LocalSemanticModels", lambda path: object())
    monkeypatch.setattr(question_routes, "GenerationClient", lambda *args, **kwargs: object())
    settings = ApplicationSettings(
        app_env="test",
        data_mode=mode,
        generation_api_key=SecretStr("fixture-no-io-credential"),
        semantic_model_cache_directory=tmp_path,
    )
    questions = question_routes.build_question_service(object(), settings)
    assert questions.data_mode == mode and questions.retriever.data_mode == mode


def test_retriever_keeps_original_live_default_and_rejects_unknown_mode():
    assert retrieval.EventEvidenceRetriever(None, None).data_mode == "live"
    with pytest.raises(ValueError, match="invalid retrieval data mode"):
        retrieval.EventEvidenceRetriever(None, None, data_mode="untrusted")


@pytest.mark.parametrize("consumer,stored", [("live", "fixture"), ("fixture", "live")])
def test_current_citation_reader_rejects_both_mode_mismatches(monkeypatch, consumer, stored):
    """Simulate only provenance metadata; no synthetic content is stored or promoted to live."""
    citation = evidence()
    source_row = {
        "evidence_id": str(citation.evidence_id),
        "revision_id": str(citation.revision_id),
        "quote": citation.quote,
    }
    session = SimpleNamespace(execute=lambda query: SimpleNamespace(mappings=lambda: [source_row]))
    monkeypatch.setattr(retrieval, "current_public_epoch", lambda *args, **kwargs: 1)
    observed = []

    class MetadataOnlyReader:
        def __init__(self, session, scope, data_mode):
            observed.append(data_mode)
            self.data_mode = data_mode

        def read_evidence(self, evidence_id):
            homogeneous_revision_mode(
                ({"data_mode": stored, "data_mode_policy_version": "trusted-source-runtime-v1"},),
                self.data_mode,
            )
            raise AssertionError("mismatched provenance reached a citation projection")

    monkeypatch.setattr(retrieval, "KnowledgeReadService", MetadataOnlyReader)
    with pytest.raises(RevisionModeUnavailableError, match="source_mode_does_not_match_consumer"):
        retrieval.EventEvidenceRetriever.require_current(
            session, SCOPE, uuid4(), 1, (citation,), data_mode=consumer
        )
    assert observed == [consumer]


@pytest.mark.parametrize("database_time", [None, datetime(2026, 10, 17)])
def test_missing_or_naive_database_clock_never_authorizes_cookie(database_time, monkeypatch):
    session = SimpleNamespace(connection=lambda: object(), scalar=lambda query: database_time)
    calls = []
    monkeypatch.setattr(service, "lock_authenticated_scope", lambda *args: calls.append(args))
    with pytest.raises(service.QuestionFailure, match="question_database_clock_unavailable"):
        service._lock_answer_scope(session, SCOPE, TOKEN.get_secret_value())
    assert calls == []
