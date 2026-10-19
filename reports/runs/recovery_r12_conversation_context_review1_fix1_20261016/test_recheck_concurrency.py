"""Two targeted controls for the new recovery transaction and historical ACL locks."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID,uuid4
import pytest
from sqlalchemy import select,text,update,func
from tests.r12_conversation_fixtures import context_identity as context_identity,record_synthetic_completion
from tests.r12_hybrid_fixtures import seed_fact
from tests.integration.test_r12_conversation_context_pg import admit
from tests.integration.test_r12_conversation_boundary_fix1_pg import expire_reservation
from tests.integration.test_r12_conversation_lock_pg import wait_for_lock
from review_fixtures import conversation_database as conversation_database
from ai_intel.answering.conversation_context import ConversationContextService
from ai_intel.api.authentication import SessionExpiredError
from ai_intel.api.question_contracts import QuestionRequest
from ai_intel.domain.access import CrossTenantAccessError
from ai_intel.knowledge.persistence_models import events
from ai_intel.retrieval.persistence_models import grounded_answers
from ai_intel.answering.conversation_models import qa_conversations,qa_conversation_turns


def test_recheck_revoke_between_recovery_and_admission_keeps_expired_receipt(context_identity,monkeypatch):
    engine,auth,scope,token,_login=context_identity
    turn=admit(context_identity)
    expire_reservation(engine,turn)
    service=ConversationContextService(engine)
    original=service._recover_expired_active_turn
    def recover_then_revoke(current_scope,conversation_id,*,session_token):
        original(current_scope,conversation_id,session_token=session_token)
        auth.logout(session_token)
    monkeypatch.setattr(service,'_recover_expired_active_turn',recover_then_revoke)
    with pytest.raises(SessionExpiredError):
        service.admit(QuestionRequest(question='Describe current facts',conversation_id=turn.conversation_id,mode='library'),
            scope,'revoked-between-transactions',conversation_version=turn.conversation_version,session_token=token)
    with engine.connect() as connection:
        assert connection.scalar(select(grounded_answers.c.model_trace))['conversation_state']=='expired'
        assert connection.scalar(select(qa_conversations.c.active_turn_id)) is None
        assert connection.scalar(select(func.count()).select_from(grounded_answers))==1


def test_recheck_historical_acl_update_waits_and_later_read_is_denied(context_identity,monkeypatch):
    engine,_auth,scope,token,_login=context_identity
    fact=seed_fact(engine,'Synthetic history ACL lock boundary.',cve='CVE-2026-10001')
    turn=admit(context_identity,event_ids=(UUID(fact['event_id']),))
    service=ConversationContextService(engine)
    record_synthetic_completion(service,engine,scope,token,turn)
    locked,release,writer_ready=Event(),Event(),Event()
    writer_pids=[]
    original=service._authorize_turn_references
    def hold_after_acl(current_session,current_scope,current_turn):
        result=original(current_session,current_scope,current_turn)
        locked.set()
        assert release.wait(4)
        return result
    def hide_event():
        with engine.begin() as connection:
            writer_pids.append(connection.scalar(text('SELECT pg_backend_pid()')))
            writer_ready.set()
            connection.execute(update(events).where(events.c.event_id==fact['event_id']).values(visibility='tenant',tenant_id='tenant-b',scope_key='tenant:tenant-b'))
    monkeypatch.setattr(service,'_authorize_turn_references',hold_after_acl)
    with ThreadPoolExecutor(max_workers=2) as pool:
        reading=pool.submit(service.read_turn,scope,turn.turn_id,session_token=token)
        assert locked.wait(3)
        writing=pool.submit(hide_event)
        try:
            assert writer_ready.wait(2)
            wait_for_lock(engine,writer_pids[0])
            assert not writing.done()
        finally:
            release.set()
        before=reading.result(4)
        writing.result(4)
    assert before.state=='completed' and before.context==turn.context
    monkeypatch.setattr(service,'_authorize_turn_references',original)
    with pytest.raises(CrossTenantAccessError):
        service.read_turn(scope,turn.turn_id,session_token=token)


@pytest.mark.parametrize('field,value',[('user_id','other-owner'),('tenant_id','tenant-b'),('tenant_id',None)])
def test_recheck_insert_owner_constraint_is_not_masked_by_update_guard(context_identity,field,value):
    from sqlalchemy.exc import IntegrityError
    engine,_auth,_scope,_token,login=context_identity
    turn=admit(context_identity)
    if field=='user_id': value=login()[0].user_id
    with engine.connect() as connection:
        answer=dict(connection.execute(select(grounded_answers)).mappings().one())
        stored_turn=dict(connection.execute(select(qa_conversation_turns)).mappings().one())
        assert connection.scalar(text("SELECT tgenabled FROM pg_trigger WHERE tgname='qa_conversation_turns_immutable' AND tgrelid='qa_conversation_turns'::regclass"))=='O'
    answer['answer_id']=str(uuid4())
    stored_turn.update(turn_id=uuid4(),turn_number=2,answer_id=answer['answer_id'])
    stored_turn[field]=value
    with pytest.raises(IntegrityError,match='conversation owner mismatch'):
        with engine.begin() as connection:
            connection.execute(grounded_answers.insert().values(**answer))
            connection.execute(qa_conversation_turns.insert().values(**stored_turn))
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(grounded_answers))==1
        assert connection.scalar(select(func.count()).select_from(qa_conversation_turns))==1
