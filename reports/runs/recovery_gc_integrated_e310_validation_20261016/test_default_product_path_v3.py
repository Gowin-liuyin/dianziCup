"""Explicit fixture network through the default authenticated product routes and worker registry."""
import os
from datetime import UTC, datetime
import secrets
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from test_r06_catalog_documents_pg import catalog_engine as catalog_engine
from test_r06_source_worker_pg import NOW
from tests.r06_source_worker_fixtures import source_response
from ai_intel.api.app import create_application
from ai_intel.api.auth_state import PgAuthenticationStateStore
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.domain.access import Role
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.network import FetchResult, NetworkTimeoutError
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.ingestion.source_jobs import SOURCE_JOB_TYPE, build_source_page_handler
from ai_intel.knowledge.models import document_revisions, job_runs, source_cursors, source_page_receipts
from ai_intel.workers.executor import execute_job

pytest_plugins=('tests.conftest',)
pytestmark=pytest.mark.real_pg
ORIGIN='http://localhost:5173'


@pytest.fixture
def catalog_engine(isolated_test_database_url,request):
    """The real default engine owns connection options; give each case its own public-schema DB."""
    from ai_intel.infrastructure.database import run_migrations
    from scripts.dev import require_isolated_test_database
    url=make_url(isolated_test_database_url)
    assert url.database=='test_dianzi_r06_catalog_gc_e310_20261016'
    suffix='_default_p3' if 'positive' in request.node.name else '_default_n3'
    database=url.database+suffix
    run_id=database.removeprefix('test_dianzi_')
    new_url=url.set(database=database)
    env=dict(os.environ,TEST_DATABASE_URL=new_url.render_as_string(hide_password=False),DIANZI_TEST_RUN_ID=run_id)
    require_isolated_test_database(env)
    admin=create_engine(url.set(database='postgres'),isolation_level='AUTOCOMMIT',hide_parameters=True)
    with admin.connect() as connection:
        assert not connection.scalar(text('SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=:n)'),{'n':database})
        assert database in {'test_dianzi_r06_catalog_gc_e310_20261016_default_p3','test_dianzi_r06_catalog_gc_e310_20261016_default_n3'}
        connection.execute(text('CREATE DATABASE '+database))
    admin.dispose()
    run_migrations(new_url.render_as_string(hide_password=False),'0016_source_response_receipts')
    engine=create_engine(new_url,hide_parameters=True)
    with engine.connect() as connection:
        assert connection.scalar(text('SELECT current_database()'))==database
        assert connection.scalar(text('SELECT version_num FROM alembic_version'))=='0016_source_response_receipts'
    yield engine
    engine.dispose()


def setup_client(engine,register):
    settings=ApplicationSettings(app_env='test',data_mode='fixture',database_url=SecretStr(engine.url.render_as_string(hide_password=False)))
    auth=AuthenticationSessionService(DatabaseUserDirectory(engine),(ORIGIN,),False,state_store=PgAuthenticationStateStore(engine))
    username='integrated-fixture-'+uuid4().hex
    password=secrets.token_urlsafe(32)
    register(SecretStr(password))
    auth.create_precreated_user(username,password,None,Role.SYSTEM_ADMIN)
    app=create_application(settings=settings)
    client=TestClient(app)
    response=client.post('/v1/auth/login',json=dict(username=username,password=password),headers={'Origin':ORIGIN})
    assert response.status_code==200
    for value in client.cookies.values(): register(SecretStr(value))
    return client,app


def request_collection(client,kind):
    headers={'Origin':ORIGIN,'X-CSRF-Token':client.get('/v1/auth/csrf').json()['csrf_token'],'Idempotency-Key':'independent-'+uuid4().hex}
    response=client.post('/v1/sources/'+kind+'/collect',json={'window_end':'2026-10-15T00:00:00Z','max_pages':1},headers=headers)
    assert response.status_code==202
    return response.json()['job_id']


def use_runtime_registry(monkeypatch,engine,handler):
    monkeypatch.setenv('DATABASE_URL',engine.url.render_as_string(hide_password=False))
    monkeypatch.setenv('REDIS_URL','redis://127.0.0.1:26484/14')
    monkeypatch.setenv('APP_ENV','test')
    monkeypatch.setenv('DATA_MODE','fixture')
    monkeypatch.setenv('RAW_CONTENT_DIRECTORY',str(Path(__file__).resolve().parent/'runtime_raw'))
    from ai_intel.workers import runtime
    assert SOURCE_JOB_TYPE in runtime.EXECUTION_HANDLERS
    monkeypatch.setattr(runtime,'EXECUTION_HANDLERS',{**runtime.EXECUTION_HANDLERS,SOURCE_JOB_TYPE:handler})
    return runtime


def test_default_api_worker_fixture_positive_and_exact_read(catalog_engine,tmp_path,monkeypatch,register_sensitive_failure_value):
    client,app=setup_client(catalog_engine,register_sensitive_failure_value)
    job_id=request_collection(client,'vllm_vendor')
    store=ContentStore(tmp_path/'raw')
    body,media=source_response('vllm_vendor')
    handler=build_source_page_handler(store,fetcher=lambda url:FetchResult(url,200,media,body),clock=lambda:datetime.now(UTC))
    runtime=use_runtime_registry(monkeypatch,catalog_engine,handler)
    assert runtime.consume_job(job_id)['outcome']=='succeeded'
    assert client.get('/api/v1/jobs/'+job_id).json()['status']=='succeeded'
    listing=client.get('/v1/events')
    assert listing.status_code==200 and listing.json()['data_mode']=='fixture'
    event_id=listing.json()['items'][0]['event_id']
    detail=client.get('/api/v1/events/'+event_id)
    assert detail.status_code==200 and detail.json()['claims']
    claim=detail.json()['claims'][0]
    evidence=client.get('/v1/evidence/'+claim['evidence_ids'][0])
    assert evidence.status_code==200 and evidence.json()['revision_id']==claim['source_revision_id']
    assert evidence.json()['quote_text']
    client.close()


def test_default_api_fixture_failure_keeps_cursor_and_no_page(catalog_engine,tmp_path,monkeypatch,register_sensitive_failure_value):
    client,app=setup_client(catalog_engine,register_sensitive_failure_value)
    job_id=request_collection(client,'vllm_vendor')
    with catalog_engine.connect() as connection:
        before=connection.execute(select(source_cursors.c.cursor_json,source_cursors.c.watermark_published_at,source_cursors.c.last_successful_page)).all()
    def unavailable(url):
        raise NetworkTimeoutError('explicit fixture timeout')
    handler=build_source_page_handler(ContentStore(tmp_path/'raw'),fetcher=unavailable,clock=lambda:datetime.now(UTC))
    runtime=use_runtime_registry(monkeypatch,catalog_engine,handler)
    assert runtime.consume_job(job_id)['outcome']=='retry_wait'
    with catalog_engine.connect() as connection:
        assert connection.execute(select(source_cursors.c.cursor_json,source_cursors.c.watermark_published_at,source_cursors.c.last_successful_page)).all()==before
        assert connection.scalar(text('SELECT count(*) FROM source_page_receipts'))==0
        assert connection.scalar(text('SELECT count(*) FROM document_revisions'))==0
    assert client.get('/v1/jobs/'+job_id).json()['status']=='retry_wait'
    assert client.get('/v1/events').json()['items']==[]
    client.close()
