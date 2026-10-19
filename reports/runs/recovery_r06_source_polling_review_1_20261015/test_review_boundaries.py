"""Independent explicit fixture probes. No real source HTTP or production changes."""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'backend/tests/integration'))
sys.path.insert(0, str(ROOT/'backend/tests'))
from conftest import isolated_test_database_url as isolated_test_database_url
from test_r06_catalog_documents_pg import ADMIN, catalog_engine as catalog_engine

from ai_intel.domain.access import AccessScope, MANAGE_PUBLIC_SOURCES, PermissionDeniedError, Role
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.ingestion.source_jobs import SOURCE_JOB_TYPE, SourcePageRequest, enqueue_source_page
from ai_intel.ingestion.source_polling import SourcePollingError, enqueue_due_source_collections, source_poll_window
from ai_intel.knowledge.models import job_payloads, job_runs, outbox_events

NOW = datetime(2026,10,15,10,17,tzinfo=UTC)


def tick(engine, at=NOW):
    with Session(engine) as session, session.begin():
        return enqueue_due_source_collections(session, ADMIN, at)


def count_jobs(engine):
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(job_runs))


@pytest.mark.parametrize('scope', [AccessScope.for_authenticated_user('tenant-system-admin', 'tenant-a', Role.SYSTEM_ADMIN), AccessScope('forged',None,Role.VIEWER,frozenset({MANAGE_PUBLIC_SOURCES}))])
def test_tenant_system_admin_or_forged_permission_rejected_before_database(scope):
    with pytest.raises(PermissionDeniedError):
        enqueue_due_source_collections(None,scope,NOW)


@pytest.mark.parametrize('kind,at,expected', [('vllm_vendor',NOW.replace(minute=29,second=59,microsecond=999999),NOW.replace(minute=0)),('vllm_vendor',NOW.replace(minute=30),NOW.replace(minute=30)),('nvd_ollama',NOW.replace(minute=59,second=59,microsecond=999999),NOW.replace(minute=0)),('nvd_ollama',NOW.replace(hour=11,minute=0),NOW.replace(hour=11,minute=0))])
def test_utc_boundary_is_floor_not_nearest_bucket(kind,at,expected):
    assert source_poll_window(kind,at) == expected
    assert source_poll_window(kind,at.astimezone(timezone(timedelta(hours=-5)))) == expected


@pytest.mark.parametrize('payload', [b'',b'{}',b'{"source_kind":"unknown"}',json.dumps({'source_kind':'nvd_ollama','window_end':'2026-10-15T10:00:00Z','tenant_id':'attacker'}).encode(),json.dumps({'source_kind':'nvd_ollama','window_end':'2026-10-15T10:00:00Z','remaining_pages':0}).encode(),json.dumps({'source_kind':'nvd_ollama','window_end':'2026-10-15T10:00:00'}).encode()])
def test_invalid_source_payload_aborts_whole_round(catalog_engine,payload):
    with Session(catalog_engine) as session, session.begin():
        enqueue_job(session,None,SOURCE_JOB_TYPE,payload,NOW)
    with pytest.raises(SourcePollingError):
        tick(catalog_engine)
    assert count_jobs(catalog_engine) == 1
    with Session(catalog_engine) as session:
        assert session.scalar(select(func.count()).select_from(outbox_events)) == 1


def test_missing_payload_is_error_not_empty_queue(catalog_engine):
    with Session(catalog_engine) as session, session.begin():
        identifier=enqueue_job(session,None,SOURCE_JOB_TYPE,b'{}',NOW)
        session.execute(delete(job_payloads).where(job_payloads.c.job_id==identifier))
    with pytest.raises(SourcePollingError):
        tick(catalog_engine)
    assert count_jobs(catalog_engine) == 1


@pytest.mark.parametrize('length', [4096,4097])
def test_byte_boundary_accepts_valid_4096_and_rejects_4097(catalog_engine,length):
    payload=SourcePageRequest(source_kind='nvd_ollama',window_end=NOW).model_dump_json().encode()
    payload=payload+b' '*(length-len(payload))
    with Session(catalog_engine) as session, session.begin():
        enqueue_job(session,None,SOURCE_JOB_TYPE,payload,NOW)
    if length == 4096:
        result=tick(catalog_engine)
        assert result.busy_sources==('nvd_ollama',) and len(result.queued_job_ids)==8
    else:
        with pytest.raises(SourcePollingError):
            tick(catalog_engine)
        assert count_jobs(catalog_engine)==1


@pytest.mark.parametrize('status', ['queued','running','retry_wait','waiting_approval'])
def test_all_active_states_defer_manual_or_continuation_source(catalog_engine,status):
    with Session(catalog_engine) as session, session.begin():
        identifier=enqueue_source_page(session,SourcePageRequest(source_kind='osv_ollama',stream_kind='backfill',window_end=NOW,remaining_pages=20),NOW,idempotency_key='manual-review')
        session.execute(update(job_runs).where(job_runs.c.job_id==identifier).values(status=status))
    result=tick(catalog_engine)
    assert result.busy_sources==('osv_ollama',) and len(result.queued_job_ids)==8


def test_terminal_invalid_source_and_unrelated_active_job_do_not_block(catalog_engine):
    with Session(catalog_engine) as session, session.begin():
        identifier=enqueue_job(session,None,SOURCE_JOB_TYPE,b'invalid',NOW)
        session.execute(update(job_runs).where(job_runs.c.job_id==identifier).values(status='failed'))
        enqueue_job(session,None,'record_source_fetch_failure',b'invalid',NOW)
    assert len(tick(catalog_engine).queued_job_ids)==9


@pytest.mark.parametrize('length', [500,501])
def test_queue_admission_threshold_and_bounded_one_tick_growth(catalog_engine,length):
    payload=SourcePageRequest(source_kind='nvd_ollama',window_end=NOW).model_dump_json().encode()
    with Session(catalog_engine) as session, session.begin():
        for _ in range(length):
            enqueue_job(session,None,SOURCE_JOB_TYPE,payload,NOW)
    if length == 500:
        assert len(tick(catalog_engine).queued_job_ids)==8
        assert count_jobs(catalog_engine)==508
        with pytest.raises(SourcePollingError):
            tick(catalog_engine)
        assert count_jobs(catalog_engine)==508
    else:
        with pytest.raises(SourcePollingError):
            tick(catalog_engine)
        assert count_jobs(catalog_engine)==501


PROCESS_SCRIPT='''
import os,sys,time
from datetime import UTC,datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from ai_intel.domain.access import AccessScope,Role
from ai_intel.ingestion.source_polling import enqueue_due_source_collections
try:
    engine=create_engine(os.environ['TEST_DATABASE_URL'],connect_args={'connect_timeout':5})
    with Session(engine) as session,session.begin():
        result=enqueue_due_source_collections(session,AccessScope.for_authenticated_user('independent-process',None,Role.SYSTEM_ADMIN),datetime(2026,10,15,10,17,tzinfo=UTC))
        print(len(result.queued_job_ids),flush=True)
        if os.environ.get('REVIEW_CRASH')=='true':
            time.sleep(60)
    engine.dispose()
except Exception as error:
    print(type(error).__name__)
    sys.exit(1)
'''


def process_environment(engine,**extra):
    return dict(os.environ,TEST_DATABASE_URL=engine.url.render_as_string(hide_password=False),**extra)


def test_four_actual_processes_share_pg_idempotency(catalog_engine):
    processes=[subprocess.Popen([sys.executable,'-B','-c',PROCESS_SCRIPT],env=process_environment(catalog_engine),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(4)]
    queued=[]
    for process in processes:
        output,error=process.communicate(timeout=25)
        assert process.returncode==0,output
        queued.append(int(output.strip()))
    assert sorted(queued)==[0,0,0,9]
    assert count_jobs(catalog_engine)==9
    restarted=subprocess.run([sys.executable,'-B','-c',PROCESS_SCRIPT],env=process_environment(catalog_engine),capture_output=True,text=True,timeout=25)
    assert restarted.returncode==0 and restarted.stdout.strip()=='0'
    assert count_jobs(catalog_engine)==9


def test_killed_process_rolls_back_root_jobs_outbox_and_releases_poll_lock(catalog_engine):
    process=subprocess.Popen([sys.executable,'-B','-c',PROCESS_SCRIPT],env=process_environment(catalog_engine,REVIEW_CRASH='true'),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        assert process.stdout.readline().strip()=='9'
    finally:
        process.kill()
        process.communicate(timeout=10)
    assert count_jobs(catalog_engine)==0
    with Session(catalog_engine) as session:
        assert session.scalar(select(func.count()).select_from(outbox_events))==0
    assert len(tick(catalog_engine).queued_job_ids)==9
