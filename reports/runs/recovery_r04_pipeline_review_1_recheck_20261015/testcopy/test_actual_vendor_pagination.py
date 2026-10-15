"""Real public Link/body replay: provider cursor must determine continuation."""
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_r04_source_jobs_pg import NOW, job_engine, queue
from test_r02_schema_migration import empty_schema_engine as empty_schema_engine

from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.network import FetchResult
from ai_intel.ingestion.source_jobs import SOURCE_JOB_TYPE, build_source_page_handler, source_page_url
from ai_intel.knowledge.models import source_cursors
from ai_intel.workers.executor import execute_job

ROOT=Path('/mnt/d/dianzi/reports/runs/recovery_r04_pipeline_review_1_20261015/public_inputs')
BODY=(ROOT/'vendor_pagination_page_1.json').read_bytes()
SECOND=(ROOT/'vendor_pagination_page_2.json').read_bytes()
NEXT_URL='https://api.github.com/repositories/599547518/security-advisories?per_page=10&state=published&after=Y3Vyc29yOnYyOpHOAAg-eQ%3D%3D'
LINK='<'+NEXT_URL+'>; rel="next"'
AFTER=dict(parse_qsl(urlsplit(NEXT_URL).query))['after']
EXPECTED={'after':AFTER,'cursor_version':2}

def test_actual_integer_pages_repeat_and_cursor_url_must_follow_after():
    assert BODY==SECOND
    assert hashlib.sha256(BODY).hexdigest()=='f5007db50489ecebbbfec5d8cc8798eb18cff1d12faf503795ce97c85e6894e1'
    assert [record['ghsa_id'] for record in json.loads(BODY)]==[record['ghsa_id'] for record in json.loads(SECOND)]
    query=dict(parse_qsl(urlsplit(source_page_url('vllm_vendor',EXPECTED)).query))
    assert query=={'per_page':'10','state':'published','after':AFTER}

@pytest.mark.real_pg
def test_actual_next_link_is_committed_as_cursor_instead_of_integer_page(job_engine,tmp_path):
    initial=queue(job_engine,kind='vllm_vendor')
    handler=build_source_page_handler(ContentStore(tmp_path),fetcher=lambda url:FetchResult(url,200,'application/json',BODY,redacted_headers={'Link':LINK}),clock=lambda:NOW)
    assert execute_job(job_engine,initial,'review-actual-link',{SOURCE_JOB_TYPE:handler},clock=lambda:NOW)=='succeeded'
    with Session(job_engine) as session:
        state=session.scalar(select(source_cursors.c.cursor_json))
        assert state['position']==EXPECTED
        assert state['window_complete'] is False
