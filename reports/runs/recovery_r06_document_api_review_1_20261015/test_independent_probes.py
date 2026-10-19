"""Independent, synthetic-source probes against real isolated PG and default app."""
import base64
import hashlib
import json
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import event, select, update
from sqlalchemy.orm import Session
from test_r06_catalog_documents_pg import ADMIN, NOW, paper, save
from test_r06_catalog_documents_pg import catalog_engine as catalog_engine
from test_r06_document_api_pg import document_id
from test_r04_knowledge_api_pg import clients as clients
from test_r04_knowledge_api_pg import test_real_pg_list_detail_evidence_and_no_cve as test_original_event_evidence_path
from test_r04_knowledge_api_pg import test_cross_tenant_and_nested_source_privacy as test_original_nested_acl
from test_r04_knowledge_api_pg import test_legacy_null_dates_no_invented_verified_locator as test_original_legacy_evidence
from test_r04_knowledge_api_pg import test_corrupt_verified_evidence_fails_closed as test_original_corrupt_evidence

from ai_intel.api import app as application_module
from ai_intel.api import document_routes
from ai_intel.api.app import create_application
from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.api.auth_state import PgAuthenticationStateStore
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.api.document_read_service import DocumentReadService, DocumentFilters
from ai_intel.domain.access import Role
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.knowledge.models import document_revisions, documents, evidence, users, text_blocks
from ai_intel.api.knowledge_read_service import KnowledgeReadService
from ai_intel.domain.access import AccessScope

pytestmark = pytest.mark.real_pg
ORIGIN = "http://localhost:5173"


@pytest.fixture
def api_engine(catalog_engine):
    return catalog_engine


@pytest.fixture
def default_api(catalog_engine, tmp_path, monkeypatch, register_sensitive_failure_value):
    revision = save(catalog_engine, ContentStore(tmp_path / "raw"), (paper(),)).revision_ids[0]
    monkeypatch.setattr(application_module, "build_engine", lambda settings: catalog_engine)
    seed_auth = AuthenticationSessionService(DatabaseUserDirectory(catalog_engine), (ORIGIN,), False,
                                             state_store=PgAuthenticationStateStore(catalog_engine))
    username = "independent-" + uuid4().hex
    password = SecretStr(secrets.token_urlsafe(32))
    register_sensitive_failure_value(password)
    seed_auth.create_precreated_user(username, password.get_secret_value(), "tenant-a", Role.TENANT_ADMIN)
    app = create_application(settings=ApplicationSettings(
        app_env="test", data_mode="fixture", allowed_origins=(ORIGIN,),
        database_url=SecretStr(catalog_engine.url.render_as_string(hide_password=False))))
    with TestClient(app) as client:
        login = client.post("/v1/auth/login", json={"username": username, "password": password.get_secret_value()}, headers={"Origin": ORIGIN})
        assert login.status_code == 200
        register_sensitive_failure_value(SecretStr(client.cookies[SESSION_COOKIE_NAME]))
        register_sensitive_failure_value(SecretStr(login.json()["csrf_token"]))
        yield client, seed_auth, document_id(catalog_engine, revision), catalog_engine, UUID(revision)


def test_default_application_real_cookie_both_prefixes_and_empty_semantics(default_api):
    client, _auth, identifier, _engine, _revision = default_api
    for prefix in ("/v1", "/api/v1"):
        response = client.get(prefix + "/documents?q=unmatched-independent-sentinel")
        assert response.status_code == 200
        assert response.json()["items"] == [] and response.json()["next_cursor"] is None
        assert client.get(f"{prefix}/documents/{identifier}").json()["document"]["document_id"] == str(identifier)
        assert client.get(f"{prefix}/documents/{identifier}/revisions").status_code == 200
    client.cookies.clear()
    assert client.get("/v1/documents").status_code == 401


@pytest.mark.parametrize("layer", ["source", "document", "revision", "evidence", "asset"])
def test_default_same_tenant_admin_cannot_export_private_document_layers(default_api, layer):
    client, _auth, identifier, engine, _revision = default_api
    with engine.begin() as connection:
        if layer == "source":
            connection.exec_driver_sql("UPDATE sources SET visibility='tenant',tenant_id='tenant-a'")
        elif layer == "asset":
            connection.execute(update(documents).values(kind="asset_inventory"))
        else:
            relation = {"document": documents, "revision": document_revisions, "evidence": evidence}[layer]
            connection.execute(update(relation).values(visibility="tenant", tenant_id="tenant-a"))
    for prefix in ("/v1", "/api/v1"):
        if layer == "evidence":
            body = client.get(f"{prefix}/documents/{identifier}").json()
            assert body["evidence"] == [] and body["evidence_total"] == 0
            assert "没有可展示" in body["source_notes"][-1]
        else:
            assert client.get(prefix + "/documents").json()["items"] == []
            assert client.get(f"{prefix}/documents/{identifier}").status_code == 404
            assert client.get(f"{prefix}/documents/{identifier}/revisions").status_code == 404


@pytest.mark.parametrize("corruption", ["hash", "coordinates", "mismatched_block"])
def test_corrupt_evidence_hash_coordinates_or_mismatched_block_returns_safe_503(default_api, corruption):
    client, _auth, identifier, engine, revision = default_api
    with engine.begin() as connection:
        first = connection.execute(select(evidence).limit(1)).mappings().one()
        if corruption == "hash":
            mutation = {"quote_sha256": "0" * 64}
        elif corruption == "coordinates":
            mutation = {"start_offset": first["start_offset"] + 10000, "end_offset": first["end_offset"] + 10000}
        else:
            block = connection.execute(select(text_blocks).where(text_blocks.c.block_id != first["block_id"]).limit(1)).mappings().one()
            mutation = {"block_id": block["block_id"]}
        connection.execute(update(evidence).where(evidence.c.evidence_id == first["evidence_id"]).values(**mutation))
    response = client.get(f"/v1/documents/{identifier}")
    assert response.status_code == 503
    assert "Quoted metadata" not in response.text and "真实坐标" not in response.text


@pytest.mark.parametrize("uri", ["http://example.com/a", "https://user:password@example.com/a", "https://example.com/a#private", "https://example.com/a?access_token=private"])
def test_invalid_stored_public_uri_is_dependency_failure_without_leak(default_api, uri):
    client, _auth, identifier, engine, _revision = default_api
    with engine.begin() as connection:
        connection.execute(update(document_revisions).values(canonical_uri=uri))
    response = client.get(f"/v1/documents/{identifier}")
    assert response.status_code == 503
    assert uri not in response.text and "private" not in response.text


@pytest.mark.parametrize("metadata", [{"published_precision": "instant"}, {"published_precision": "calendar_date"}, {"source_notes": ["x" * 1001]}, {"license_uri": "https://example.com/?password=sensitive"}])
def test_malformed_metadata_never_turns_into_success_empty(default_api, metadata):
    client, _auth, identifier, engine, _revision = default_api
    with engine.begin() as connection:
        connection.execute(update(document_revisions).values(source_metadata=metadata))
    response = client.get(f"/v1/documents/{identifier}")
    assert response.status_code == 503 and "sensitive" not in response.text


def test_fixed_revision_pages_do_not_follow_updated_current(catalog_engine, tmp_path):
    store = ContentStore(tmp_path / "raw")
    revision = save(catalog_engine, store, (paper(),)).revision_ids[0]
    identifier = document_id(catalog_engine, revision)
    with Session(catalog_engine) as session:
        first = DocumentReadService(session, ADMIN, "fixture").document_detail(identifier, evidence_limit=1)
    current = save(catalog_engine, store, (replace(paper(), title="Later current"),), at=NOW + timedelta(seconds=1)).revision_ids[0]
    with Session(catalog_engine) as session:
        reader = DocumentReadService(session, ADMIN, "fixture")
        second = reader.document_detail(identifier, first.document.revision_id, evidence_offset=1, evidence_limit=1)
        assert second.document.revision_id == UUID(revision) and second.document.title == paper().title
        assert not second.document.is_current
        assert reader.document_detail(identifier).document.revision_id == UUID(current)
        assert second.evidence[0].quote_sha256 == hashlib.sha256(second.evidence[0].quote_text.encode()).hexdigest()


def test_duplicate_cursor_json_and_changed_filters_rejected_on_api(default_api):
    client, _auth, _identifier, engine, _revision = default_api
    from ai_intel.api.document_read_service import encode_document_cursor
    cursor = encode_document_cursor(NOW, uuid4(), DocumentFilters())
    raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
    duplicate = base64.urlsafe_b64encode((raw[:-1] + ',"version":1}').encode()).decode().rstrip("=")
    assert client.get("/v1/documents", params={"cursor": duplicate}).status_code == 422
    for params in ({"q": "changed"}, {"document_kind": "policy"}, {"source_category": "technical_blog"}):
        assert client.get("/v1/documents", params={"cursor": cursor, **params}).status_code == 422


def test_sql_queries_are_constant_count_and_bounded_for_detail_pages(default_api):
    client, _auth, identifier, engine, _revision = default_api
    statements = []
    def remember(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)
    event.listen(engine, "before_cursor_execute", remember)
    try:
        result = client.get(f"/v1/documents/{identifier}?evidence_limit=1")
    finally:
        event.remove(engine, "before_cursor_execute", remember)
    assert result.status_code == 200
    assert len(statements) <= 10
    evidence_reads = [query for query in statements if "text_blocks" in query and "evidence" in query]
    assert len(evidence_reads) == 1 and "LIMIT" in evidence_reads[0]


def test_tenant_change_between_initial_auth_and_read_lock_denied(default_api, monkeypatch):
    client, _auth, _identifier, engine, _revision = default_api
    original = document_routes.lock_authenticated_scope
    def changed_scope(connection, token, at):
        with engine.begin() as write:
            write.execute(update(users).values(tenant_id="tenant-b"))
        return original(connection, token, at)
    monkeypatch.setattr(document_routes, "lock_authenticated_scope", changed_scope)
    assert client.get("/v1/documents").status_code == 403


def test_session_revoke_after_lock_waits_then_next_request_denied(default_api, monkeypatch):
    client, auth, _identifier, _engine, _revision = default_api
    locked = threading.Event()
    release = threading.Event()
    revoked = threading.Event()
    original = DocumentReadService.list_documents
    def paused_read(reader, *args):
        locked.set()
        assert release.wait(5)
        return original(reader, *args)
    monkeypatch.setattr(DocumentReadService, "list_documents", paused_read)
    token = client.cookies[SESSION_COOKIE_NAME]
    def revoke():
        auth.logout(token)
        revoked.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        reading = pool.submit(client.get, "/v1/documents")
        assert locked.wait(5)
        revoking = pool.submit(revoke)
        assert not revoked.wait(0.2)
        release.set()
        assert reading.result(timeout=5).status_code == 200
        revoking.result(timeout=5)
    assert revoked.is_set()
    assert client.get("/v1/documents").status_code == 401


def test_unconfigured_default_document_database_returns_503():
    app = create_application(settings=ApplicationSettings(app_env="test", data_mode="fixture"))
    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE_NAME, "independent-nonsecret-invalid-session")
        assert client.get("/v1/documents").status_code == 503


def test_old_evidence_rows_caller_is_not_capped_or_forced_public(catalog_engine, tmp_path):
    revision = save(catalog_engine, ContentStore(tmp_path / "raw"), (paper(),)).revision_ids[0]
    with catalog_engine.begin() as connection:
        first = dict(connection.execute(select(evidence).limit(1)).mappings().one())
        clones = [{**first, "evidence_id": str(uuid4())} for _ in range(105)]
        connection.execute(evidence.insert(), clones)
        private = {**first, "evidence_id": str(uuid4()), "visibility": "tenant", "tenant_id": "tenant-a"}
        connection.execute(evidence.insert().values(**private))
    scope = AccessScope.for_authenticated_user("old-caller", "tenant-a", Role.TENANT_ADMIN)
    with Session(catalog_engine) as session:
        reader = KnowledgeReadService(session, scope, "fixture")
        assert len(reader._evidence_rows(revision_ids=(revision,))) == 108
        assert reader.read_evidence(UUID(private["evidence_id"])).quote_text == first["quote"]
        items, total = reader.read_public_revision_evidence(UUID(revision), 0, 100)
        assert total == 107 and len(items) == 100


def test_document_evidence_over_2000_returns_503(default_api):
    client, _auth, identifier, engine, _revision = default_api
    with engine.begin() as connection:
        first = dict(connection.execute(select(evidence).limit(1)).mappings().one())
        connection.execute(evidence.insert(), [{**first, "evidence_id": str(uuid4())} for _ in range(2000)])
    response = client.get(f"/v1/documents/{identifier}")
    assert response.status_code == 503 and "Quoted metadata" not in response.text
