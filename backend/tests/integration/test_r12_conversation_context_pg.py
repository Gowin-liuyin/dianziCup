"""Real PG concurrency, ownership and lifecycle; all answer bodies are synthetic receipts."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import func, select, update
from tests.r12_conversation_fixtures import context_identity as context_identity
from tests.r12_conversation_fixtures import conversation_database as conversation_database
from tests.r12_conversation_fixtures import record_synthetic_completion
from tests.r12_hybrid_fixtures import seed_fact

from ai_intel.answering.conversation_context import ConversationContextService
from ai_intel.answering.conversation_contracts import ConversationFailure
from ai_intel.answering.conversation_models import qa_conversation_turns
from ai_intel.api.authentication import SessionExpiredError
from ai_intel.api.question_contracts import QuestionRequest
from ai_intel.domain.access import CrossTenantAccessError
from ai_intel.retrieval.persistence_models import grounded_answers

pytestmark = pytest.mark.real_pg


def admit(
    identity,
    *,
    event_ids=(),
    key="synthetic-key",
    conversation=None,
    version=None,
    question="Describe current facts",
):
    engine, _auth, scope, token, _login = identity
    service = ConversationContextService(engine)
    return service.admit(
        QuestionRequest(
            question=question, event_ids=event_ids, conversation_id=conversation, mode="library"
        ),
        scope,
        key,
        conversation_version=version,
        session_token=token,
    )


def test_pg_admission_restart_same_key_and_conflict(context_identity):
    engine, _auth, scope, token, _login = context_identity
    first = admit(context_identity)
    second = admit(context_identity)
    assert first.turn_id == second.turn_id and second.replayed
    restarted = ConversationContextService(engine).read_turn(
        scope, first.turn_id, session_token=token
    )
    assert restarted.context == first.context and restarted.state == "pending"
    with pytest.raises(ConversationFailure, match="idempotency_conflict"):
        admit(context_identity, question="A different request")
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(grounded_answers)) == 1
        assert connection.scalar(select(func.count()).select_from(qa_conversation_turns)) == 1


def test_pg_two_instances_same_key_have_one_turn(context_identity):
    with ThreadPoolExecutor(max_workers=2) as pool:
        turns = list(pool.map(lambda unused: admit(context_identity), range(2)))
    assert turns[0].turn_id == turns[1].turn_id
    assert sum(not turn.replayed for turn in turns) == 1


def test_pg_pending_then_completed_then_unambiguous_followup(context_identity):
    engine, _auth, scope, token, _login = context_identity
    fact = seed_fact(engine, "Synthetic source fact.", cve="CVE-2026-10001")
    first = admit(context_identity, event_ids=(UUID(fact["event_id"]),))
    completed = record_synthetic_completion(
        ConversationContextService(engine), engine, scope, token, first
    )
    assert [event.state for event in completed.history] == ["pending", "completed"]
    followup = admit(
        context_identity,
        key="followup",
        conversation=first.conversation_id,
        version=completed.conversation_version,
        question="它的来源事实是什么？",
    )
    assert followup.context.event_ids == (UUID(fact["event_id"]),)
    assert followup.context.reference_turn_ids == (first.turn_id,)
    assert followup.turn_number == 2
    assert "CVE-2026-10001" in followup.context.retrieval_queries[0].text


def test_pg_two_keys_same_conversation_have_one_active_turn(context_identity):
    engine, _auth, scope, token, _login = context_identity
    first = admit(context_identity)
    record_synthetic_completion(ConversationContextService(engine), engine, scope, token, first)

    def compete(key):
        try:
            return admit(context_identity, key=key, conversation=first.conversation_id, version=1)
        except ConversationFailure as failure:
            return failure.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(compete, ("next-a", "next-b")))
    assert sum(not isinstance(outcome, str) for outcome in outcomes) == 1
    assert "conversation_turn_in_progress" in outcomes


@pytest.mark.parametrize("tenant", ["tenant-a", "tenant-b"])
def test_t31_c06_other_user_cannot_read_or_continue(context_identity, tenant):
    engine, _auth, _scope, _token, login = context_identity
    first = admit(context_identity)
    scope, token = login(tenant=tenant)
    service = ConversationContextService(engine)
    with pytest.raises(CrossTenantAccessError, match="resource not found"):
        service.read_turn(scope, first.turn_id, session_token=token)
    with pytest.raises(CrossTenantAccessError, match="resource not found"):
        service.admit(
            QuestionRequest(
                question="Probe another session",
                conversation_id=first.conversation_id,
                mode="library",
            ),
            scope,
            "other-user",
            conversation_version=1,
            session_token=token,
        )


def test_pg_revoke_cancels_pending_and_preserves_owner_history(context_identity):
    engine, _auth, scope, token, _login = context_identity
    first = admit(context_identity)
    service = ConversationContextService(engine)
    service.revoke(scope, first.conversation_id, session_token=token)
    assert [
        event.state for event in service.read_history(scope, first.turn_id, session_token=token)
    ] == ["pending", "cancelled"]
    with pytest.raises(ConversationFailure, match="conversation_revoked"):
        service.read_turn(scope, first.turn_id, session_token=token)
    with pytest.raises(ConversationFailure, match="conversation_revoked"):
        record_synthetic_completion(service, engine, scope, token, first)


def test_pg_failed_turn_late_completion_does_not_overwrite(context_identity):
    engine, _auth, scope, token, _login = context_identity
    first = admit(context_identity)
    service = ConversationContextService(engine)
    failed = service.fail_turn(
        scope,
        first.turn_id,
        reservation_id=first.reservation_id,
        reason_code="synthetic_verification_failed",
        session_token=token,
    )
    assert [event.state for event in failed.history] == ["pending", "failed"]
    with pytest.raises(ConversationFailure, match="turn_reservation_conflict"):
        record_synthetic_completion(service, engine, scope, token, first)
    with engine.connect() as connection:
        assert connection.scalar(select(grounded_answers.c.response)) == {
            "kind": "failed",
            "error_code": "synthetic_verification_failed",
        }


def test_pg_expired_reservation_is_terminal_without_paid_replay(context_identity):
    engine, _auth, scope, token, _login = context_identity
    first = admit(context_identity)
    with engine.begin() as connection:
        trace = connection.scalar(select(grounded_answers.c.model_trace))
        trace["reservation_expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        connection.execute(update(grounded_answers).values(model_trace=trace))
    expired = admit(context_identity)
    assert expired.replayed and expired.state == "expired"
    assert [event.state for event in expired.history] == ["pending", "expired"]
    with pytest.raises(ConversationFailure, match="turn_reservation_conflict"):
        record_synthetic_completion(ConversationContextService(engine), engine, scope, token, first)


def test_pg_session_revoke_blocks_all_turn_operations(context_identity):
    engine, auth, scope, token, _login = context_identity
    first = admit(context_identity)
    auth.logout(token)
    with pytest.raises(SessionExpiredError):
        ConversationContextService(engine).read_turn(scope, first.turn_id, session_token=token)


def test_pg_existing_conversation_requires_matching_version(context_identity):
    first = admit(context_identity)
    with pytest.raises(ConversationFailure, match="conversation_version_required"):
        admit(context_identity, key="without-version", conversation=first.conversation_id)


def test_pg_foreign_event_never_enters_turn(context_identity):
    engine, _auth, _scope, _token, _login = context_identity
    fact = seed_fact(engine, "Synthetic private fact belonging to tenant-b.", tenant="tenant-b")
    with pytest.raises(CrossTenantAccessError):
        admit(context_identity, event_ids=(UUID(fact["event_id"]),))
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(grounded_answers)) == 0


def test_pg_read_bundle_rejection_commits_expired_history(context_identity):
    engine, _auth, scope, token, _login = context_identity
    service = ConversationContextService(engine)
    turn = admit(context_identity)
    with engine.begin() as connection:
        trace = connection.scalar(select(grounded_answers.c.model_trace))
        trace["reservation_expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        connection.execute(update(grounded_answers).values(model_trace=trace))
    with pytest.raises(ConversationFailure, match="turn_reservation_conflict"):
        service.read_bundle(scope, turn.turn_id, session_token=token, data_mode="fixture")
    assert [
        item.state for item in service.read_history(scope, turn.turn_id, session_token=token)
    ] == ["pending", "expired"]


def test_pg_read_turn_refreshes_state_after_waiting_for_conversation_lock(
    context_identity, monkeypatch
):
    from threading import Event, current_thread

    engine, _auth, scope, token, _login = context_identity
    service = ConversationContextService(engine)
    turn = admit(context_identity)
    read_before_lock, release_reader = Event(), Event()
    lock_conversation = service._conversation

    def pause_reader(session, authenticated_scope, conversation_id):
        if current_thread().name.startswith("r12-state-reader"):
            read_before_lock.set()
            assert release_reader.wait(timeout=4)
        return lock_conversation(session, authenticated_scope, conversation_id)

    monkeypatch.setattr(service, "_conversation", pause_reader)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="r12-state-reader") as pool:
        reading = pool.submit(service.read_turn, scope, turn.turn_id, session_token=token)
        assert read_before_lock.wait(timeout=3)
        try:
            completed = record_synthetic_completion(service, engine, scope, token, turn)
        finally:
            release_reader.set()
        result = reading.result(timeout=3)
    assert result.state == completed.state == "completed"
    assert [item.state for item in result.history] == ["pending", "completed"]
