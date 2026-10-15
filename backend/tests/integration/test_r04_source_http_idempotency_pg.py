"""真实隔离PG验证来源写入的主体、路由幂等域与提交时认证。"""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema
from test_r04_knowledge_api_pg import clients as clients

from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.domain.access import Role
from ai_intel.infrastructure.database import run_migrations
from ai_intel.knowledge.models import job_runs, users

pytestmark = pytest.mark.real_pg
BODY = {"window_end": "2026-10-15T00:00:00Z", "max_pages": 1}


@pytest.fixture
def api_engine(isolated_test_database_url):
    url = make_url(isolated_test_database_url)
    assert url.database.startswith("test_dianzi_gb_source_http_")
    base = create_engine(url, connect_args={"connect_timeout": 5})
    schema = "test_gb_source_http_" + uuid4().hex
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=5000"}
    )
    run_migrations(isolated.render_as_string(hide_password=False))
    engine = create_engine(isolated, connect_args={"connect_timeout": 5})
    try:
        yield engine
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


def request_headers(client, key="fixture-source-http-key"):
    headers = {
        "Origin": "http://localhost:5173",
        "x-csrf-token": client.get("/v1/auth/csrf").json()["csrf_token"],
    }
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def job_count(engine):
    with engine.connect() as connection:
        return connection.scalar(select(func.count()).select_from(job_runs))


@pytest.mark.parametrize(
    "key", [None, "", "contains space", "a" * 201, "tab\tkey", "delete\x7fkey"]
)
def test_missing_or_nonvisible_key_is_denied_before_source_reservation(api_engine, clients, key):
    client = clients[0](Role.SYSTEM_ADMIN, None)
    headers = request_headers(client, key)
    for prefix in ("/v1", "/api/v1"):
        response = client.post(prefix + "/sources/nvd_ollama/collect", json=BODY, headers=headers)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_key"
    assert job_count(api_engine) == 0


def test_same_key_two_authenticated_administrators_create_independent_jobs(api_engine, clients):
    first, second = (clients[0](Role.SYSTEM_ADMIN, None) for _ in range(2))
    results = [
        client.post("/v1/sources/nvd_ollama/collect", json=BODY, headers=request_headers(client))
        for client in (first, second)
    ]
    assert [result.status_code for result in results] == [202, 202]
    assert results[0].json()["job_id"] != results[1].json()["job_id"]
    assert job_count(api_engine) == 2


def test_same_key_is_independent_per_source_but_shared_across_prefixes(api_engine, clients):
    client = clients[0](Role.SYSTEM_ADMIN, None)
    headers = request_headers(client)
    nvd = client.post("/v1/sources/nvd_ollama/collect", json=BODY, headers=headers)
    vendor = client.post("/api/v1/sources/vllm_vendor/collect", json=BODY, headers=headers)
    assert nvd.status_code == vendor.status_code == 202
    assert nvd.json()["job_id"] != vendor.json()["job_id"]
    replay = client.post("/api/v1/sources/nvd_ollama/collect", json=BODY, headers=headers)
    assert replay.status_code == 202 and replay.json()["job_id"] == nvd.json()["job_id"]
    conflict = client.post(
        "/v1/sources/nvd_ollama/collect", json={**BODY, "max_pages": 2}, headers=headers
    )
    assert conflict.status_code == 409
    assert job_count(api_engine) == 2


def test_concurrent_alias_replay_reserves_exactly_one_source_job(api_engine, clients):
    client = clients[0](Role.SYSTEM_ADMIN, None)
    headers = request_headers(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                client.post, prefix + "/sources/nvd_ollama/collect", json=BODY, headers=headers
            )
            for prefix in ("/v1", "/api/v1")
        ]
        responses = [future.result(timeout=15) for future in futures]
    assert [response.status_code for response in responses] == [202, 202]
    assert len({response.json()["job_id"] for response in responses}) == 1
    assert job_count(api_engine) == 1


@pytest.mark.parametrize("change", ["logout", "role"])
def test_authorization_change_after_initial_scope_is_rejected_before_commit(
    api_engine, clients, monkeypatch, change
):
    client = clients[0](Role.SYSTEM_ADMIN, None)
    headers = request_headers(client)
    auth = clients[2]
    original = auth.build_access_scope

    def revoke_after_scope(token):
        scope = original(token)
        if change == "logout":
            auth.logout(client.cookies[SESSION_COOKIE_NAME])
        else:
            with api_engine.begin() as connection:
                connection.execute(
                    update(users)
                    .where(users.c.user_id == scope.user_id)
                    .values(role=Role.VIEWER.value, tenant_id="tenant-a")
                )
        return scope

    monkeypatch.setattr(auth, "build_access_scope", revoke_after_scope)
    response = client.post("/v1/sources/nvd_ollama/collect", json=BODY, headers=headers)
    assert response.status_code in (401, 403)
    assert job_count(api_engine) == 0
