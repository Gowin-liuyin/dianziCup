"""Independent observable edge inputs; recorded fixture and own real PG/MinIO."""
import hashlib
import json
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from minio import Minio
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_r02_schema_migration import empty_schema_engine as empty_schema_engine
from test_r04_source_documents import page_engine, persist, table_counts, vendor_response
from test_r04_source_jobs_pg import NOW, job_engine, nvd_response, queue

from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.minio_store import MinioContentStore
from ai_intel.infrastructure.network import FetchResult
from ai_intel.ingestion.source_jobs import SOURCE_JOB_TYPE, build_source_page_handler
from ai_intel.knowledge.models import document_revisions, fetch_attempts, job_runs, source_cursors
from ai_intel.knowledge.revisions import cleanup_unreferenced_object
from ai_intel.workers.executor import execute_job

pytestmark=pytest.mark.real_pg

def test_two_real_nvd_pages_continue_from_committed_offset(job_engine,tmp_path):
    now=[NOW]
    urls=[]
    def fetch(url):
        urls.append(url)
        result=nvd_response(next_page=True)
        page=json.loads(result.body)
        if 'startIndex=1' in url:
            page['startIndex']=1
            page['vulnerabilities'][0]['cve']['id']='CVE-2026-54321'
        return FetchResult(result.final_url,200,'application/json',json.dumps(page).encode())
    initial=queue(job_engine)
    handler=build_source_page_handler(ContentStore(tmp_path),fetcher=fetch,clock=lambda:now[0])
    assert execute_job(job_engine,initial,'review-1',{SOURCE_JOB_TYPE:handler},clock=lambda:now[0])=='succeeded'
    with Session(job_engine) as session:
        following=session.scalar(select(job_runs.c.job_id).where(job_runs.c.job_id!=initial))
    now[0]+=timedelta(seconds=8)
    assert execute_job(job_engine,following,'review-2',{SOURCE_JOB_TYPE:handler},clock=lambda:now[0])=='succeeded'
    with Session(job_engine) as session:
        assert session.scalar(select(func.count()).select_from(document_revisions))==2
        cursor=session.execute(select(source_cursors)).mappings().one()
        assert cursor['cursor_json']['window_complete'] is True
        assert cursor['cursor_json']['position']=={}
        assert session.scalar(select(func.count()).select_from(job_runs))==2
    assert urls[0].endswith('startIndex=0') and urls[1].endswith('startIndex=1')

def test_vendor_full_page_requires_and_commits_empty_successor(job_engine,tmp_path):
    now=[NOW]
    base=json.loads(vendor_response().body)[0]
    page=[]
    for number in range(10):
        record=dict(base)
        suffix='23456789cf'[number]
        record['ghsa_id']='GHSA-6cxc-2vcg-w5q'+suffix
        record['html_url']='https://github.com/vllm-project/vllm/security/advisories/'+record['ghsa_id']
        record['cve_id']=None
        page.append(record)
    urls=[]
    def fetch(url):
        urls.append(url)
        return FetchResult('https://api.github.com',200,'application/json',json.dumps(page).encode() if url.endswith('page=1') else b'[]')
    initial=queue(job_engine,kind='vllm_vendor')
    handler=build_source_page_handler(ContentStore(tmp_path),fetcher=fetch,clock=lambda:now[0])
    assert execute_job(job_engine,initial,'vendor-1',{SOURCE_JOB_TYPE:handler},clock=lambda:now[0])=='succeeded'
    with Session(job_engine) as session:
        following=session.scalar(select(job_runs.c.job_id).where(job_runs.c.job_id!=initial))
        assert session.execute(select(source_cursors.c.cursor_json)).scalar()['position']=={'page':2}
    now[0]+=timedelta(seconds=8)
    assert execute_job(job_engine,following,'vendor-2',{SOURCE_JOB_TYPE:handler},clock=lambda:now[0])=='succeeded'
    with Session(job_engine) as session:
        assert session.scalar(select(func.count()).select_from(document_revisions))==10
        assert session.scalar(select(func.count()).select_from(fetch_attempts))==2
        assert session.execute(select(source_cursors.c.cursor_json)).scalar()['window_complete'] is True
    assert len(urls)==2 and urls[1].endswith('page=2')

def test_source_effects_are_rolled_back_when_job_fence_expires(job_engine,tmp_path):
    now=[NOW]
    def fetch(url):
        now[0]+=timedelta(seconds=61)
        return nvd_response()
    job=queue(job_engine)
    handler=build_source_page_handler(ContentStore(tmp_path),fetcher=fetch,clock=lambda:now[0])
    assert execute_job(job_engine,job,'expired-source-worker',{SOURCE_JOB_TYPE:handler},clock=lambda:now[0])=='lease_lost'
    with Session(job_engine) as session:
        for table in (document_revisions,fetch_attempts,source_cursors):
            assert session.scalar(select(func.count()).select_from(table))==0

@pytest.mark.parametrize('status,expected,code',[(429,'retry_wait','source_rate_limited'),(403,'blocked','source_auth_denied'),(404,'failed','source_client_error'),(503,'retry_wait','source_server_error')])
def test_classified_http_failure_keeps_prior_source_success(job_engine,tmp_path,status,expected,code):
    now=[NOW]
    initial=queue(job_engine)
    store=ContentStore(tmp_path)
    first=build_source_page_handler(store,fetcher=lambda url:nvd_response(),clock=lambda:now[0])
    assert execute_job(job_engine,initial,'success-before-failure',{SOURCE_JOB_TYPE:first},clock=lambda:now[0])=='succeeded'
    now[0]+=timedelta(seconds=8)
    later=queue(job_engine)
    failed=build_source_page_handler(store,fetcher=lambda url:FetchResult('https://services.nvd.nist.gov',status,'application/json',b'{}',redacted_headers={'Retry-After':'17'}),clock=lambda:now[0])
    assert execute_job(job_engine,later,'failure-after-success',{SOURCE_JOB_TYPE:failed},clock=lambda:now[0])==expected
    with Session(job_engine) as session:
        assert session.scalar(select(func.count()).select_from(document_revisions))==1
        assert session.scalar(select(func.count()).select_from(fetch_attempts))==1
        assert session.execute(select(source_cursors.c.cursor_json)).scalar()['window_complete'] is True
        assert session.scalar(select(job_runs.c.error_code).where(job_runs.c.job_id==later))==code

def test_real_minio_full_response_reference_blocks_gc(page_engine,register_sensitive_failure_value):
    private=json.loads(Path('/tmp/dianzi-minio-r02-20261015/private/connection.json').read_text())
    assert private['endpoint']=='127.0.0.1:29400'
    access,secret=SecretStr(private['access_key']),SecretStr(private['secret_key'])
    register_sensitive_failure_value(access)
    register_sensitive_failure_value(secret)
    bucket='test-dianzi-r04-pipeline-review-'+uuid4().hex[:12]
    client=Minio(private['endpoint'],access_key=access.get_secret_value(),secret_key=secret.get_secret_value(),secure=False,region='us-east-1')
    client.make_bucket(bucket)
    store=MinioContentStore(private['endpoint'],bucket,access,secret,secure=False,test_mode=True)
    response=vendor_response()
    try:
        saved=persist(page_engine,store,response)
        assert store.read_verified(saved.response_content_hash)==response.body
        with Session(page_engine) as session,session.begin():
            assert cleanup_unreferenced_object(session,store,saved.response_content_hash) is False
        assert store.read_verified(saved.response_content_hash)==response.body
        assert hashlib.sha256(response.body).hexdigest()==saved.response_content_hash
        assert table_counts(page_engine)[0]==1
    finally:
        for item in client.list_objects(bucket,recursive=True):
            client.remove_object(bucket,item.object_name)
        client.remove_bucket(bucket)
