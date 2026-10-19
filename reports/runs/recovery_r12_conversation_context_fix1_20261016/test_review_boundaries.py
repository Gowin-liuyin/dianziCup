"""Independent real writers and ACL wait controls in owned schemas."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID,uuid4
from datetime import UTC,datetime
import pytest
from sqlalchemy import select,text,update
from sqlalchemy.orm import Session
from tests.r12_conversation_fixtures import context_identity as context_identity,record_synthetic_completion
from tests.r12_hybrid_fixtures import seed_fact
from tests.integration.test_r12_evidence_bundle_pg import bundle,public_epochs
from tests.integration.test_r12_conversation_lock_pg import wait_for_lock
from tests.integration.test_r12_conversation_context_pg import admit
from review_fixtures import conversation_database as conversation_database
from ai_intel.answering import evidence_bundle
from ai_intel.answering.conversation_context import ConversationContextService
from ai_intel.api.knowledge_read_service import sources
from ai_intel.domain.access import AccessScope,Role


def test_pg_reader_holds_source_acl_until_constructed(context_identity,monkeypatch):
    engine=context_identity[0]
    fact=seed_fact(engine,'Synthetic public source ACL boundary.')
    public_epochs(engine)
    constructing,release,connected=Event(),Event(),Event()
    pids=[]
    original=evidence_bundle.QuestionEvidenceBundle
    def construct(*args,**kwargs):
        constructing.set()
        assert release.wait(4)
        return original(*args,**kwargs)
    def write_acl():
        with engine.begin() as connection:
            pids.append(connection.scalar(text('SELECT pg_backend_pid()')))
            connected.set()
            connection.execute(update(sources).where(sources.c.source_id==fact['source_id']).values(visibility='tenant',tenant_id='tenant-b'))
    monkeypatch.setattr(evidence_bundle,'QuestionEvidenceBundle',construct)
    with ThreadPoolExecutor(max_workers=2) as pool:
        reading=pool.submit(bundle,context_identity,events=(UUID(fact['event_id']),))
        assert constructing.wait(3)
        writing=pool.submit(write_acl)
        try:
            assert connected.wait(2)
            wait_for_lock(engine,pids[0])
            assert not writing.done()
        finally:
            release.set()
        before=reading.result(4)
        writing.result(4)
    assert before.citations and not before.partial
    monkeypatch.setattr(evidence_bundle,'QuestionEvidenceBundle',original)
    after=bundle(context_identity,events=(UUID(fact['event_id']),))
    assert not after.citations and after.partial


def test_pg_hidden_source_row_lock_does_not_delay_denial(context_identity):
    engine=context_identity[0]
    fact=seed_fact(engine,'Synthetic hidden source.')
    public_epochs(engine)
    with engine.begin() as connection:
        connection.execute(update(sources).where(sources.c.source_id==fact['source_id']).values(visibility='tenant',tenant_id='tenant-b'))
    with engine.begin() as connection:
        connection.execute(select(sources).where(sources.c.source_id==fact['source_id']).with_for_update()).all()
        with ThreadPoolExecutor(max_workers=1) as pool:
            result=pool.submit(bundle,context_identity,events=(UUID(fact['event_id']),)).result(1.5)
    assert not result.citations and result.partial


def test_pg_reverse_enrichment_writer_waits_for_bundle_parents(context_identity,tmp_path,monkeypatch):
    from test_r07_enrichment_inputs_pg import ADMIN,seeded_event
    from ai_intel.enrichment import publication
    from ai_intel.enrichment.inputs import load_event_enrichment_inputs
    from ai_intel.enrichment.signals import enrich_structured_fields
    from ai_intel.enrichment.contracts import DimensionAttempt
    from ai_intel.domain.enums import DimensionStatus
    engine=context_identity[0]
    store,event_id=seeded_event(engine,tmp_path)
    with Session(engine) as session:
        loaded=load_event_enrichment_inputs(session,store,ADMIN,event_id,'review-reverse-writer')
    attempts=enrich_structured_fields(loaded.context,loaded.documents)
    def publish(connected=None,pids=None):
        with Session(engine) as session,session.begin():
            if connected:
                pids.append(session.scalar(text('SELECT pg_backend_pid()')))
                connected.set()
            selected=(DimensionAttempt(dimension='literature',status=DimensionStatus.PENDING),) if connected else attempts
            return publication.publish_enrichment_attempts(session,ADMIN,loaded,selected,
                request_id=uuid4(),recorded_at=loaded.documents[0].observed_at)
    assert publish()
    constructing,release,connected=Event(),Event(),Event()
    pids=[]
    original=evidence_bundle.QuestionEvidenceBundle
    def construct(*args,**kwargs):
        constructing.set()
        assert release.wait(4)
        return original(*args,**kwargs)
    monkeypatch.setattr(evidence_bundle,'QuestionEvidenceBundle',construct)
    with ThreadPoolExecutor(max_workers=2) as pool:
        reading=pool.submit(bundle,context_identity,events=(event_id,))
        assert constructing.wait(3)
        writing=pool.submit(publish,connected,pids)
        try:
            assert connected.wait(2)
            wait_for_lock(engine,pids[0])
            assert not writing.done()
        finally:
            release.set()
        before=reading.result(4)
        assert writing.result(4)
    assert before.citations


def test_pg_legal_merge_keeps_completed_owner_turn_readable(context_identity):
    from ai_intel.knowledge.event_linking import EventRepository
    engine,_auth,scope,token,_login=context_identity
    fact=seed_fact(engine,'Synthetic historic source.',cve='CVE-2026-10001')
    target=seed_fact(engine,'Synthetic corrected grouping.')
    first=admit(context_identity,event_ids=(UUID(fact['event_id']),))
    service=ConversationContextService(engine)
    record_synthetic_completion(service,engine,scope,token,first)
    authority=AccessScope.for_authenticated_user('synthetic-merge-authority',None,Role.SYSTEM_ADMIN)
    with Session(engine) as session,session.begin():
        EventRepository(session,authority).merge_events(uuid4().hex,fact['event_id'],target['event_id'],
            'Synthetic same CVE grouping correction',datetime.now(UTC))
    restored=service.read_turn(scope,first.turn_id,session_token=token)
    assert restored.state=='completed' and restored.context==first.context
