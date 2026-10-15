"""Independently exercise maximum encoded cursor through two PG jobs, no HTTP."""
from datetime import timedelta
from urllib.parse import urlencode

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_r02_schema_migration import empty_schema_engine as empty_schema_engine
from test_r04_source_jobs_pg import NOW, FIXTURES, job_engine, queue

from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.network import FetchResult
from ai_intel.ingestion.source_documents import SourceResponse, SourceDocumentError, _request_parameters
from ai_intel.ingestion.source_jobs import SOURCE_JOB_TYPE, build_source_page_handler
from ai_intel.knowledge.models import fetch_attempts, job_runs, source_cursors
from ai_intel.workers.executor import execute_job

@pytest.mark.real_pg
def test_maximum_encoded_after_survives_pg_page_and_observation_url(job_engine,tmp_path):
    after='/+='*682+'ab'
    assert len(after)==2048
    query=urlencode({'per_page':10,'state':'published','after':after})
    next_url='https://api.github.com/repos/vllm-project/vllm/security-advisories?'+query
    assert 6000<len(next_url)<=6500
    body=(FIXTURES/'vllm_api_page_20261015_public.json').read_bytes()
    seen=[]
    clock=[NOW]
    def fetch(url):
        seen.append(url)
        if len(seen)==1:
            return FetchResult(url,200,'application/json',body,{'Link':'<'+next_url+'>; rel="next"'})
        assert url==next_url
        return FetchResult(url,200,'application/json',b'[]')
    handler=build_source_page_handler(ContentStore(tmp_path),fetcher=fetch,clock=lambda:clock[0])
    job_id=queue(job_engine,kind='vllm_vendor')
    assert execute_job(job_engine,job_id,'cursor-max-first',{SOURCE_JOB_TYPE:handler},clock=lambda:clock[0])=='succeeded'
    with Session(job_engine) as session:
        assert session.scalar(select(source_cursors.c.cursor_json))['position']=={'cursor_version':2,'after':after}
        next_job=session.scalar(select(job_runs.c.job_id).where(job_runs.c.job_type==SOURCE_JOB_TYPE,job_runs.c.job_id!=job_id))
    clock[0]+=timedelta(seconds=8)
    assert execute_job(job_engine,next_job,'cursor-max-second',{SOURCE_JOB_TYPE:handler},clock=lambda:clock[0])=='succeeded'
    with Session(job_engine) as session:
        assert next_url in session.scalars(select(fetch_attempts.c.final_url)).all()
        assert session.scalar(select(source_cursors.c.cursor_json))['window_complete'] is True
    assert len(seen)==2

def test_nvd_url_still_keeps_original_two_thousand_character_boundary():
    url='https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=ollama&resultsPerPage=20&startIndex='+('0'*2000)
    with pytest.raises(SourceDocumentError,match='invalid source request URL'):
        _request_parameters(SourceResponse('nvd_ollama',b'{}',url,NOW))
