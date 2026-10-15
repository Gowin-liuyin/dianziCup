"""公开资料真实PG/API路径；合成源正文显式fixture，不计来源live。"""

import secrets
from dataclasses import replace
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from test_r06_catalog_documents_pg import ADMIN, NOW, paper, save
from test_r06_catalog_documents_pg import catalog_engine as catalog_engine

from ai_intel.api import app as application_module
from ai_intel.api.app import create_application
from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.api.auth_state import PgAuthenticationStateStore
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.api.document_read_service import (
    DocumentFilters,
    DocumentReadService,
    InvalidDocumentCursor,
    sources,
)
from ai_intel.domain.access import ROLE_PERMISSIONS, AccessScope, CrossTenantAccessError, Role
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.knowledge.models import document_revisions, documents, evidence

pytestmark = pytest.mark.real_pg
ORIGIN = "http://localhost:5173"


def document_id(engine, revision_id):
    with engine.connect() as connection:
        return UUID(
            connection.scalar(
                select(document_revisions.c.document_id).where(
                    document_revisions.c.revision_id == revision_id
                )
            )
        )


def test_document_history_retains_titles_raw_dates_and_fixed_revision_evidence(
    catalog_engine, tmp_path
):
    store = ContentStore(tmp_path / "raw")
    first = paper()
    second = replace(
        first,
        title="Changed current title",
        metadata={
            **first.metadata,
            "content_coverage": "abstract",
            "license_identifier": "CC0-1.0",
            "license_uri": "https://creativecommons.org/publicdomain/zero/1.0/",
            "source_notes": ["Synthetic abstract, no full paper fetched."],
        },
    )
    old = save(catalog_engine, store, (first,)).revision_ids[0]
    current = save(catalog_engine, store, (second,), at=NOW + timedelta(seconds=1)).revision_ids[0]
    identifier = document_id(catalog_engine, old)
    with Session(catalog_engine) as session:
        reader = DocumentReadService(session, ADMIN, "fixture")
        detail = reader.document_detail(identifier, evidence_limit=1)
        assert detail.document.revision_id == UUID(current)
        assert detail.document.title == "Changed current title"
        assert detail.document.published_precision == "calendar_date"
        assert detail.document.source_published_at is None
        assert detail.document.published_at_raw == "2026-01-01"
        assert detail.document.content_coverage == "abstract"
        assert detail.license_identifier == "CC0-1.0" and detail.source_notes
        assert detail.evidence_total == 2 and detail.next_evidence_offset == 1
        next_page = reader.document_detail(identifier, UUID(current), 1, 1)
        assert next_page.next_evidence_offset is None
        assert next_page.evidence[0].span_id != detail.evidence[0].span_id
        assert {item.revision_id for item in (*detail.evidence, *next_page.evidence)} == {
            UUID(current)
        }
        history = reader.list_revisions(identifier, limit=1)
        assert history.next_offset == 1 and history.items[0].is_current
        prior = reader.list_revisions(identifier, offset=1, limit=1)
        assert prior.next_offset is None and prior.items[0].title == first.title
        assert prior.items[0].revision_id == UUID(old) and not prior.items[0].is_current
        assert reader.document_detail(identifier, UUID(old)).document.title == first.title


def test_document_list_uses_stable_filter_bound_paging_and_literal_query(catalog_engine, tmp_path):
    members = tuple(
        replace(paper(), source_record_id=str(index), title=f"Paper {index}") for index in range(3)
    )
    save(catalog_engine, ContentStore(tmp_path / "raw"), members)
    with Session(catalog_engine) as session:
        reader = DocumentReadService(session, ADMIN, "fixture")
        filters = DocumentFilters(document_kind="paper", q="Paper")
        first = reader.list_documents(filters, limit=2)
        assert len(first.items) == 2 and first.next_cursor is not None
        second = reader.list_documents(filters, first.next_cursor, 2)
        assert len(second.items) == 1 and second.next_cursor is None
        assert len({item.document_id for item in (*first.items, *second.items)}) == 3
        with pytest.raises(InvalidDocumentCursor):
            reader.list_documents(DocumentFilters(q="changed"), first.next_cursor)
        assert reader.list_documents(DocumentFilters(q="%_\\")).items == ()
        assert reader.list_documents(DocumentFilters(document_kind="policy")).items == ()


@pytest.mark.parametrize("hidden_layer", ["document", "revision", "source", "asset_kind"])
def test_private_data_never_enters_public_documents_even_for_same_tenant_admin(
    catalog_engine, tmp_path, hidden_layer
):
    identifier = save(catalog_engine, ContentStore(tmp_path / "raw"), (paper(),)).revision_ids[0]
    doc_id = document_id(catalog_engine, identifier)
    with catalog_engine.begin() as connection:
        if hidden_layer == "document":
            connection.execute(update(documents).values(visibility="tenant", tenant_id="tenant-a"))
        elif hidden_layer == "revision":
            connection.execute(
                update(document_revisions).values(visibility="tenant", tenant_id="tenant-a")
            )
        elif hidden_layer == "source":
            connection.execute(update(sources).values(visibility="tenant", tenant_id="tenant-a"))
        else:
            connection.execute(update(documents).values(kind="asset_inventory"))
    scope = AccessScope.for_authenticated_user("same-tenant", "tenant-a", Role.TENANT_ADMIN)
    with Session(catalog_engine) as session:
        reader = DocumentReadService(session, scope, "fixture")
        assert reader.list_documents(DocumentFilters()).items == ()
        with pytest.raises(CrossTenantAccessError):
            reader.document_detail(doc_id)
        with pytest.raises(CrossTenantAccessError):
            reader.list_revisions(doc_id)


def test_private_evidence_is_not_returned_or_counted_in_public_document(catalog_engine, tmp_path):
    identifier = save(catalog_engine, ContentStore(tmp_path / "raw"), (paper(),)).revision_ids[0]
    with catalog_engine.begin() as connection:
        connection.execute(update(evidence).values(visibility="tenant", tenant_id="tenant-a"))
    scope = AccessScope.for_authenticated_user("same-tenant", "tenant-a", Role.TENANT_ADMIN)
    with Session(catalog_engine) as session:
        result = DocumentReadService(session, scope, "fixture").document_detail(
            document_id(catalog_engine, identifier)
        )
        assert result.evidence == () and result.evidence_total == 0


@pytest.fixture
def document_api(catalog_engine, tmp_path, monkeypatch, register_sensitive_failure_value):
    revision_id = save(catalog_engine, ContentStore(tmp_path / "raw"), (paper(),)).revision_ids[0]
    monkeypatch.setattr(application_module, "build_engine", lambda settings: catalog_engine)
    auth = AuthenticationSessionService(
        DatabaseUserDirectory(catalog_engine),
        (ORIGIN,),
        False,
        state_store=PgAuthenticationStateStore(catalog_engine),
    )
    username = "fixture-document-" + uuid4().hex
    password = SecretStr(secrets.token_urlsafe(32))
    register_sensitive_failure_value(password)
    auth.create_precreated_user(username, password.get_secret_value(), "tenant-a", Role.VIEWER)
    app = create_application(
        auth_service=auth,
        settings=ApplicationSettings(
            app_env="test",
            data_mode="fixture",
            allowed_origins=(ORIGIN,),
            database_url=SecretStr(catalog_engine.url.render_as_string(hide_password=False)),
        ),
    )
    with TestClient(app) as client:
        login = client.post(
            "/v1/auth/login",
            json={"username": username, "password": password.get_secret_value()},
            headers={"Origin": ORIGIN},
        )
        assert login.status_code == 200
        register_sensitive_failure_value(SecretStr(client.cookies[SESSION_COOKIE_NAME]))
        register_sensitive_failure_value(SecretStr(login.json()["csrf_token"]))
        yield client, auth, document_id(catalog_engine, revision_id), catalog_engine


def test_document_get_routes_use_real_pg_authentication_and_both_prefixes(document_api):
    client, _auth, identifier, _engine = document_api
    for prefix in ("/v1", "/api/v1"):
        response = client.get(prefix + "/documents")
        assert response.status_code == 200
        assert response.json()["data_mode"] == "fixture"
        assert response.json()["items"][0]["document_id"] == str(identifier)
        detail = client.get(f"{prefix}/documents/{identifier}")
        assert detail.status_code == 200 and detail.json()["evidence_total"] == 2
        assert client.get(f"{prefix}/documents/{identifier}/revisions").status_code == 200
        assert client.get(f"{prefix}/documents/{uuid4()}").status_code == 404
        assert (
            client.get(f"{prefix}/documents/{identifier}?revision_id={uuid4()}").status_code == 404
        )


@pytest.mark.parametrize(
    "query",
    [
        "q=bad%00query",
        "document_kind=asset_inventory",
        "cursor=bad",
        "limit=101",
        "source_category=unknown",
    ],
)
def test_document_bad_filters_are_422_not_success_or_database_error(document_api, query):
    client, _auth, _identifier, _engine = document_api
    assert client.get("/v1/documents?" + query).status_code == 422


def test_document_revoked_session_cannot_read_any_route(document_api):
    client, auth, identifier, _engine = document_api
    auth.logout(client.cookies[SESSION_COOKIE_NAME])
    for suffix in ("", f"/{identifier}", f"/{identifier}/revisions"):
        assert client.get("/v1/documents" + suffix).status_code == 401


def test_document_revocation_between_initial_scope_and_pg_lock_is_rejected(
    document_api, monkeypatch
):
    client, auth, _identifier, _engine = document_api
    original = auth.build_access_scope

    def revoked_scope(token):
        scope = original(token)
        auth.logout(token)
        return scope

    monkeypatch.setattr(auth, "build_access_scope", revoked_scope)
    assert client.get("/v1/documents").status_code == 401


def test_document_permission_removal_is_403(document_api, monkeypatch):
    client, _auth, _identifier, _engine = document_api
    monkeypatch.setitem(ROLE_PERMISSIONS, Role.VIEWER, frozenset())
    assert client.get("/v1/documents").status_code == 403


def test_document_corrupt_quote_returns_503_without_leaking_text(document_api):
    client, _auth, identifier, engine = document_api
    with engine.begin() as connection:
        connection.execute(update(evidence).values(quote="corrupt-hidden-sentinel"))
    response = client.get(f"/v1/documents/{identifier}")
    assert response.status_code == 503 and "corrupt-hidden-sentinel" not in response.text


def test_document_old_metadata_is_explicit_unknown_and_never_relabels_historical_title(
    catalog_engine, tmp_path
):
    store = ContentStore(tmp_path / "raw")
    old = save(catalog_engine, store, (paper(),)).revision_ids[0]
    save(
        catalog_engine,
        store,
        (replace(paper(), title="New current title"),),
        at=NOW + timedelta(seconds=1),
    )
    with catalog_engine.begin() as connection:
        connection.execute(
            update(document_revisions)
            .where(document_revisions.c.revision_id == old)
            .values(source_metadata={})
        )
    with Session(catalog_engine) as session:
        detail = DocumentReadService(session, ADMIN, "fixture").document_detail(
            document_id(catalog_engine, old), UUID(old)
        )
        assert detail.document.title == "历史标题未记录"
        assert detail.document.title != "New current title"
        assert detail.document.content_coverage == "unknown"
        assert detail.document.published_precision == "unknown"
        assert detail.license_identifier is None and detail.license_uri is None
        assert "历史修订未保存标题" in detail.source_notes[-1]


def test_document_arbitrary_metadata_and_source_html_are_not_interpreted_or_exported(
    catalog_engine, tmp_path
):
    member = replace(
        paper(),
        title="<img src=x onerror=alert(1)>",
        metadata={
            **paper().metadata,
            "uncontracted_secret_sentinel": "not-in-public-response",
            "source_notes": ["<script>alert(1)</script>"],
        },
    )
    revision = save(catalog_engine, ContentStore(tmp_path / "raw"), (member,)).revision_ids[0]
    with Session(catalog_engine) as session:
        detail = DocumentReadService(session, ADMIN, "fixture").document_detail(
            document_id(catalog_engine, revision)
        )
        assert detail.document.title == member.title
        assert detail.source_notes == ("<script>alert(1)</script>",)
        assert "not-in-public-response" not in detail.model_dump_json()


def test_document_valid_but_foreign_revision_cannot_be_read_under_another_document(
    catalog_engine, tmp_path
):
    members = (paper(), replace(paper(), source_record_id="other-paper"))
    saved = save(catalog_engine, ContentStore(tmp_path / "raw"), members)
    with Session(catalog_engine) as session, pytest.raises(CrossTenantAccessError):
        DocumentReadService(session, ADMIN, "fixture").document_detail(
            document_id(catalog_engine, saved.revision_ids[0]), UUID(saved.revision_ids[1])
        )
