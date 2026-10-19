"""Independent behavioral counterexamples; synthetic PG only, no model calls."""
import json
from datetime import UTC,datetime,timedelta
from uuid import UUID
import pytest
from sqlalchemy import select,update,func
from tests.r12_conversation_fixtures import context_identity as context_identity,record_synthetic_completion
from tests.r12_hybrid_fixtures import seed_fact
from tests.integration.test_r12_conversation_context_pg import admit
from review_fixtures import conversation_database as conversation_database
from ai_intel.answering.conversation_context import ConversationContextService,resolve_question_context
from ai_intel.answering.conversation_contracts import ConversationFailure
from ai_intel.answering.conversation_models import qa_conversation_turns,qa_conversations
from ai_intel.api.question_contracts import QuestionRequest
from ai_intel.domain.access import AccessScope,Role,CrossTenantAccessError
from ai_intel.knowledge.persistence_models import events
from ai_intel.retrieval.persistence_models import grounded_answers


def test_missing_reference_without_successful_parent_requires_clarification():
    scope=AccessScope.for_authenticated_user('synthetic-owner','tenant-a',Role.ANALYST)
    result=resolve_question_context(QuestionRequest(question='它的修复是什么？',mode='library'),
        conversation_id=UUID('00000000-0000-0000-0000-000000000001'),base_version=0,scope=scope,
        event_references=(),now=datetime.now(UTC))
    assert result.clarification_code is not None, 'unbound pronoun must clarify before retrieval'
    assert result.retrieval_queries==()


def test_pg_missing_reference_does_not_reserve_an_answer(context_identity):
    engine=context_identity[0]
    with pytest.raises(ConversationFailure):
        admit(context_identity,question='它的修复是什么？')
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(grounded_answers))==0


def test_pg_admission_rejection_commits_expired_history(context_identity):
    engine,_auth,scope,token,_login=context_identity
    turn=admit(context_identity)
    with engine.begin() as connection:
        trace=connection.scalar(select(grounded_answers.c.model_trace))
        trace['reservation_expires_at']=(datetime.now(UTC)-timedelta(seconds=1)).isoformat()
        connection.execute(update(grounded_answers).values(model_trace=trace))
    with pytest.raises(ConversationFailure,match='conversation_version_conflict'):
        admit(context_identity,key='stale-version-new-key',conversation=turn.conversation_id,version=0)
    history=ConversationContextService(engine).read_history(scope,turn.turn_id,session_token=token)
    assert [item.state for item in history]==['pending','expired'], 'rejected admission rolled back recovery'
    with engine.connect() as connection:
        assert connection.scalar(select(qa_conversations.c.active_turn_id)) is None


def test_pg_child_admission_verifies_saved_parent_hash(context_identity):
    engine,_auth,scope,token,_login=context_identity
    fact=seed_fact(engine,'Synthetic current source.',cve='CVE-2026-10001')
    first=admit(context_identity,event_ids=(UUID(fact['event_id']),))
    service=ConversationContextService(engine)
    record_synthetic_completion(service,engine,scope,token,first)
    with engine.begin() as connection:
        context=connection.scalar(select(qa_conversation_turns.c.resolved_context))
        context['question']='Corrupt stored parent body; original digest unchanged.'
        connection.execute(update(qa_conversation_turns).values(resolved_context=context))
    with pytest.raises(ConversationFailure,match='context_integrity_unavailable'):
        service.read_turn(scope,first.turn_id,session_token=token)
    with pytest.raises(ConversationFailure,match='context_integrity_unavailable'):
        admit(context_identity,key='child-of-corrupt-parent',conversation=first.conversation_id,
            version=first.conversation_version,question='它的来源是什么？')


def test_pg_owner_completed_turn_survives_current_event_inactive(context_identity):
    engine,_auth,scope,token,_login=context_identity
    fact=seed_fact(engine,'Synthetic historical source.',cve='CVE-2026-10001')
    first=admit(context_identity,event_ids=(UUID(fact['event_id']),))
    service=ConversationContextService(engine)
    record_synthetic_completion(service,engine,scope,token,first)
    with engine.begin() as connection:
        connection.execute(update(events).where(events.c.event_id==fact['event_id']).values(status='withdrawn'))
    restored=service.read_turn(scope,first.turn_id,session_token=token)
    assert restored.state=='completed' and restored.context==first.context


def test_pg_own_same_tenant_owner_update_is_rejected(context_identity):
    from sqlalchemy.exc import IntegrityError
    engine,_auth,_scope,_token,login=context_identity
    first=admit(context_identity)
    other,_other_token=login()
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(update(qa_conversations).where(qa_conversations.c.conversation_id==first.conversation_id).values(user_id=other.user_id))


def test_pg_nonce_change_body_keeps_original_answer_count(context_identity):
    engine=context_identity[0]
    first=admit(context_identity)
    with pytest.raises(ConversationFailure,match='idempotency_conflict'):
        admit(context_identity,question='Changed nonce body')
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(grounded_answers))==1
        assert connection.scalar(select(qa_conversation_turns.c.answer_id))==str(first.answer_id)
