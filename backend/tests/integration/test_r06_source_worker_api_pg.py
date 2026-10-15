"""Real cookie/CSRF/admin catalog scheduling in the dedicated UUID-isolated test PG."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest
import test_r04_source_http_idempotency_pg as legacy_source_http
from sqlalchemy import func, select, text, update
from test_r04_knowledge_api_pg import clients as clients
from test_r06_source_worker_pg import catalog_worker_engine as catalog_worker_engine

from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.domain.access import Role
from ai_intel.ingestion.source_catalog import CATALOG_SOURCES
from ai_intel.ingestion.source_jobs import SOURCE_JOB_TYPE
from ai_intel.knowledge.models import job_payloads, job_runs, users

pytestmark = pytest.mark.real_pg
BODY = {"window_end": "2026-10-15T00:00:00Z", "max_pages": 1}
test_legacy_auth = (
    legacy_source_http.test_authorization_change_after_initial_scope_is_rejected_before_commit
)
test_legacy_concurrent = (
    legacy_source_http.test_concurrent_alias_replay_reserves_exactly_one_source_job
)
test_legacy_invalid_key = (
    legacy_source_http.test_missing_or_nonvisible_key_is_denied_before_source_reservation
)
test_legacy_source_scope = (
    legacy_source_http.test_same_key_is_independent_per_source_but_shared_across_prefixes
)
test_legacy_actor_scope = (
    legacy_source_http.test_same_key_two_authenticated_administrators_create_independent_jobs
)


@pytest.fixture
def api_engine(catalog_worker_engine):
    return catalog_worker_engine


def headers(client, key="fixture-catalog-key"):
    return {
        "Origin": "http://localhost:5173",
        "x-csrf-token": client.get("/v1/auth/csrf").json()["csrf_token"],
        "Idempotency-Key": key,
    }


def job_count(engine):
    with engine.connect() as connection:
        return connection.scalar(select(func.count()).select_from(job_runs))


@pytest.mark.parametrize("kind", tuple(CATALOG_SOURCES))
def test_admin_schedules_all_nine_keys_with_original_payload_attempts_and_alias_replay(
    api_engine, clients, kind
):
    client = clients[0](Role.SYSTEM_ADMIN, None)
    request_headers = headers(client)
    first = client.post("/v1/sources/" + kind + "/collect", json=BODY, headers=request_headers)
    assert first.status_code == 202, first.text
    second = client.post("/api/v1/sources/" + kind + "/collect", json=BODY, headers=request_headers)
    assert second.status_code == 202 and second.json() == first.json()
    conflict = client.post(
        "/v1/sources/" + kind + "/collect", json={**BODY, "max_pages": 2}, headers=request_headers
    )
    assert (
        conflict.status_code == 409 and conflict.json()["error"]["code"] == "idempotency_conflict"
    )
    assert client.get("/api/v1/jobs/" + first.json()["job_id"]).json() == first.json()
    assert job_count(api_engine) == 1
    with api_engine.connect() as connection:
        job = connection.execute(select(job_runs)).mappings().one()
        assert job["max_attempts"] == 3 and job["tenant_id"] is None
        assert job["job_type"] == SOURCE_JOB_TYPE
        payload = json.loads(connection.scalar(select(job_payloads.c.payload)))
        assert payload["source_kind"] == kind and payload["remaining_pages"] == 1
        assert (
            connection.scalar(text("SELECT source_id FROM sources"))
            == CATALOG_SOURCES[kind].source_id
        )


@pytest.mark.parametrize("kind", ["osv_ollama", "avid_community", "nist_ai_rmf"])
@pytest.mark.parametrize("change", ["csrf", "origin", "role"])
def test_new_sources_require_original_csrf_origin_and_system_admin(
    api_engine, clients, kind, change
):
    client = (
        clients[0](Role.ANALYST, "tenant-a")
        if change == "role"
        else clients[0](Role.SYSTEM_ADMIN, None)
    )
    request_headers = headers(client)
    if change == "csrf":
        request_headers["x-csrf-token"] = "invalid-fixture-csrf"
    if change == "origin":
        request_headers["Origin"] = "https://untrusted.example"
    response = client.post("/v1/sources/" + kind + "/collect", json=BODY, headers=request_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == (
        "permission_denied" if change == "role" else "csrf_rejected"
    )
    assert job_count(api_engine) == 0


@pytest.mark.parametrize(
    "extra",
    [
        {"url": "https://127.0.0.1"},
        {"tenant_id": "other"},
        {"cursor": {"blob_sha": "a" * 40}},
        {"max_pages": 21},
    ],
)
def test_new_sources_reject_client_target_cursor_identity_and_unbounded_input(
    api_engine, clients, extra
):
    client = clients[0](Role.SYSTEM_ADMIN, None)
    response = client.post(
        "/v1/sources/avid_community/collect", json={**BODY, **extra}, headers=headers(client)
    )
    assert response.status_code == 422
    assert job_count(api_engine) == 0


def test_same_admin_key_is_separate_per_new_source_and_shared_per_prefix(api_engine, clients):
    client = clients[0](Role.SYSTEM_ADMIN, None)
    request_headers = headers(client)
    responses = [
        client.post(prefix + "/sources/" + kind + "/collect", json=BODY, headers=request_headers)
        for prefix, kind in (("/v1", "osv_ollama"), ("/api/v1", "avid_community"))
    ]
    assert all(response.status_code == 202 for response in responses)
    assert responses[0].json()["job_id"] != responses[1].json()["job_id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                client.post,
                prefix + "/sources/nist_ai_rmf/collect",
                json=BODY,
                headers=request_headers,
            )
            for prefix in ("/v1", "/api/v1")
        ]
        replayed = [future.result(timeout=15) for future in futures]
    assert all(response.status_code == 202 for response in replayed)
    assert replayed[0].json() == replayed[1].json()
    assert job_count(api_engine) == 3


@pytest.mark.parametrize("change", ["logout", "role"])
def test_catalog_submission_rechecks_authentication_in_the_job_transaction(
    api_engine, clients, monkeypatch, change
):
    client = clients[0](Role.SYSTEM_ADMIN, None)
    request_headers = headers(client)
    auth = clients[2]
    build_scope = auth.build_access_scope

    def changed_scope(token):
        scope = build_scope(token)
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

    monkeypatch.setattr(auth, "build_access_scope", changed_scope)
    response = client.post("/v1/sources/avid_community/collect", json=BODY, headers=request_headers)
    assert response.status_code in (401, 403)
    assert job_count(api_engine) == 0


@pytest.mark.parametrize("role", [Role.VIEWER, Role.ANALYST, Role.TENANT_ADMIN])
def test_catalog_jobs_cannot_be_read_by_other_tenant_roles(api_engine, clients, role):
    admin = clients[0](Role.SYSTEM_ADMIN, None)
    response = admin.post("/v1/sources/avid_community/collect", json=BODY, headers=headers(admin))
    assert response.status_code == 202
    other = clients[0](role, "tenant-other")
    denied = other.get("/api/v1/jobs/" + response.json()["job_id"])
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "permission_denied"
