"""Reviewer-authored synthetic PG HTTP cases; no live intelligence or model calls."""

import secrets
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import update
from test_r04_knowledge_api_pg import api_engine as api_engine
from test_r04_knowledge_api_pg import clients as clients
from test_r04_knowledge_api_pg import seed_claim, seed_dimension, seed_event, seed_source_document

from ai_intel.api import app as application_module
from ai_intel.api.app import create_application
from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.api.auth_state import PgAuthenticationStateStore
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.domain.access import Role
from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.knowledge.persistence_models import claims

pytestmark = pytest.mark.real_pg


@pytest.fixture()
def default_pg_client(api_engine, monkeypatch, register_sensitive_failure_value):
    """The default application constructs PG authentication in an isolated engine."""
    monkeypatch.setattr(application_module, "build_engine", lambda settings: api_engine)
    preparation_service = AuthenticationSessionService(
        DatabaseUserDirectory(api_engine),
        ("http://localhost:5173",),
        False,
        state_store=PgAuthenticationStateStore(api_engine),
    )
    account_name = "review-fixture-" + uuid4().hex
    password = SecretStr(secrets.token_urlsafe(32))
    register_sensitive_failure_value(password)
    preparation_service.create_precreated_user(
        account_name, password.get_secret_value(), "tenant-a", Role.ANALYST
    )
    settings = ApplicationSettings(
        app_env="test",
        data_mode="fixture",
        allowed_origins=("http://localhost:5173",),
        database_url=SecretStr(api_engine.url.render_as_string(hide_password=False)),
    )
    application = create_application(settings=settings)
    with TestClient(application, raise_server_exceptions=False) as client:
        login = client.post(
            "/v1/auth/login",
            json={"username": account_name, "password": password.get_secret_value()},
            headers={"origin": "http://localhost:5173"},
        )
        assert login.status_code == 200
        register_sensitive_failure_value(SecretStr(client.cookies[SESSION_COOKIE_NAME]))
        yield client


@pytest.mark.parametrize("prefix", ["/v1", "/api/v1"])
def test_default_pg_authentication_login_and_all_three_reads(api_engine, default_pg_client, prefix):
    public = seed_source_document(api_engine)
    target = seed_event(
        api_engine, [public["revision_id"]], title="review fixture with real PG auth"
    )
    seed_claim(api_engine, public, "review fixture product")
    foreign = seed_source_document(
        api_engine,
        source_visibility="tenant",
        source_tenant="tenant-b",
        visibility="tenant",
        tenant="tenant-b",
    )
    foreign_event = seed_event(
        api_engine, [foreign["revision_id"]], visibility="tenant", tenant="tenant-b"
    )
    listing = default_pg_client.get(
        prefix + "/events", params={"tenant_id": "tenant-b", "role": "system_admin"}
    )
    assert listing.status_code == 200
    assert listing.json()["data_mode"] == "fixture"
    assert {row["event_id"] for row in listing.json()["items"]} == {target}
    detail = default_pg_client.get(prefix + "/events/" + target)
    assert detail.status_code == 200
    assert detail.json()["revisions"][0]["revision_id"] == public["revision_id"]
    quoted = default_pg_client.get(prefix + "/evidence/" + public["evidence_id"])
    assert quoted.status_code == 200
    assert quoted.json()["quote_text"] == "中文🙂 old evidence"
    assert quoted.json()["start_offset"] == 100
    assert default_pg_client.get(prefix + "/events/" + foreign_event).status_code == 404
    assert default_pg_client.get(prefix + "/evidence/" + foreign["evidence_id"]).status_code == 404


@pytest.mark.parametrize("field", ["q", "product", "risk_type"])
def test_nul_filter_is_rejected_as_client_validation(api_engine, default_pg_client, field):
    response = default_pg_client.get("/v1/events", params={field: "review\x00input"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_cursor_is_reauthorized_after_session_revocation(api_engine, default_pg_client):
    for _ in range(3):
        seed_event(api_engine, [])
    first = default_pg_client.get("/v1/events", params={"limit": 1})
    assert first.status_code == 200
    cursor = first.json()["next_cursor"]
    assert cursor
    csrf = default_pg_client.get("/v1/auth/csrf").json()["csrf_token"]
    response = default_pg_client.post(
        "/v1/auth/logout", headers={"origin": "http://localhost:5173", "x-csrf-token": csrf}
    )
    assert response.status_code == 200
    denied = default_pg_client.get("/v1/events", params={"limit": 1, "cursor": cursor})
    assert denied.status_code == 401


def test_missing_dimension_reference_is_not_successful_empty_state(api_engine, default_pg_client):
    revision = seed_source_document(api_engine)
    target = seed_event(api_engine, [revision["revision_id"]])
    claim = seed_claim(api_engine, revision, "review fixture product")
    dimension = seed_dimension(api_engine, target, revision, claim)
    initial = default_pg_client.get("/v1/events/" + target)
    assert initial.status_code == 200
    assert initial.json()["dimensions"][0]["status"] == "available"
    with api_engine.begin() as connection:
        connection.execute(
            update(enrichment_results)
            .where(enrichment_results.c.result_id == dimension)
            .values(reference_ids=[str(uuid4())])
        )
    response = default_pg_client.get("/v1/events/" + target)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "knowledge_unavailable"


def test_stale_supporting_claim_invalidates_current_dimension(api_engine, default_pg_client):
    revision = seed_source_document(api_engine)
    target = seed_event(api_engine, [revision["revision_id"]])
    claim = seed_claim(api_engine, revision, "review fixture product")
    seed_dimension(api_engine, target, revision, claim)
    initial = default_pg_client.get("/v1/events/" + target)
    assert initial.status_code == 200
    assert initial.json()["dimensions"][0]["freshness"] == "current"
    with api_engine.begin() as connection:
        connection.execute(
            update(claims).where(claims.c.claim_id == claim).values(freshness="stale")
        )
    response = default_pg_client.get("/v1/events/" + target)
    assert response.status_code == 200
    assert response.json()["dimensions"][0]["freshness"] == "stale"


@pytest.mark.parametrize("column_name", ["source_scope", "claim_ids", "reference_ids"])
def test_corrupt_saved_reference_member_is_fixed_problem(
    api_engine, default_pg_client, column_name
):
    revision = seed_source_document(api_engine)
    target = seed_event(api_engine, [revision["revision_id"]])
    claim = seed_claim(api_engine, revision, "fixture product")
    dimension = seed_dimension(api_engine, target, revision, claim)
    with api_engine.begin() as connection:
        connection.execute(
            update(enrichment_results)
            .where(enrichment_results.c.result_id == dimension)
            .values(**{column_name: [{}]})
        )
    response = default_pg_client.get("/v1/events/" + target)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "knowledge_unavailable"


@pytest.mark.parametrize("column_name", ["claim_ids", "reference_ids"])
def test_visible_reference_from_another_event_is_damage(api_engine, default_pg_client, column_name):
    original = seed_source_document(api_engine)
    unrelated = seed_source_document(api_engine, body="unrelated public document")
    target = seed_event(api_engine, [original["revision_id"]])
    unrelated_event = seed_event(api_engine, [unrelated["revision_id"]])
    original_claim = seed_claim(api_engine, original, "original public product")
    unrelated_claim = seed_claim(api_engine, unrelated, "unrelated public product")
    dimension = seed_dimension(api_engine, target, original, original_claim)
    assert default_pg_client.get("/v1/events/" + unrelated_event).status_code == 200
    assert default_pg_client.get("/v1/evidence/" + unrelated["evidence_id"]).status_code == 200
    identifier = unrelated_claim if column_name == "claim_ids" else unrelated["evidence_id"]
    with api_engine.begin() as connection:
        connection.execute(
            update(enrichment_results)
            .where(enrichment_results.c.result_id == dimension)
            .values(**{column_name: [identifier]})
        )
    response = default_pg_client.get("/v1/events/" + target)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "knowledge_unavailable"


@pytest.mark.parametrize("role", [Role.ANALYST, Role.TENANT_ADMIN, Role.SYSTEM_ADMIN])
def test_source_collection_requires_global_admin_and_bound_csrf(clients, role):
    client = clients[0](role, None if role == Role.SYSTEM_ADMIN else "tenant-a")
    payload = {"window_end": "2026-10-15T00:00:00Z", "max_pages": 2}
    csrf = client.get("/v1/auth/csrf").json()["csrf_token"]
    assert client.post("/v1/sources/nvd_ollama/collect", json=payload).status_code == 403
    headers = {
        "origin": "http://localhost:5173",
        "x-csrf-token": csrf,
        "idempotency-key": "fixture-source-window",
    }
    response = client.post("/v1/sources/nvd_ollama/collect", json=payload, headers=headers)
    if role != Role.SYSTEM_ADMIN:
        assert response.status_code == 403
        return
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert response.json()["status"] == "queued"
    repeated = client.post("/api/v1/sources/nvd_ollama/collect", json=payload, headers=headers)
    assert repeated.status_code == 202
    assert repeated.json()["job_id"] == job_id
    conflict = client.post(
        "/v1/sources/nvd_ollama/collect", json={**payload, "max_pages": 1}, headers=headers
    )
    assert conflict.status_code == 409
    assert client.get("/v1/jobs/" + job_id).status_code == 200
    assert clients[0](Role.TENANT_ADMIN, "tenant-a").get("/v1/jobs/" + job_id).status_code == 403
    assert "payload" not in client.get("/v1/jobs/" + job_id).json()


def test_source_api_rejects_forged_identity_and_unknown_job(clients):
    client = clients[0](Role.SYSTEM_ADMIN, None)
    csrf = client.get("/v1/auth/csrf").json()["csrf_token"]
    headers = {"origin": "http://localhost:5173", "x-csrf-token": csrf}
    payload = {"window_end": "2026-10-15T00:00:00Z"}
    assert (
        client.post(
            "/v1/sources/nvd_ollama/collect",
            json={**payload, "tenant_id": "forged"},
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        client.post("/v1/sources/unknown/collect", json=payload, headers=headers).status_code == 422
    )
    assert client.get("/v1/jobs/" + str(uuid4())).status_code == 404
