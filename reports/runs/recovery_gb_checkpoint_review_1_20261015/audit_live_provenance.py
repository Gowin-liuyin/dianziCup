import hashlib
import json
from pathlib import Path
import subprocess
from pydantic import SecretStr
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from ai_intel.infrastructure.minio_store import MinioContentStore
from ai_intel.ingestion.parsing.parsers import parse_json_document
from run_command import now

ROOT = Path('D:/wt/gb-stage-review')
RUN = Path(__file__).parent
def private_json(path):
    result = subprocess.run(['wsl','-d','Ubuntu-22.04','-u','root','--exec','cat',path],capture_output=True,text=True,check=True,timeout=15)
    return json.loads(result.stdout)

started = now()
pg = make_url(private_json('/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json')['TEST_DATABASE_URL']).set(database='test_dianzi_r04_pipeline_20261015')
config = private_json('/tmp/dianzi-minio-r02-20261015/private/connection.json')
assert config['endpoint'] == '127.0.0.1:29400'
store = MinioContentStore(config['endpoint'],config['bucket'],SecretStr(config['access_key']),SecretStr(config['secret_key']),secure=False,test_mode=True)
engine = create_engine(pg,connect_args={'options':'-c default_transaction_read_only=on -c statement_timeout=15000'})
with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
    assert connection.scalar(text('SHOW transaction_read_only')) == 'on'
    counts = {name: connection.scalar(text('SELECT count(*) FROM ' + name)) for name in ['events','evidence','grounded_answers','retrieval_chunks']}
    row = dict(connection.execute(text("SELECT response, model_trace,scope_epochs FROM grounded_answers WHERE answer_id=:id"),{'id':'ee73ded8-bfad-59b0-ad16-c251404eb778'}).mappings().one())
    citation = row['response']['citations'][0]
    spans = [dict(value) for value in connection.execute(text('SELECT e.evidence_id,e.revision_id,e.start_offset,e.end_offset,e.quote,e.quote_sha256,b.block_text,b.start_offset AS block_start,b.json_pointer,r.content_hash,r.source_response_hash,r.source_json_pointer,r.canonical_uri FROM evidence e JOIN text_blocks b ON b.block_id=e.block_id JOIN document_revisions r ON r.revision_id=e.revision_id')).mappings()]
    original_record = json.loads((ROOT / 'reports/runs/recovery_r05_controller_20261015/product_live_dc014c9/pg_answer_trace.json').read_text(encoding='utf-8'))['rows'][0]
    raw_artifact = json.loads((ROOT / 'reports/runs/recovery_r05_controller_20261015/product_live_dc014c9/browser_artifacts/r05_real_question-R05-repa-cfb83-and-fixed-revision-evidence/actual_question.json').read_text(encoding='utf-8'))
    matches = {'response_equals_raw':row['response'] == raw_artifact['body'], 'response_equals_pg_receipt':row['response'] == original_record['response'],'trace_equals_receipt':row['model_trace'] == original_record['model_trace'],'epochs_equals_receipt':row['scope_epochs'] == original_record['scope_epochs']}
engine.dispose()
cache = {}
def object_bytes(digest):
    if digest not in cache:
        cache[digest] = store.read_verified(digest)
    return cache[digest]
verified = []
for span in spans:
    relative_start = span['start_offset'] - span['block_start']
    relative_end = span['end_offset'] - span['block_start']
    block_ok = span['block_text'][relative_start:relative_end] == span['quote']
    quote_hash_ok = hashlib.sha256(span['quote'].encode()).hexdigest() == span['quote_sha256']
    member = object_bytes(span['content_hash'])
    response = object_bytes(span['source_response_hash'])
    parsed = parse_json_document(member)
    parser_block_ok = any(block.start_offset == span['block_start'] and block.text == span['block_text'] for block in parsed.blocks)
    target = json.loads(response)
    for part in span['source_json_pointer'].removeprefix('/').split('/'):
        target = target[int(part)] if isinstance(target,list) else target[part.replace('~1','/').replace('~0','~')]
    member_matches_response = json.loads(member) == target
    verified.append({'evidence_id':span['evidence_id'],'revision_id':span['revision_id'],'member_hash':span['content_hash'],'response_hash':span['source_response_hash'],'block_ok':block_ok,'quote_hash_ok':quote_hash_ok,'parser_block_ok':parser_block_ok,'member_matches_response':member_matches_response})
target = next(span for span in spans if span['evidence_id'] == citation['evidence_id'])
citation_matches = citation['revision_id'] == target['revision_id'] and citation['source_uri'] == target['canonical_uri'] and citation['quote'] in target['quote']
assert all(matches.values()) and citation_matches
assert all(all(value[key] for key in ['block_ok','quote_hash_ok','parser_block_ok','member_matches_response']) for value in verified)
report = {'started_at':started,'ended_at':now(),'database':'test_dianzi_r04_pipeline_20261015','transaction_read_only':True,'counts':counts,'receipt_matches':matches,'citation_matches':citation_matches,'complete_browser_elapsed_ms':raw_artifact['complete_browser_elapsed_milliseconds'],'supplier_attempts':len(row['model_trace']['attempts']),'candidate_count':row['model_trace']['candidate_count'],'fee':row['model_trace']['fee'],'unique_verified_objects':len(cache),'verified_evidence':verified,'paid_calls_in_review':0,'quality_or_sla_evaluation':'not_run'}
(RUN / 'live_provenance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k != 'verified_evidence'},ensure_ascii=False))
