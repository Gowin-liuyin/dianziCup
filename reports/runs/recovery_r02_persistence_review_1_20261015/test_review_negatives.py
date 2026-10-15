"""非作者真实PG负例；只写专属run目录，业务模块从固定WT导入。"""
from pathlib import Path
import importlib.util, json
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
WT=Path(r'C:\Users\yinha\.codex\worktrees\recovery-r02-review\dianzi')
LOG=Path(r'D:\dianzi\reports\runs\recovery_r02_persistence_review_1_20261015')
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result
conf=module(WT/'backend/tests/conftest.py','review_conf')
fixtures=module(WT/'backend/tests/integration/test_r02_knowledge_revisions.py','review_fixed_helpers')
isolated_test_database_url=conf.isolated_test_database_url
migrated_engine=conf.migrated_engine
from ai_intel.domain.values import Identifier
from ai_intel.domain.records import ScoreValue, VersionRangeValue
from ai_intel.knowledge.event_linking import EventSubmission,EventIdentifier,EventRepository,EventLinkingError
from ai_intel.knowledge.persistence import KnowledgeRepository,ClaimSubmission,ClaimRelation,EvidenceLink,KnowledgePublicationError
from ai_intel.knowledge.persistence_models import event_external_ids, claims
from ai_intel.knowledge.models import document_revisions
from ai_intel.knowledge.revisions import save_document_revision,add_text_block,attach_evidence_span
from ai_intel.infrastructure.content_store import ContentStore
NOW=fixtures.NOW

def write_case(name,observed):
    (LOG/(name+'.observed.json')).write_text(json.dumps(observed,ensure_ascii=False,indent=2),encoding='utf-8')

def later_claim(engine,tmp_path,first,value,authority=''):
    at=NOW+timedelta(seconds=1)
    with engine.begin() as conn:
        doc=conn.execute(select(document_revisions.c.document_id).where(document_revisions.c.revision_id==first.revision_id.value)).scalar_one()
        saved=save_document_revision(conn,ContentStore(tmp_path/'objects'),doc,b'later independent field','public',None,at)
        block=add_text_block(conn,saved.revision_id,1,100,107,'changed')
        evidence=attach_evidence_span(conn,saved.revision_id,100,107,'paragraph','changed',True,'public',None,at,block_id=block,verified_at=at)
    return ClaimSubmission.model_validate({**first.model_dump(),'record':first.record.model_copy(update={'claim_id':Identifier(value=str(uuid4())),'object_value':value}).model_dump(),'scoring_authority':authority,'revision_id':{'value':saved.revision_id},'evidence_links':[{'evidence_id':{'value':evidence},'support_kind':'supports','validation_status':'validated'}]})

def test_existing_event_cannot_gain_a_second_distinct_cve(migrated_engine,tmp_path):
    source=fixtures.prepared_submission(migrated_engine,tmp_path)
    scope=source.record.scope
    first_id='CVE-2026-'+str(int(uuid4().hex[:8],16))
    second_id='CVE-2026-'+str(int(uuid4().hex[:8],16))
    first=EventSubmission(event_id=Identifier(value=str(uuid4())),event_type='vulnerability',title='independent two-CVE negative',scope=scope,external_ids=(EventIdentifier(id_type='cve',id_value=first_id),),source_revision_ids=(source.revision_id,))
    second=first.model_copy(update={'external_ids':(EventIdentifier(id_type='cve',id_value=second_id),)})
    with Session(migrated_engine) as session,session.begin():
        repo=EventRepository(session,fixtures.publisher_scope(scope))
        repo.publish_events(str(uuid4()),scope,(first,),NOW)
        try:
            repo.publish_events(str(uuid4()),scope,(second,),NOW)
        except EventLinkingError:
            return
        ids=session.execute(select(event_external_ids.c.id_value).where(event_external_ids.c.event_id==first.event_id.value)).scalars().all()
        write_case('existing_event_second_cve',{'event_id':first.event_id.value,'expected':'reject conflicting CVE or keep distinct event','actual_external_ids':ids})
        assert len(ids)==1,'One existing event accepted two distinct CVEs across valid submissions'

@pytest.mark.parametrize('boundary',['branch','authority'])
def test_supersede_does_not_erase_independent_branch_or_authority(migrated_engine,tmp_path,boundary):
    if boundary=='branch':
        first_value=VersionRangeValue(kind='version_range',ecosystem='pypi',expression='<1.5',branch='1.x')
        second_value=VersionRangeValue(kind='version_range',ecosystem='pypi',expression='<2.5',branch='2.x')
        predicate='affected_versions'
        first_authority=second_authority=''
    else:
        first_value=ScoreValue(kind='score',score=5,authority='vendor-A')
        second_value=ScoreValue(kind='score',score=9,authority='vendor-B')
        predicate='cvss_score'
        first_authority='vendor-A'
        second_authority='vendor-B'
    first=fixtures.prepared_submission(migrated_engine,tmp_path,value=first_value,predicate=predicate,scoring_authority=first_authority)
    fixtures.publish_submission(migrated_engine,first)
    second=later_claim(migrated_engine,tmp_path,first,second_value,second_authority)
    relation=ClaimRelation(left_claim_id=first.record.claim_id,right_claim_id=second.record.claim_id,relation_type='supersedes',reason='same document changed another independent field')
    with Session(migrated_engine) as session,session.begin():
        repo=KnowledgeRepository(session,fixtures.publisher_scope(first.record.scope))
        try:
            repo.publish(str(uuid4()),first.record.scope,(second,),relations=(relation,),created_at=NOW+timedelta(seconds=2))
        except KnowledgePublicationError:
            return
        status=repo.get_claim(first.record.claim_id.value).claim_status.value
        current=repo.list_current_claims(candidate_ids=(first.record.claim_id.value,second.record.claim_id.value))
        write_case('supersede_'+boundary,{'expected':'independent '+boundary+' remains supported/current or relation rejected','actual_old_status':status,'current_ids':[x.claim_id.value for x in current],'old_id':first.record.claim_id.value,'new_id':second.record.claim_id.value})
        assert status=='supported','Supersede erased an independent '+boundary+' assertion'

def test_dispute_must_not_promote_unverified_model_hypothesis(migrated_engine,tmp_path):
    first=fixtures.prepared_submission(migrated_engine,tmp_path,claim_origin='model_hypothesis',claim_status='unverified',condition='true')
    second=fixtures.prepared_submission(migrated_engine,tmp_path,condition='false')
    second=ClaimSubmission.model_validate({**second.model_dump(),'record':second.record.model_copy(update={'subject':first.record.subject}).model_dump()})
    relation=ClaimRelation(left_claim_id=first.record.claim_id,right_claim_id=second.record.claim_id,relation_type='disputed',reason='synthetic contradictory condition')
    with Session(migrated_engine) as session,session.begin():
        repo=KnowledgeRepository(session,fixtures.publisher_scope(first.record.scope))
        try:
            repo.publish(str(uuid4()),first.record.scope,(first,second),relations=(relation,),created_at=NOW)
        except KnowledgePublicationError:
            return
        old=repo.get_claim(first.record.claim_id.value)
        current=repo.list_current_claims(candidate_ids=(first.record.claim_id.value,))
        write_case('dispute_model_hypothesis',{'expected':'model hypothesis remains unverified and absent current factual candidates','actual_model_status':old.claim_status.value,'actual_current_claims':[item.model_dump(mode='json') for item in current]})
        assert old.claim_status.value=='unverified' and current==(),'Dispute promoted model hypothesis into current verified candidates'

def test_payload_bytes_are_persisted_readable_after_new_connection(migrated_engine,tmp_path):
    from ai_intel.knowledge.persistence import publication_payload_digest
    from ai_intel.knowledge.persistence_models import change_events,publication_receipts
    from ai_intel.knowledge.models import job_runs,outbox_events
    first=fixtures.prepared_submission(migrated_engine,tmp_path)
    receipt=fixtures.publish_submission(migrated_engine,first)
    with migrated_engine.connect() as connection:
        payload=connection.execute(select(change_events.c.payload).where(change_events.c.change_id==receipt.change_id)).scalar_one()
        job=connection.execute(select(job_runs.c.payload_ref).where(job_runs.c.job_id==receipt.job_id)).scalar_one()
        outbox=connection.execute(select(outbox_events.c.payload_ref).where(outbox_events.c.event_id==receipt.outbox_id)).scalar_one()
        stored=connection.execute(select(publication_receipts.c.payload_sha256).where(publication_receipts.c.receipt_id==receipt.receipt_id)).scalar_one()
    payload_bytes=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
    assert len(payload_bytes)>0
    assert publication_payload_digest(payload)==stored==receipt.payload_sha256
    assert job==outbox=='pg:change:'+receipt.change_id
    assert payload['claims'][0]['record']['claim_id']['value']==first.record.claim_id.value
    write_case('persisted_payload',{'payload_bytes_length':len(payload_bytes),'hash_matches_receipt':True,'job_ref_equals_outbox_ref':True,'change_id':receipt.change_id,'fresh_connection_used':True})

def test_same_timestamp_history_uses_transition_sequence(migrated_engine,tmp_path):
    first,second=fixtures.conflict_pair(migrated_engine,tmp_path)
    fixtures.publish_submission(migrated_engine,first)
    relation=ClaimRelation(left_claim_id=first.record.claim_id,right_claim_id=second.record.claim_id,relation_type='disputed',reason='same timestamp distinct known transition')
    with Session(migrated_engine) as session,session.begin():
        repo=KnowledgeRepository(session,fixtures.publisher_scope(first.record.scope))
        repo.publish(str(uuid4()),first.record.scope,(second,),relations=(relation,),created_at=NOW)
    from ai_intel.knowledge.persistence_models import claim_status_history
    with Session(migrated_engine) as session:
        repo=KnowledgeRepository(session,fixtures.publisher_scope(first.record.scope))
        states=[repo.get_claim(first.record.claim_id.value,known_at=NOW).claim_status.value for unused in range(5)]
        sequence=session.execute(select(claim_status_history.c.status,claim_status_history.c.transition_sequence).where(claim_status_history.c.claim_id==first.record.claim_id.value).order_by(claim_status_history.c.transition_sequence)).all()
    assert states==['disputed']*5
    assert [row[0] for row in sequence]==['supported','disputed']
    assert sequence[0][1]<sequence[1][1]
    write_case('same_timestamp_history',{'statuses':states,'transitions':[{'status':row[0],'sequence':row[1]} for row in sequence]})

def test_content_a_b_a_bytes_reread_independently(migrated_engine,tmp_path):
    from ai_intel.knowledge.revisions import record_fetch_attempt
    doc=str(uuid4())
    store=ContentStore(tmp_path/'objects')
    saved=[]
    with migrated_engine.begin() as connection:
        fixtures.seed_document(connection,doc,'public',None)
        for index,payload in enumerate((b'independent-A',b'independent-B',b'independent-A')):
            saved.append(save_document_revision(connection,store,doc,payload,'public',None,NOW+timedelta(seconds=index)))
    with migrated_engine.connect() as connection:
        rows=connection.execute(select(document_revisions.c.revision_id,document_revisions.c.content_hash).where(document_revisions.c.document_id==doc).order_by(document_revisions.c.revision_number)).all()
    reread=ContentStore(tmp_path/'objects')
    actual=[reread.read_verified(row[1]) for row in rows]
    assert actual==[b'independent-A',b'independent-B',b'independent-A']
    assert rows[0][0]!=rows[2][0] and rows[0][1]==rows[2][1]
    write_case('a_b_a_read_bytes',{'revision_ids':[row[0] for row in rows],'same_first_third_hash':True,'bytes_match_originals':True,'fresh_store_reader':True})
