"""真实隔离PG端点、嵌套ACL与历史证据；合成样本明确不计live。"""

import hashlib
import secrets
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event, text, update
from sqlalchemy.engine import Engine, make_url

from ai_intel.api import app as application_module
from ai_intel.api.app import create_application
from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.api.auth_state import PgAuthenticationStateStore
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.domain.access import AccessScope, Role
from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.knowledge.models import (
    document_revisions,
    documents,
    evidence,
    text_blocks,
)
from ai_intel.knowledge.persistence_models import (
    claim_evidence,
    claims,
    event_documents,
    event_external_ids,
    events,
)

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 15, 5, 0, tzinfo=UTC)


@pytest.fixture()
def api_engine(isolated_test_database_url: str) -> Iterator[Engine]:
    schema = "test_r04_api_" + uuid4().hex
    base = create_engine(isolated_test_database_url)
    with base.begin() as connection:
        assert (
            connection.scalar(text("SELECT current_database()")) == "test_dianzi_r04_api_20261015"
        )
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    migration_url = (
        make_url(isolated_test_database_url)
        .update_query_dict(
            {"options": f"-c search_path={schema} -c statement_timeout=20000 -c lock_timeout=5000"}
        )
        .render_as_string(hide_password=False)
    )
    run_migrations(migration_url)
    engine = create_engine(migration_url)
    try:
        yield engine
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        base.dispose()


def seed_source_document(
    engine: Engine,
    *,
    source_visibility: str = "public",
    source_tenant: str | None = None,
    visibility: str = "public",
    tenant: str | None = None,
    source_id: str | None = None,
    document_id: str | None = None,
    previous_revision_id: str | None = None,
    revision_number: int = 1,
    created_at: datetime = NOW,
    body: str = "中文🙂 old evidence",
    legacy: bool = False,
) -> dict[str, str]:
    source_id = source_id or str(uuid4())
    document_id = document_id or str(uuid4())
    revision_id, block_id, evidence_id = (str(uuid4()) for _ in range(3))
    digest = hashlib.sha256(body.encode()).hexdigest()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO content_objects(content_hash,size_bytes,created_at) "
                "VALUES(:hash,:size,:now) ON CONFLICT DO NOTHING"
            ),
            {"hash": digest, "size": len(body.encode()), "now": created_at},
        )
        connection.execute(
            text(
                "INSERT INTO sources(source_id,name,category,base_origin,visibility,tenant_id,"
                "created_at) VALUES(:id,:id,'vendor_advisory',"
                "'https://example.invalid',:visibility,:tenant,:now) ON CONFLICT DO NOTHING"
            ),
            {
                "id": source_id,
                "visibility": source_visibility,
                "tenant": source_tenant,
                "now": created_at,
            },
        )
        if previous_revision_id is None:
            connection.execute(
                documents.insert().values(
                    document_id=document_id,
                    source_id=source_id,
                    kind="advisory",
                    title="fixture document",
                    published_at=None,
                    retrieved_at=created_at,
                    content_hash=digest,
                    visibility=visibility,
                    tenant_id=tenant,
                    schema_version=2,
                )
            )
        else:
            connection.execute(
                update(document_revisions)
                .where(document_revisions.c.revision_id == previous_revision_id)
                .values(is_current=False)
            )
        connection.execute(
            document_revisions.insert().values(
                revision_id=revision_id,
                document_id=document_id,
                revision_number=revision_number,
                content_hash=digest,
                created_at=created_at,
                is_current=True,
                previous_revision_id=previous_revision_id,
                visibility=visibility,
                tenant_id=tenant,
                canonical_uri=None if legacy else "https://example.invalid/advisory?public_id=1",
                source_published_at=None,
                source_modified_at=None,
                first_observed_at=None if legacy else created_at,
                ingested_at=None if legacy else created_at,
                parse_status="legacy_unverified" if legacy else "parsed",
                **({} if legacy else {"source_metadata": {"data_mode": "fixture"}}),
            )
        )
        connection.execute(
            text_blocks.insert().values(
                block_id=block_id,
                revision_id=revision_id,
                ordinal=1,
                start_offset=100,
                end_offset=100 + len(body),
                text_sha256=digest,
                block_text=body,
                block_type="json_value",
                json_pointer="/description" if not legacy else None,
            )
        )
        connection.execute(
            evidence.insert().values(
                evidence_id=evidence_id,
                revision_id=revision_id,
                start_offset=100,
                end_offset=100 + len(body),
                locator="/description",
                quote=body,
                supports_claim=True,
                visibility=visibility,
                tenant_id=tenant,
                created_at=created_at,
                block_id=block_id,
                quote_sha256=None if legacy else digest,
                verified_at=None if legacy else created_at,
                coordinate_version="legacy_unverified" if legacy else "fulltext_unicode_v1",
            )
        )
    return {
        "source_id": source_id,
        "document_id": document_id,
        "revision_id": revision_id,
        "block_id": block_id,
        "evidence_id": evidence_id,
    }


def seed_event(
    engine: Engine,
    revision_ids: list[str],
    *,
    title: str = "fixture event",
    visibility: str = "public",
    tenant: str | None = None,
    seen: datetime = NOW,
    event_type: str = "vulnerability",
    external_id: str | None = None,
) -> str:
    event_id = str(uuid4())
    scope_key = "public" if visibility == "public" else "tenant:" + str(tenant)
    with engine.begin() as connection:
        connection.execute(
            events.insert().values(
                event_id=event_id,
                event_type=event_type,
                title=title,
                scope_key=scope_key,
                visibility=visibility,
                tenant_id=tenant,
                status="active",
                first_seen_at=seen,
                business_version=1,
            )
        )
        for revision_id in revision_ids:
            connection.execute(
                event_documents.insert().values(
                    event_id=event_id,
                    revision_id=revision_id,
                    active=True,
                    associated_at=seen,
                )
            )
        if external_id:
            connection.execute(
                event_external_ids.insert().values(
                    event_id=event_id,
                    id_type="ghsa",
                    id_value=external_id,
                    scope_key=scope_key,
                )
            )
    return event_id


def seed_claim(
    engine: Engine,
    revision: dict[str, str],
    value: str,
    *,
    current: bool = True,
    status: str = "supported",
    origin: str = "source_explicit",
    visibility: str = "public",
    tenant: str | None = None,
) -> str:
    claim_id = str(uuid4())
    with engine.begin() as connection:
        connection.execute(
            claims.insert().values(
                claim_id=claim_id,
                subject="fixture component",
                predicate="affected_product",
                object_value=value,
                claim_status=status,
                claim_origin=origin,
                condition_value="true",
                freshness="unknown",
                asserted_at=NOW,
                observed_at=None,
                visibility=visibility,
                tenant_id=tenant,
                created_at=NOW,
                is_current=current,
                source_revision_id=revision["revision_id"],
                schema_version=2,
                provenance_status="source_verified",
            )
        )
        connection.execute(
            claim_evidence.insert().values(
                claim_id=claim_id,
                evidence_id=revision["evidence_id"],
                support_kind="supports",
                validation_status="validated",
            )
        )
    return claim_id


@pytest.fixture()
def clients(api_engine: Engine, monkeypatch, register_sensitive_failure_value):
    monkeypatch.setattr(application_module, "build_engine", lambda settings: api_engine)
    auth = AuthenticationSessionService(
        DatabaseUserDirectory(api_engine),
        ("http://localhost:5173",),
        False,
        state_store=PgAuthenticationStateStore(api_engine),
    )
    settings = ApplicationSettings(
        app_env="test",
        data_mode="fixture",
        database_url=SecretStr(api_engine.url.render_as_string(hide_password=False)),
    )
    app = create_application(auth, settings=settings)
    instances = []

    def create(role: Role = Role.ANALYST, tenant: str | None = "tenant-a") -> TestClient:
        account_name = "fixture-user-" + uuid4().hex
        password = secrets.token_urlsafe(32)
        register_sensitive_failure_value(SecretStr(password))
        auth.create_precreated_user(account_name, password, tenant, role)
        client = TestClient(app)
        response = client.post(
            "/v1/auth/login",
            json={"username": account_name, "password": password},
            headers={"origin": "http://localhost:5173"},
        )
        assert response.status_code == 200
        register_sensitive_failure_value(SecretStr(client.cookies[SESSION_COOKIE_NAME]))
        instances.append(client)
        return client

    yield create, app, auth
    for client in instances:
        client.close()


def test_real_pg_list_detail_evidence_and_no_cve(api_engine, clients) -> None:
    revision = seed_source_document(api_engine)
    event_id = seed_event(api_engine, [revision["revision_id"]], external_id="GHSA-test-no-cve")
    claim_id = seed_claim(api_engine, revision, "vLLM")
    client = clients[0]()
    listing = client.get("/v1/events")
    assert listing.status_code == 200
    assert listing.json()["data_mode"] == "fixture"
    assert listing.json()["items"][0]["event_id"] == event_id
    assert listing.json()["items"][0]["external_ids"] == ["GHSA-test-no-cve"]
    assert listing.json()["items"][0]["freshness"] == "unknown"
    assert listing.json()["items"][0]["primary_product_ids"] == []
    detail = client.get("/api/v1/events/" + event_id)
    assert detail.status_code == 200
    assert detail.json()["dimensions"] == []
    assert detail.json()["claims"][0]["claim_id"] == claim_id
    assert detail.json()["claims"][0]["source_revision_id"] == revision["revision_id"]
    response = client.get("/v1/evidence/" + revision["evidence_id"])
    assert response.status_code == 200
    assert response.json()["quote_text"] == "中文🙂 old evidence"
    assert response.json()["start_offset"] == 100
    assert response.json()["locator_kind"] == "json_pointer"
    assert response.json()["json_pointer"] == "/description"
    assert response.json()["source_published_at"] is None


def test_keyset_pages_stable_with_equal_times_and_insert(api_engine, clients) -> None:
    revision = seed_source_document(api_engine)
    ids = [seed_event(api_engine, [revision["revision_id"]]) for _ in range(5)]
    client = clients[0]()
    page = client.get("/v1/events?limit=2").json()
    found = [item["event_id"] for item in page["items"]]
    assert found == sorted(ids, reverse=True)[:2]
    seed_event(api_engine, [revision["revision_id"]], seen=NOW + timedelta(seconds=1))
    while page["next_cursor"]:
        page = client.get("/v1/events", params={"limit": 2, "cursor": page["next_cursor"]}).json()
        found.extend(item["event_id"] for item in page["items"])
    assert found == sorted(ids, reverse=True)
    assert len(set(found)) == 5


def test_filters_literal_and_cursor_bound(api_engine, clients) -> None:
    revision = seed_source_document(api_engine)
    match = seed_event(
        api_engine,
        [revision["revision_id"]],
        title="literal %_ ' OR 1=1 --",
        external_id="GHSA-external-text",
    )
    seed_claim(api_engine, revision, "vLLM %_")
    seed_event(api_engine, [], title="ordinary vLLM title")
    client = clients[0]()
    for query in ("%_", "' OR 1=1 --", "external-TEXT"):
        result = client.get("/v1/events", params={"q": query})
        assert result.status_code == 200
        assert [item["event_id"] for item in result.json()["items"]] == [match]
    product = client.get("/v1/events", params={"product": "Vllm %_"})
    assert [item["event_id"] for item in product.json()["items"]] == [match]
    assert client.get("/v1/events", params={"product": "ordinary"}).json()["items"] == []
    assert client.get("/v1/events", params={"risk_type": "VULNERABILITY"}).json()["items"] == []
    page = client.get("/v1/events?limit=1").json()
    changed = client.get("/v1/events", params={"q": "%_", "cursor": page["next_cursor"]})
    assert changed.status_code == 422
    assert changed.json()["error"]["code"] == "invalid_cursor"


def test_product_only_current_source_revision_and_claim(api_engine, clients) -> None:
    first = seed_source_document(api_engine)
    seed_claim(api_engine, first, "old-product")
    second = seed_source_document(
        api_engine,
        source_id=first["source_id"],
        document_id=first["document_id"],
        previous_revision_id=first["revision_id"],
        revision_number=2,
        created_at=NOW + timedelta(minutes=1),
        body="new evidence",
    )
    event_id = seed_event(api_engine, [first["revision_id"], second["revision_id"]])
    seed_claim(api_engine, second, "withdrawn-product", current=False, status="withdrawn")
    seed_claim(api_engine, second, "model-product", origin="model_hypothesis")
    seed_claim(api_engine, second, "new-product")
    client = clients[0]()
    for query in ("old-product", "withdrawn-product", "model-product"):
        assert client.get("/v1/events", params={"product": query}).json()["items"] == []
    assert (
        client.get("/v1/events", params={"product": "new-product"}).json()["items"][0]["event_id"]
        == event_id
    )
    detail = client.get("/v1/events/" + event_id).json()
    assert len(detail["revisions"]) == 2
    assert detail["event"]["source_count"] == 1
    assert detail["event"]["latest_revision_id"] == second["revision_id"]
    old = client.get("/v1/evidence/" + first["evidence_id"]).json()
    assert old["revision_id"] == first["revision_id"]
    assert old["quote_text"] == "中文🙂 old evidence"


def test_updated_after_uses_saved_revision_times_not_source_unknown(api_engine, clients) -> None:
    first = seed_source_document(api_engine, created_at=NOW - timedelta(days=2))
    event_id = seed_event(api_engine, [first["revision_id"]], seen=NOW - timedelta(days=2))
    client = clients[0]()
    parameters = {"updated_after": (NOW - timedelta(days=1)).isoformat()}
    assert client.get("/v1/events", params=parameters).json()["items"] == []
    with api_engine.begin() as connection:
        connection.execute(
            update(document_revisions)
            .where(document_revisions.c.revision_id == first["revision_id"])
            .values(ingested_at=NOW)
        )
    assert client.get("/v1/events", params=parameters).json()["items"][0]["event_id"] == event_id


def test_cross_tenant_and_nested_source_privacy(api_engine, clients) -> None:
    public = seed_source_document(api_engine)
    private = seed_source_document(
        api_engine,
        source_visibility="tenant",
        source_tenant="tenant-b",
        visibility="tenant",
        tenant="tenant-b",
        body="private title/body",
    )
    poisoned = seed_source_document(
        api_engine, source_visibility="tenant", source_tenant="tenant-b"
    )
    seed_claim(api_engine, private, "private-product", visibility="tenant", tenant="tenant-b")
    public_id = seed_event(
        api_engine, [public["revision_id"], private["revision_id"], poisoned["revision_id"]]
    )
    private_id = seed_event(
        api_engine,
        [private["revision_id"]],
        visibility="tenant",
        tenant="tenant-b",
        title="private event name",
    )
    analyst = clients[0]()
    admin = clients[0](Role.SYSTEM_ADMIN, None)
    for client in (analyst, admin):
        listing = client.get("/v1/events").json()
        assert [item["event_id"] for item in listing["items"]] == [public_id]
        detail = client.get("/v1/events/" + public_id)
        assert detail.status_code == 200
        assert detail.json()["event"]["source_count"] == 1
        assert [item["revision_id"] for item in detail.json()["revisions"]] == [
            public["revision_id"]
        ]
        assert "private-product" not in detail.text
        for target in (private_id, str(uuid4())):
            assert client.get("/v1/events/" + target).status_code == 404
        for target in (private["evidence_id"], poisoned["evidence_id"], str(uuid4())):
            assert client.get("/v1/evidence/" + target).status_code == 404
    owner = clients[0](Role.ANALYST, "tenant-b")
    assert owner.get("/v1/events/" + private_id).status_code == 200
    viewer = clients[0](Role.VIEWER, "tenant-b")
    assert viewer.get("/v1/events/" + private_id).status_code == 404


def test_legacy_null_dates_no_invented_verified_locator(api_engine, clients) -> None:
    revision = seed_source_document(api_engine, legacy=True)
    event_id = seed_event(api_engine, [revision["revision_id"]])
    client = clients[0]()
    detail = client.get("/v1/events/" + event_id).json()["revisions"][0]
    assert detail["source_published_at"] is None
    assert detail["first_observed_at"] is None
    assert detail["ingested_at"] is None
    assert detail["parse_status"] == "legacy_unverified"
    response = client.get("/v1/evidence/" + revision["evidence_id"]).json()
    assert response["locator_kind"] == "legacy_unverified"
    assert response["verified_at"] is None
    assert response["quote_sha256"] == hashlib.sha256("中文🙂 old evidence".encode()).hexdigest()


@pytest.mark.parametrize(
    "path",
    [
        "/v1/events",
        "/v1/events/10000000-0000-0000-0000-000000000001",
        "/v1/evidence/10000000-0000-0000-0000-000000000001",
    ],
)
def test_missing_and_expired_cookie_denied(clients, path) -> None:
    client = TestClient(clients[1])
    assert client.get(path).status_code == 401
    client.cookies.set(SESSION_COOKIE_NAME, "invalid-fixture-session")
    assert client.get(path).status_code == 401
    client.close()


@pytest.mark.parametrize(
    "parameters",
    [
        {"cursor": ""},
        {"cursor": "bad?"},
        {"limit": 0},
        {"limit": 101},
        {"updated_after": "2026-10-15T00:00:00"},
    ],
)
def test_invalid_boundary_422(clients, parameters) -> None:
    client = clients[0]()
    response = client.get("/v1/events", params=parameters)
    assert response.status_code == 422
    assert "bad?" not in response.text


def test_invalid_uuid_fixed_problem(clients) -> None:
    response = clients[0]().get("/v1/evidence/not-a-uuid")
    assert response.status_code == 422
    assert response.json()["error"]["details"] == {}


def test_database_failure_not_empty_success(api_engine, clients) -> None:
    client = clients[0]()

    def unavailable(conn, cursor, statement, parameters, context, executemany):
        if "FROM events" in statement:
            from sqlalchemy.exc import OperationalError

            raise OperationalError(
                statement, parameters, RuntimeError("fixture sensitive db detail")
            )

    event.listen(api_engine, "before_cursor_execute", unavailable)
    try:
        response = client.get("/v1/events")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "knowledge_unavailable"
        assert response.json()["error"]["retryable"] is True
        assert "fixture sensitive db detail" not in response.text
        assert "SELECT" not in response.text
    finally:
        event.remove(api_engine, "before_cursor_execute", unavailable)


def test_missing_read_permission_403(clients, monkeypatch) -> None:
    client = clients[0]()
    monkeypatch.setattr(
        clients[2],
        "build_access_scope",
        lambda token: AccessScope("fixture-user", "tenant-a", Role.ANALYST, frozenset()),
    )
    response = client.get("/v1/events")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def seed_dimension(
    engine: Engine,
    event_id: str,
    revision: dict[str, str],
    claim_id: str | None,
    *,
    dimension: str = "cvss",
    status: str = "available",
) -> str:
    result_id = str(uuid4())
    with engine.begin() as connection:
        connection.execute(
            enrichment_results.insert().values(
                result_id=result_id,
                event_id=event_id,
                dimension=dimension,
                status=status,
                claim_ids=[claim_id] if claim_id else [],
                reference_ids=[revision["evidence_id"]] if claim_id else [],
                error_code="upstream_timeout" if status == "failed" else None,
                searched_at=NOW,
                source_scope=[revision["source_id"]],
                input_fingerprint="a" * 64,
                recorded_at=NOW,
                is_current=True,
                event_version=1,
                observed_at=NOW,
                freshness="current",
            )
        )
    return result_id


def test_dimension_state_and_event_version_staleness(api_engine, clients) -> None:
    revision = seed_source_document(api_engine)
    event_id = seed_event(api_engine, [revision["revision_id"]])
    claim_id = seed_claim(api_engine, revision, "fixture affected product")
    seed_dimension(api_engine, event_id, revision, claim_id)
    seed_dimension(api_engine, event_id, revision, None, dimension="epss", status="failed")
    client = clients[0]()
    result = client.get("/v1/events/" + event_id)
    assert result.status_code == 200
    dimensions = {item["dimension"]: item for item in result.json()["dimensions"]}
    assert dimensions["cvss"]["citations"][0]["revision_id"] == revision["revision_id"]
    assert dimensions["cvss"]["citations"][0]["quote"] == "中文🙂 old evidence"
    assert dimensions["epss"]["status"] == "failed"
    assert dimensions["epss"]["error_code"] == "upstream_timeout"
    assert dimensions["epss"]["claim_ids"] == []
    with api_engine.begin() as connection:
        connection.execute(
            update(events).where(events.c.event_id == event_id).values(business_version=2)
        )
    later = client.get("/v1/events/" + event_id).json()["dimensions"]
    assert all(item["freshness"] == "stale" for item in later)
    assert {item["dimension"]: item["status"] for item in later} == {
        "cvss": "available",
        "epss": "failed",
    }


def test_private_dimension_and_private_claim_reference_do_not_leak(api_engine, clients) -> None:
    public = seed_source_document(api_engine)
    private = seed_source_document(
        api_engine,
        source_visibility="tenant",
        source_tenant="tenant-b",
        visibility="tenant",
        tenant="tenant-b",
        body="private evidence body",
    )
    event_id = seed_event(api_engine, [public["revision_id"], private["revision_id"]])
    claim_id = seed_claim(
        api_engine, private, "private product", visibility="tenant", tenant="tenant-b"
    )
    seed_dimension(api_engine, event_id, private, claim_id)
    public_claim = seed_claim(api_engine, public, "public product")
    with api_engine.begin() as connection:
        connection.execute(
            claim_evidence.insert().values(
                claim_id=public_claim,
                evidence_id=private["evidence_id"],
                support_kind="context",
                validation_status="unverified",
            )
        )
    response = clients[0]().get("/v1/events/" + event_id)
    assert response.status_code == 200
    assert response.json()["dimensions"] == []
    assert "private product" not in response.text
    assert private["evidence_id"] not in response.text
    assert response.json()["claims"][0]["evidence_ids"] == [public["evidence_id"]]


def test_old_claim_does_not_adopt_new_revision_evidence(api_engine, clients) -> None:
    first = seed_source_document(api_engine)
    claim_id = seed_claim(api_engine, first, "old claim")
    second = seed_source_document(
        api_engine,
        source_id=first["source_id"],
        document_id=first["document_id"],
        previous_revision_id=first["revision_id"],
        revision_number=2,
        created_at=NOW + timedelta(seconds=1),
        body="new different fact",
    )
    event_id = seed_event(api_engine, [first["revision_id"], second["revision_id"]])
    with api_engine.begin() as connection:
        connection.execute(
            claim_evidence.insert().values(
                claim_id=claim_id,
                evidence_id=second["evidence_id"],
                support_kind="context",
                validation_status="unverified",
            )
        )
    claim = clients[0]().get("/v1/events/" + event_id).json()["claims"][0]
    assert claim["source_revision_id"] == first["revision_id"]
    assert claim["evidence_ids"] == [first["evidence_id"]]


@pytest.mark.parametrize("corruption", ["hash", "span", "block"])
def test_corrupt_verified_evidence_fails_closed(api_engine, clients, corruption) -> None:
    revision = seed_source_document(api_engine)
    with api_engine.begin() as connection:
        values = {"quote_sha256": "0" * 64} if corruption == "hash" else {"end_offset": 1000}
        if corruption == "block":
            other = seed_source_document(api_engine)
            values = {"block_id": other["block_id"]}
        connection.execute(
            update(evidence)
            .where(evidence.c.evidence_id == revision["evidence_id"])
            .values(**values)
        )
    response = clients[0]().get("/v1/evidence/" + revision["evidence_id"])
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "knowledge_unavailable"
    assert "中文" not in response.text
