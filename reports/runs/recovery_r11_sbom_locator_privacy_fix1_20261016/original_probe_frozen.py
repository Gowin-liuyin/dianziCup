"""Default app, real cookie login and production head; all uploads are synthetic fixtures."""

import copy
import hashlib
import json
import os
import secrets
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import MetaData, Table, create_engine, func, insert, select, text, update
from sqlalchemy.engine import make_url
from tests.integration.test_r11_sbom_inventory_postgres import document, raw_document, spdx_document
from tests.r11_forward_fixtures import forbid_business_table_creation, forbid_metadata_creation

from ai_intel.api.app import create_application
from ai_intel.api.auth_state import PgAuthenticationStateStore
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.assets.inventory_models import asset_snapshots, assets
from ai_intel.assets.sbom_persistence_models import asset_snapshot_sbom_sidecars
from ai_intel.domain.access import Role
from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.knowledge.models import users

pytestmark = pytest.mark.real_pg
ORIGIN = "http://localhost:5173"
OBSERVED = datetime(2026, 10, 16, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def default_engine():
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert url.database == "test_dianzi_r11_int_api_rev1_20261016"
    assert url.host == "127.0.0.1" and url.port == 25432
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(MetaData, "create_all", forbid_metadata_creation)
        patch.setattr(Table, "create", forbid_business_table_creation)
        run_migrations(url.render_as_string(hide_password=False))
    engine = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0022_sbom_sidecars"
        assert connection.scalar(text("SELECT current_schema()")) == "public"
    yield engine
    engine.dispose()


@pytest.fixture()
def api(default_engine, tmp_path, register_sensitive_failure_value):
    settings = ApplicationSettings(
        app_env="test", data_mode="fixture", database_url=SecretStr(default_engine.url.render_as_string(hide_password=False)),
        allowed_origins=(ORIGIN,), raw_content_directory=str(tmp_path), dependency_timeout_seconds=10,
    )
    bootstrap = AuthenticationSessionService(DatabaseUserDirectory(default_engine), (ORIGIN,), False,
                                             state_store=PgAuthenticationStateStore(default_engine))
    application = create_application(settings=settings)
    clients = []

    def login(role=Role.TENANT_ADMIN, tenant=None):
        username = "integrated-review-" + uuid4().hex
        password = secrets.token_urlsafe(24)
        register_sensitive_failure_value(SecretStr(password))
        account = bootstrap.create_precreated_user(username, password, tenant or "fixture-tenant-" + uuid4().hex, role)
        client = TestClient(application)
        clients.append(client)
        response = client.post("/v1/auth/login", headers={"Origin": ORIGIN}, json={"username": username, "password": password})
        assert response.status_code == 200
        csrf = response.json()["csrf_token"]
        register_sensitive_failure_value(SecretStr(csrf))
        register_sensitive_failure_value(SecretStr(client.cookies.get("ai_intel_session")))
        return client, {"Origin": ORIGIN, "X-CSRF-Token": csrf, "Idempotency-Key": str(uuid4())}, account

    yield login, settings, application
    for client in clients:
        client.close()


def upload(client, headers, raw=None, **parameters):
    return client.post("/v1/asset-imports", content=raw_document(document()) if raw is None else raw,
                       headers=headers, params={"manifest_format": "cyclonedx_json", "display_name": "Synthetic integrated asset",
                                               "source_version": "fixture-r11-integrated", "observed_at": OBSERVED.isoformat(), **parameters})


def path(created):
    return f"/v1/assets/{created['asset_id']}/snapshots/{created['snapshot']['snapshot_id']}/sbom"


def row_counts(engine, tenant):
    with engine.connect() as connection:
        return tuple(connection.scalar(select(func.count()).select_from(table).where(table.c.tenant_id == tenant))
                     for table in (assets, asset_snapshots, asset_snapshot_sbom_sidecars))


def test_default_routes_have_inventory_graph_r07_and_aliases(api):
    _, _, application = api
    paths = application.openapi()["paths"]
    expected = {"/v1/asset-imports", "/v1/assets/{asset_id}/snapshots/{snapshot_id}/sbom",
                "/v1/events/{event_id}/graph", "/v1/events/{event_id}/enrichment-jobs", "/v1/jobs/{job_id}"}
    assert expected <= set(paths)
    with TestClient(application) as client:
        for prefix in ("/v1", "/api/v1"):
            assert client.get(prefix + "/assets").status_code == 401
            assert client.get(prefix + "/events/" + str(uuid4()) + "/graph").status_code == 401
            assert client.get(prefix + "/enrichment-workflows/" + str(uuid4())).status_code == 401


@pytest.mark.parametrize("kind", ["cyclonedx_json", "spdx_json", "json_manifest_v1", "csv_components_v1"])
def test_actual_supported_raw_formats_and_sbom_readroute(default_engine, api, kind):
    login, _, _ = api
    client, headers, account = login()
    if kind == "cyclonedx_json":
        raw = b" " + raw_document(document()) + b"\n"
    elif kind == "spdx_json":
        raw = raw_document(spdx_document())
    elif kind == "json_manifest_v1":
        raw = b'{"format_version":1,"components":[{"ecosystem":"pypi","package_name":"langchain","purl":"pkg:pypi/langchain@1.0","version":"1.0"}],"inventory_completeness":"partial"}'
    else:
        raw = b'ecosystem,package_name,version,purl\npypi,langchain,1.0,pkg:pypi/langchain@1.0\n'
    parameters = {}
    if kind == "csv_components_v1":
        parameters["csv_column_mapping"] = json.dumps({"ecosystem": "ecosystem", "package_name": "package_name", "version": "version", "purl": "purl"})
    result = upload(client, headers, raw, manifest_format=kind, **parameters)
    assert result.status_code == 201, result.text
    created = result.json()
    assert created["snapshot"]["tenant_id"] == account.tenant_id
    read = client.get(path(created))
    assert read.status_code == (200 if kind in {"cyclonedx_json", "spdx_json"} else 404)
    full = client.get(path(created).removesuffix("/sbom"))
    assert full.status_code == 200 and full.json() == created["snapshot"]
    if kind in {"json_manifest_v1", "csv_components_v1"}:
        assert full.json()["components"][0]["purl"] == "pkg:pypi/langchain@1.0"
    with default_engine.connect() as connection:
        row = connection.execute(select(asset_snapshots).where(asset_snapshots.c.snapshot_id == created["snapshot"]["snapshot_id"])).mappings().one()
        assert bytes(row["raw_input"]) == raw
        assert row["raw_input_sha256"] == hashlib.sha256(raw).hexdigest()
        assert row["manifest_sha256"] == created["snapshot"]["snapshot_sha256"]


def test_snapshot_history_sidecar_only_change_replay_and_reopen(default_engine, api):
    login, settings, _ = api
    client, headers, account = login()
    first_raw = raw_document(document())
    first_response = upload(client, headers, first_raw)
    assert first_response.status_code == 201
    first = first_response.json()
    before_sidecar = client.get(path(first)).json()
    changed = document()
    changed["dependencies"][0]["dependsOn"] = ["b"]
    second = upload(client, {**headers, "Idempotency-Key": str(uuid4())}, raw_document(changed), asset_id=first["asset_id"]).json()
    assert second["snapshot"]["snapshot_number"] == 2
    assert second["snapshot"]["snapshot_sha256"] == first["snapshot"]["snapshot_sha256"]
    assert client.get(path(first)).json() == before_sidecar
    third_response = upload(client, {**headers, "Idempotency-Key": str(uuid4())}, first_raw, asset_id=first["asset_id"])
    assert third_response.status_code == 201
    third = third_response.json()
    assert third["snapshot"]["snapshot_number"] == 3
    replay = upload(client, headers, first_raw).json()
    assert replay["reused"] and replay["snapshot"]["snapshot_id"] == first["snapshot"]["snapshot_id"]
    assert client.get("/v1/assets/" + first["asset_id"]).json()["current_snapshot_id"] == third["snapshot"]["snapshot_id"]
    history = client.get("/v1/assets/" + first["asset_id"] + "/snapshots").json()["items"]
    assert {entry["snapshot_number"] for entry in history} == {1, 2, 3}
    default_engine.dispose()
    with TestClient(create_application(settings=settings)) as reopened:
        reopened.cookies.update(client.cookies)
        response = reopened.get(path(first))
        assert response.status_code == 200 and response.json() == before_sidecar
        assert reopened.get("/api/v1/assets/" + first["asset_id"]).json()["current_snapshot_id"] == third["snapshot"]["snapshot_id"]
    assert row_counts(default_engine, account.tenant_id) == (1, 3, 3)


def test_true_cookie_two_tenants_read_permission_and_spoof(default_engine, api):
    login, _, _ = api
    first, headers, account = login()
    result = upload(first, headers).json()
    foreign, foreign_headers, _ = login()
    for route in (path(result), path(result).removesuffix("/sbom"), "/v1/assets/" + result["asset_id"], "/v1/assets/" + result["asset_id"] + "/snapshots"):
        response = foreign.get(route)
        assert response.status_code == 404
        assert account.tenant_id not in response.text
        assert set(response.json()) <= {"type", "title", "status", "detail", "instance", "trace_id", "error"}
    assert upload(foreign, foreign_headers, asset_id=result["asset_id"]).status_code == 404
    analyst, analyst_headers, _ = login(Role.ANALYST, account.tenant_id)
    assert analyst.get(path(result)).status_code == 200
    assert upload(analyst, analyst_headers).status_code == 403
    before = row_counts(default_engine, account.tenant_id)
    assert upload(first, {**headers, "Idempotency-Key": str(uuid4())}, tenant_id="forged-other").status_code == 422
    payload = document()
    payload["tenant_id"] = "forged-other"
    assert upload(first, {**headers, "Idempotency-Key": str(uuid4())}, raw_document(payload)).status_code == 422
    assert row_counts(default_engine, account.tenant_id) == before


@pytest.mark.parametrize("phase", ["read", "write"])
def test_late_current_role_revocation_rechecked(default_engine, api, monkeypatch, phase):
    login, _, _ = api
    client, headers, account = login()
    created = upload(client, headers).json()
    before = row_counts(default_engine, account.tenant_id)
    original = AuthenticationSessionService.build_access_scope
    invoked = False

    def revoke_after_initial(authentication, token):
        nonlocal invoked
        initial = original(authentication, token)
        if not invoked:
            invoked = True
            with default_engine.begin() as connection:
                connection.execute(update(users).where(users.c.user_id == account.user_id).values(role="viewer"))
        return initial

    monkeypatch.setattr(AuthenticationSessionService, "build_access_scope", revoke_after_initial)
    response = client.get(path(created)) if phase == "read" else upload(client, {**headers, "Idempotency-Key": str(uuid4())}, asset_id=created["asset_id"])
    assert invoked and response.status_code == 403
    assert row_counts(default_engine, account.tenant_id) == before


@pytest.mark.parametrize("invalid", ["lock", "vex", "unknown", "bad_json", "duplicate", "wrong_version", "missing_key", "csrf", "origin", "too_big", "empty"])
def test_unsupported_and_error_uploads_are_explicit_and_atomic(default_engine, api, invalid):
    login, _, _ = api
    client, headers, account = login()
    raw, parameters = raw_document(document()), {}
    if invalid == "lock":
        raw, parameters = b'package==1.0\n', {"manifest_format": "requirements_lock"}
    elif invalid == "vex":
        raw, parameters = b'{"@context":"https://openvex.dev/ns/v0.2.0","statements":[]}', {"manifest_format": "openvex_json"}
    elif invalid == "unknown":
        parameters = {"manifest_format": "invented_format"}
    elif invalid == "bad_json":
        raw = b'{"bomFormat":'
    elif invalid == "duplicate":
        raw = b'{"bomFormat":"CycloneDX","bomFormat":"CycloneDX","specVersion":"1.7","version":1,"components":[]}'
    elif invalid == "wrong_version":
        raw = raw_document(document("2.0"))
    elif invalid == "missing_key":
        headers = {name: value for name, value in headers.items() if name != "Idempotency-Key"}
    elif invalid == "csrf":
        headers["X-CSRF-Token"] = "invalid"
    elif invalid == "origin":
        headers["Origin"] = "https://unapproved.example"
    elif invalid == "too_big":
        raw = b"x" * 1048577
    elif invalid == "empty":
        raw = b""
    before = row_counts(default_engine, account.tenant_id)
    response = upload(client, headers, raw, **parameters)
    expected = 403 if invalid in {"csrf", "origin"} else 413 if invalid in {"too_big", "empty"} else 422
    assert response.status_code == expected, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["error"]["code"]
    assert row_counts(default_engine, account.tenant_id) == before


def test_partial_manifest_keeps_unknown_version_and_completeness(api):
    login, _, _ = api
    client, headers, _ = login()
    raw = b'{"format_version":1,"inventory_completeness":"partial","components":[{"ecosystem":"mystery","package_name":"synthetic"}]}'
    response = upload(client, headers, raw, manifest_format="json_manifest_v1")
    assert response.status_code == 201
    value = response.json()["snapshot"]
    assert value["inventory_completeness"] == "partial"
    assert value["components"][0]["version"] is None
    assert value["components"][0]["version_scheme"] == "unknown"


def test_safe_uri_purl_locator_and_topology_default_http(default_engine, api):
    login, _, _ = api
    client, headers, _ = login()
    value = document()
    private = "postgresql://synthetic_user:synthetic_password@db.internal:5432/private"
    value["components"][0]["bom-ref"] = private
    value["components"][0].pop("version")
    value["components"][0]["purl"] = "pkg:pypi/a@postgresql%3A%2F%2Fsynthetic_user%3Asynthetic_password%40db.internal%3A5432%2Fprivate"
    value["dependencies"][0] = {"ref": private, "dependsOn": ["b"]}
    value["compositions"][0]["assemblies"] = [private]
    encoded = "file%25252525253A%25252525252F%25252525252F%25252525252FC%25252525253A%25252525252Fprivate"
    value[encoded] = {"opaque": "synthetic-private-marker"}
    raw = raw_document(value)
    response = upload(client, headers, raw)
    assert response.status_code == 201, response.text
    created = response.json()
    public = client.get(path(created))
    assert public.status_code == 200
    sidecar = public.json()
    alias = "redacted-ref:" + hashlib.sha256(private.encode()).hexdigest()
    assert sidecar["component_sources"][0]["source_ref"] == alias
    assert sidecar["dependency_edges"][0]["source_ref"] == alias
    assert sidecar["dependency_edges"][0]["target_ref"] == "b"
    assert sidecar["completeness_declarations"][0]["assemblies"] == [alias]
    assert any(entry["reason"] == "unsafe_uri_or_path" and entry["replacement_ref"] == alias for entry in sidecar["redactions"])
    for route in (path(created).removesuffix("/sbom"), "/v1/assets/" + created["asset_id"], "/v1/assets/" + created["asset_id"] + "/snapshots", "/v1/assets"):
        observed = client.get(route)
        assert observed.status_code == 200
        assert private not in observed.text and "synthetic_password" not in observed.text
    assert created["snapshot"]["components"][0]["purl"] is None
    assert encoded not in public.text and private not in public.text
    with default_engine.connect() as connection:
        saved = connection.execute(select(asset_snapshots).where(asset_snapshots.c.snapshot_id == created["snapshot"]["snapshot_id"])).mappings().one()
        assert bytes(saved["raw_input"]) == raw
        assert saved["raw_input_sha256"] == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize("key", ["../../private/sbom.json", "..\\..\\private\\sbom.json"])
def test_relative_private_path_key_never_leaves_default_api(api, key):
    login, _, _ = api
    client, headers, _ = login()
    value = document()
    value["components"][0][key] = "opaque-synthetic"
    result = upload(client, headers, raw_document(value))
    assert result.status_code == 201
    response = client.get(path(result.json()))
    assert response.status_code == 200
    assert "private" not in response.text and "sbom.json" not in response.text
    assert any(item["reason"] == "unsafe_uri_or_path" and "redacted-field:" in item["source_field_locator"] for item in response.json()["redactions"])


def test_partly_redacted_forged_immutable_locator_returns_safe_503(default_engine, api):
    login, _, _ = api
    client, headers, _ = login()
    created = upload(client, headers).json()
    with default_engine.connect() as connection:
        snapshot = copy.deepcopy(dict(connection.execute(select(asset_snapshots).where(asset_snapshots.c.snapshot_id == created["snapshot"]["snapshot_id"])).mappings().one()))
        sidecar = copy.deepcopy(dict(connection.execute(select(asset_snapshot_sbom_sidecars).where(asset_snapshot_sbom_sidecars.c.snapshot_id == snapshot["snapshot_id"])).mappings().one()))
    new_id = str(uuid4())
    snapshot.update(snapshot_id=new_id, snapshot_number=2, previous_snapshot_id=snapshot["snapshot_id"])
    snapshot["canonical_payload"].update(snapshot_id=new_id, snapshot_number=2)
    sidecar["snapshot_id"] = new_id
    sidecar["canonical_payload"]["snapshot_id"] = new_id
    locator = "/redacted-field:" + "a" * 64 + "/postgresql:~1~1synthetic_user:synthetic_password@db.internal~1private"
    sidecar["canonical_payload"]["unmapped_field_locators"] = [locator]
    sidecar["canonical_payload"]["redactions"] = [{"source_field_locator": locator, "reason": "unsafe_uri_or_path", "replacement_ref": None}]
    with default_engine.begin() as connection:
        connection.execute(insert(asset_snapshots).values(snapshot))
        connection.execute(insert(asset_snapshot_sbom_sidecars).values(sidecar))
    response = client.get(f"/v1/assets/{created['asset_id']}/snapshots/{new_id}/sbom")
    assert response.status_code == 503
    assert "synthetic_password" not in response.text and "postgresql:" not in response.text
