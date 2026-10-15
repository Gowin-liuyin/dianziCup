import json
import pytest
from sqlalchemy import func,select
from test_review_knowledge_api import api_engine as api_engine, clients as clients
from test_r02_schema_migration import empty_schema_engine as empty_schema_engine
from ai_intel.domain.access import Role
from ai_intel.knowledge.models import job_runs

pytestmark = pytest.mark.real_pg

def write_headers(client,key=None):
    headers = {'origin':'http://localhost:5173','x-csrf-token':client.get('/v1/auth/csrf').json()['csrf_token']}
    if key is not None:
        headers['idempotency-key'] = key
    return headers

def test_missing_source_write_key_is_rejected_before_queue(api_engine,clients):
    client = clients[0](Role.SYSTEM_ADMIN,None)
    headers = write_headers(client)
    responses = [client.post(prefix + '/sources/nvd_ollama/collect',json={'window_end':'2026-10-15T00:00:00Z','max_pages':1},headers=headers) for prefix in ['/v1','/v1','/api/v1','/api/v1']]
    with api_engine.connect() as connection:
        count = connection.scalar(select(func.count()).select_from(job_runs))
    print(json.dumps({'status_codes':[response.status_code for response in responses],'distinct_jobs':len({response.json().get('job_id') for response in responses}),'pg_job_count':count}))
    assert [response.status_code for response in responses] == [422] * 4
    assert count == 0

def test_source_key_is_scoped_to_authenticated_subject(api_engine,clients):
    first,second = clients[0](Role.SYSTEM_ADMIN,None),clients[0](Role.SYSTEM_ADMIN,None)
    body = {'window_end':'2026-10-15T00:00:00Z','max_pages':1}
    responses = [client.post('/v1/sources/nvd_ollama/collect',json=body,headers=write_headers(client,'independent-shared-subject-key')) for client in [first,second]]
    assert all(response.status_code == 202 for response in responses)
    print(json.dumps({'status_codes':[response.status_code for response in responses],'same_job':responses[0].json()['job_id'] == responses[1].json()['job_id']}))
    assert responses[0].json()['job_id'] != responses[1].json()['job_id']

def test_source_key_is_scoped_to_canonical_source_route(api_engine,clients):
    client = clients[0](Role.SYSTEM_ADMIN,None)
    body = {'window_end':'2026-10-15T00:00:00Z','max_pages':1}
    headers = write_headers(client,'independent-shared-route-key')
    responses = [client.post('/v1/sources/' + source + '/collect',json=body,headers=headers) for source in ['nvd_ollama','vllm_vendor']]
    print(json.dumps({'status_codes':[response.status_code for response in responses]}))
    assert [response.status_code for response in responses] == [202,202]
