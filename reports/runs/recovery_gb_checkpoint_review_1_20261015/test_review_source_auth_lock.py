import pytest
from sqlalchemy import func,select,text,update
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
from test_review_knowledge_api import api_engine as api_engine, clients as clients
from test_r02_schema_migration import empty_schema_engine as empty_schema_engine
from test_review_source_idempotency import write_headers
from ai_intel.api import source_routes
from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.domain.access import Role
from ai_intel.knowledge.models import job_runs,users

pytestmark = pytest.mark.real_pg

@pytest.mark.parametrize('change',['logout','role','tenant'])
def test_source_authorization_changed_before_commit_lock_blocks_queue(api_engine,clients,monkeypatch,change):
    client = clients[0](Role.SYSTEM_ADMIN,None)
    headers = write_headers(client,'independent-source-before-auth-lock-' + change)
    user_id = client.get('/v1/auth/me').json()['user_id']
    original = source_routes.lock_authenticated_scope
    def changed_before_lock(connection,token,at):
        if change == 'logout':
            clients[2].logout(client.cookies[SESSION_COOKIE_NAME])
        else:
            with api_engine.begin() as writer:
                writer.execute(update(users).where(users.c.user_id == user_id).values(**({'role':'viewer','tenant_id':'independent-other-tenant'} if change == 'role' else {'tenant_id':'independent-other-tenant'})))
        return original(connection,token,at)
    monkeypatch.setattr(source_routes,'lock_authenticated_scope',changed_before_lock)
    response = client.post('/v1/sources/nvd_ollama/collect',json={'window_end':'2026-10-15T00:00:00Z','max_pages':1},headers=headers)
    assert response.status_code == (401 if change == 'logout' else 403)
    with api_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(job_runs)) == 0

def test_source_commit_lock_blocks_logout_until_job_transaction_commits(api_engine,clients,monkeypatch):
    client = clients[0](Role.SYSTEM_ADMIN,None)
    headers = write_headers(client,'independent-source-holds-auth-lock')
    original = source_routes.lock_authenticated_scope
    entered,release = Event(),Event()
    holder = {}
    def held(connection,token,at):
        scope = original(connection,token,at)
        holder['pid'] = connection.scalar(text('SELECT pg_backend_pid()'))
        entered.set()
        assert release.wait(10)
        return scope
    monkeypatch.setattr(source_routes,'lock_authenticated_scope',held)
    with ThreadPoolExecutor(max_workers=2) as pool:
        request = pool.submit(client.post,'/v1/sources/nvd_ollama/collect',json={'window_end':'2026-10-15T00:00:00Z','max_pages':1},headers=headers)
        assert entered.wait(10)
        revoke = pool.submit(clients[2].logout,client.cookies[SESSION_COOKIE_NAME])
        blocked = []
        deadline = time.monotonic() + 5
        try:
            while time.monotonic() < deadline:
                with api_engine.connect() as connection:
                    blocked = list(connection.scalars(text('SELECT pid FROM pg_stat_activity WHERE :pid = ANY(pg_blocking_pids(pid))'),{'pid':holder['pid']}))
                if blocked:
                    break
                time.sleep(0.02)
            assert blocked and not revoke.done()
        finally:
            release.set()
        assert request.result(timeout=15).status_code == 202
        revoke.result(timeout=15)
    with api_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(job_runs)) == 1
    assert client.get('/v1/auth/me').status_code == 401

@pytest.mark.parametrize('change',['logout','role','tenant'])
def test_source_job_read_authorization_changed_before_read_lock_is_denied(api_engine,clients,monkeypatch,change):
    client = clients[0](Role.SYSTEM_ADMIN,None)
    headers = write_headers(client,'independent-source-get-before-auth-lock-' + change)
    job = client.post('/v1/sources/nvd_ollama/collect',json={'window_end':'2026-10-15T00:00:00Z','max_pages':1},headers=headers)
    assert job.status_code == 202
    user_id = client.get('/v1/auth/me').json()['user_id']
    original = source_routes.lock_authenticated_scope
    def changed_before_lock(connection,token,at):
        if change == 'logout':
            clients[2].logout(client.cookies[SESSION_COOKIE_NAME])
        else:
            with api_engine.begin() as writer:
                writer.execute(update(users).where(users.c.user_id == user_id).values(**({'role':'viewer','tenant_id':'independent-other-tenant'} if change == 'role' else {'tenant_id':'independent-other-tenant'})))
        return original(connection,token,at)
    monkeypatch.setattr(source_routes,'lock_authenticated_scope',changed_before_lock)
    response = client.get('/api/v1/jobs/' + job.json()['job_id'])
    assert response.status_code == (401 if change == 'logout' else 403)
    assert 'job_id' not in response.json()
    with api_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(job_runs)) == 1
