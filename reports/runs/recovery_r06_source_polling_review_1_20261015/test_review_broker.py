"""Real 60-second beat -> Redis -> PG -> fixture source worker, then disabled restart."""

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC,datetime
from pathlib import Path
from threading import Thread
from uuid import uuid4

import pytest
from redis import Redis
from sqlalchemy import func,select,text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

ROOT=Path(__file__).resolve().parents[3]
RUN=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'backend/tests/integration'))
sys.path.insert(0,str(ROOT/'backend/tests'))
from conftest import isolated_test_database_url as isolated_test_database_url
from test_r06_catalog_documents_pg import catalog_engine as catalog_engine

from ai_intel.ingestion.source_jobs import SourcePageRequest,enqueue_source_page
from ai_intel.ingestion.source_catalog import CATALOG_SOURCES
from ai_intel.knowledge.models import fetch_attempts,job_runs,job_payloads,source_cursors,source_page_receipts


def wait_for(predicate,timeout):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate():
            return
        time.sleep(0.25)
    raise AssertionError('actual process state did not arrive within bounded observation')


def test_actual_default_schedule_dispatches_and_disabled_restart_preserves_history(catalog_engine):
    identifier='poll_review_'+uuid4().hex
    prefix=identifier+':'
    queue=identifier+'_queue'
    redis_url=make_url(os.environ['TEST_REDIS_URL']).set(database='15').render_as_string(hide_password=False)
    client=Redis.from_url(redis_url,socket_connect_timeout=3,socket_timeout=3)
    before={key for key in client.scan_iter()}
    assert not list(client.scan_iter(match=prefix+'*'))
    environment=dict(os.environ,DATABASE_URL=catalog_engine.url.render_as_string(hide_password=False),REDIS_URL=redis_url,APP_ENV='test',DATA_MODE='fixture',SOURCE_POLLING_ENABLED='true',REVIEW_QUEUE=queue,REVIEW_BROKER_PREFIX=prefix)
    schema=re.search(r'search_path=(test_r06_catalog_[0-9a-f]{32})',catalog_engine.url.query['options'])[1]
    assert catalog_engine.url.database=='test_dianzi_r06_catalog_polling_20261015'
    with catalog_engine.begin() as connection:
        previous=connection.scalar(text("SELECT value FROM pg_db_role_setting,unnest(setconfig) value WHERE setdatabase=(SELECT oid FROM pg_database WHERE datname=current_database()) AND setrole=0 AND value LIKE 'search_path=%'"))
        assert previous is None
        connection.exec_driver_sql('ALTER DATABASE test_dianzi_r06_catalog_polling_20261015 SET search_path TO '+schema)
    processes=[]
    phase_receipts=[]
    def start(label,beat=False):
        path=RUN/(identifier+'_'+label+'.log')
        output=path.open('w',encoding='utf-8')
        arguments=[sys.executable,'-B',str(RUN/'broker_fixture_entry.py')]
        if beat:
            arguments+=['beat','--loglevel=WARNING','--schedule',str(RUN/(identifier+'_'+label+'.beat')),'--pidfile',str(RUN/(identifier+'_'+label+'.pid'))]
        else:
            arguments+=['worker','--pool=solo','--loglevel=WARNING','--without-gossip','--without-mingle','--without-heartbeat','-Q',queue,'-n',label+'@'+identifier]
        process=subprocess.Popen(arguments,cwd=ROOT/'backend',env=environment,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        def drain():
            for line in process.stdout:
                for value in [environment['DATABASE_URL'],environment['REDIS_URL'],make_url(environment['DATABASE_URL']).password,make_url(environment['REDIS_URL']).password]:
                    if value:
                        line=line.replace(value,'[redacted fixture credential]')
                output.write(line)
                output.flush()
        thread=Thread(target=drain,daemon=True)
        thread.start()
        processes.append((label,process,output,path,datetime.now().astimezone().isoformat(timespec='seconds'),thread))
        return process
    def stop_phase():
        for label,process,output,path,started,thread in processes:
            controlled=process.poll() is None
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            thread.join(timeout=5)
            output.close()
            contents=path.read_text(encoding='utf-8')
            for value in [environment['DATABASE_URL'],environment['REDIS_URL'],make_url(environment['DATABASE_URL']).password,make_url(environment['REDIS_URL']).password]:
                if value:
                    contents=contents.replace(value,'[redacted fixture credential]')
            path.write_text(contents,encoding='utf-8')
            phase_receipts.append({'label':label,'pid':process.pid,'started_at':started,'stopped_at':datetime.now().astimezone().isoformat(timespec='seconds'),'exit_code':process.returncode,'log':path.name,'pool':'beat' if 'beat' in label else 'native solo','stop':'review-controlled termination' if controlled else 'process exited before cleanup'})
        processes.clear()
    def osv_success_count():
        with Session(catalog_engine) as session:
            return session.scalar(select(func.count()).select_from(fetch_attempts).where(fetch_attempts.c.source_id==CATALOG_SOURCES['osv_ollama'].source_id,fetch_attempts.c.outcome=='succeeded'))
    def jobs_count():
        with Session(catalog_engine) as session:
            return session.scalar(select(func.count()).select_from(job_runs))
    try:
        enabled_start=time.monotonic()
        start('enabled_worker')
        start('enabled_beat',beat=True)
        wait_for(lambda:jobs_count()==9,85)
        wait_for(lambda:osv_success_count()==1,20)
        assert time.monotonic()-enabled_start>=59
        with Session(catalog_engine) as session:
            job_ids=set(session.scalars(select(job_runs.c.job_id)))
            payloads={str(row[0]):hashlib.sha256(row[1]).hexdigest() for row in session.execute(select(job_payloads.c.job_id,job_payloads.c.payload))}
            assert len(job_ids)==9 and len(payloads)==9
            assert session.scalar(select(func.count()).select_from(source_page_receipts))==1
            source_row=session.execute(select(source_cursors).where(source_cursors.c.source_id==CATALOG_SOURCES['osv_ollama'].source_id)).mappings().one()
            assert source_row['stream_kind']=='live' and source_row['cursor_json']['window_complete'] is True
        stop_phase()
        environment['SOURCE_POLLING_ENABLED']='false'
        now=datetime.now(UTC)
        with Session(catalog_engine) as session,session.begin():
            manual_id=enqueue_source_page(session,SourcePageRequest(source_kind='osv_ollama',stream_kind='live',window_end=now,remaining_pages=1),now,idempotency_key='review-manual-after-disable')
        disabled_start=time.monotonic()
        start('disabled_worker')
        start('disabled_beat',beat=True)
        wait_for(lambda:osv_success_count()==2,25)
        while time.monotonic()-disabled_start<65:
            assert jobs_count()==10
            time.sleep(0.25)
        assert jobs_count()==10
        with Session(catalog_engine) as session:
            assert set(session.scalars(select(job_runs.c.job_id)))==job_ids|{manual_id}
            for identifier_value,payload in session.execute(select(job_payloads.c.job_id,job_payloads.c.payload)):
                if identifier_value in payloads:
                    assert hashlib.sha256(payload).hexdigest()==payloads[identifier_value]
            assert session.scalar(select(func.count()).select_from(source_page_receipts))==2
            assert session.scalar(select(job_runs.c.status).where(job_runs.c.job_id==manual_id))=='succeeded'
        print('actual 60-second default beat -> broker -> durable PG -> offline OSV source handler passed; disabled 65-second restart kept nine roots and completed one existing manual job')
    finally:
        stop_phase()
        owned_keys=list(client.scan_iter(match=prefix+'*'))
        if owned_keys:
            client.delete(*owned_keys)
        after={key for key in client.scan_iter()}
        assert before<=after, 'non-owned broker keys disappeared'
        assert not list(client.scan_iter(match=prefix+'*'))
        (RUN/(identifier+'_processes.json')).write_text(json.dumps({'run_id':identifier,'redis_db':15,'isolated_global_keyprefix':prefix,'source_transport':'explicit synthetic empty OSV; eight unselected sources waiting_approval; no source network','default_poll_schedule_seconds':60,'disabled_observation_seconds':65,'processes':phase_receipts,'owned_key_cleanup_count':len(owned_keys),'non_owned_keys_preserved':True},indent=2),encoding='utf-8')
        with catalog_engine.begin() as connection:
            connection.exec_driver_sql('ALTER DATABASE test_dianzi_r06_catalog_polling_20261015 RESET search_path')
            assert connection.scalar(text("SELECT value FROM pg_db_role_setting,unnest(setconfig) value WHERE setdatabase=(SELECT oid FROM pg_database WHERE datname=current_database()) AND setrole=0 AND value LIKE 'search_path=%'")) is None
        client.close()
