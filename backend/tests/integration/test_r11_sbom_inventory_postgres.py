"""专用真实PG与HTTP的SBOM历史事务；合成上传不冒产品live。"""

import hashlib
import json
import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, delete, func, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_intel.api.auth_routes import build_auth_router
from ai_intel.api.auth_state import PgAuthenticationStateStore
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.assets.inventory import InventoryService
from ai_intel.assets.inventory_models import asset_snapshots
from ai_intel.assets.inventory_routes import build_inventory_router
from ai_intel.assets.sbom_persistence_models import asset_snapshot_sbom_sidecars
from ai_intel.domain.access import AccessScope, CrossTenantAccessError, Role
from ai_intel.infrastructure.outbox import IdempotencyConflictError
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.knowledge.models import job_runs, outbox_events, users
from ai_intel.knowledge.persistence_models import change_events

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 16, 0, tzinfo=UTC)
ORIGIN = "http://localhost:5173"


@pytest.fixture(scope="module")
def sbom_engine():
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert url.database.startswith("test_dianzi_r11_sbom_inventory_")
    assert url.host in {"127.0.0.1", "localhost"} and url.port == 25432
    assert os.environ.get("DIANZI_TEST_RUN_ID", "").startswith("r11_sbom_inventory_")
    engine = create_engine(
        url,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 5,
            "options": "-c statement_timeout=15000 -c lock_timeout=5000",
        },
    )
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0019_aggregate_observations"
        )
        assert (
            connection.scalar(text("SELECT to_regclass('asset_snapshot_sbom_sidecars')"))
            is not None
        )
    yield engine
    engine.dispose()


def actor(engine, tenant=None):
    identity = str(uuid4())
    tenant = tenant or "sbom-tenant-" + uuid4().hex
    with engine.begin() as connection:
        connection.execute(
            insert(users).values(
                user_id=identity,
                username="sbom-user-" + identity,
                password_hash="synthetic-unused",
                tenant_id=tenant,
                role=Role.TENANT_ADMIN.value,
                created_at=NOW,
            )
        )
    return AccessScope.for_authenticated_user(identity, tenant, Role.TENANT_ADMIN)


def document(version="1.7"):
    return {
        "bomFormat": "CycloneDX",
        "specVersion": version,
        "version": 1,
        "components": [
            {
                "type": "library",
                "name": "a",
                "version": "1",
                "bom-ref": "a",
                "hashes": [{"alg": "SHA-256", "content": "a" * 64}],
            },
            {"type": "library", "name": "b", "version": "1", "bom-ref": "b"},
        ],
        "dependencies": [{"ref": "a", "dependsOn": []}],
        "compositions": [{"aggregate": "unknown", "assemblies": ["a"]}],
        "opaque": "synthetic-private-marker",
    }


def spdx_document():
    return {
        "spdxVersion": "SPDX-2.3",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "synthetic",
        "documentNamespace": "https://example.test/sbom",
        "dataLicense": "CC0-1.0",
        "creationInfo": {"created": "2026-10-16T00:00:00Z", "creators": ["Tool: synthetic"]},
        "packages": [
            {
                "SPDXID": "SPDXRef-A",
                "name": "a",
                "versionInfo": "1",
                "downloadLocation": "NOASSERTION",
                "checksums": [{"algorithm": "SHA256", "checksumValue": "b" * 64}],
            }
        ],
        "externalDocumentRefs": [
            {
                "externalDocumentId": "DocumentRef-external",
                "spdxDocument": "https://example.test/external",
                "checksum": {"algorithm": "SHA256", "checksumValue": "c" * 64},
            }
        ],
        "relationships": [
            {
                "spdxElementId": "SPDXRef-A",
                "relatedSpdxElement": "DocumentRef-external:SPDXRef-B",
                "relationshipType": "DEPENDS_ON",
            }
        ],
    }


def raw_document(value):
    return json.dumps(value, separators=(",", ":")).encode()


def save(engine, scope, value=None, **options):
    raw = (
        value if isinstance(value, bytes) else raw_document(document() if value is None else value)
    )
    with Session(engine) as session, session.begin():
        return InventoryService(session, scope).import_manifest(
            raw,
            manifest_format=options.pop("manifest_format", "cyclonedx_json"),
            display_name="Synthetic SBOM asset",
            source_version="synthetic-sbom-1",
            observed_at=NOW,
            idempotency_key=options.pop("key", str(uuid4())),
            **options,
        )


def counts(engine, tenant):
    with engine.connect() as connection:
        return {
            "snapshots": connection.scalar(
                select(func.count())
                .select_from(asset_snapshots)
                .where(asset_snapshots.c.tenant_id == tenant)
            ),
            "sidecars": connection.scalar(
                select(func.count())
                .select_from(asset_snapshot_sbom_sidecars)
                .where(asset_snapshot_sbom_sidecars.c.tenant_id == tenant)
            ),
            "changes": connection.scalar(
                select(func.count())
                .select_from(change_events)
                .where(change_events.c.scope_key == "tenant:" + tenant)
            ),
            "outbox": connection.scalar(
                select(func.count())
                .select_from(outbox_events.join(job_runs))
                .where(job_runs.c.tenant_id == tenant)
            ),
        }


@pytest.mark.parametrize("version", ["1.5", "1.6", "1.7"])
def test_cdx_raw_and_typed_sources_are_immutable_facts(sbom_engine, version):
    scope = actor(sbom_engine)
    raw = b" " + raw_document(document(version)) + b"\n"
    imported = save(sbom_engine, scope, raw)
    with Session(sbom_engine) as session:
        sidecar = InventoryService(session, scope).get_snapshot_sbom(
            imported.asset_id, imported.snapshot.snapshot_id
        )
    assert sidecar.spec_version == version
    assert sidecar.component_sources[0].checksums[0].checksum_value == "a" * 64
    assert sidecar.component_sources[0].source_ref == "a"
    assert sidecar.completeness_declarations[0].aggregate == "unknown"
    assert "synthetic-private-marker" not in sidecar.model_dump_json()
    assert imported.snapshot.components[0].image_digest is None
    assert imported.snapshot.components[0].dependency_path is None
    assert imported.snapshot.inventory_completeness == "unknown"
    with sbom_engine.connect() as connection:
        row = (
            connection.execute(
                select(asset_snapshots).where(
                    asset_snapshots.c.snapshot_id == imported.snapshot.snapshot_id
                )
            )
            .mappings()
            .one()
        )
        assert bytes(row["raw_input"]) == raw
        assert row["raw_input_sha256"] == hashlib.sha256(raw).hexdigest() == sidecar.raw_sha256
        assert row["manifest_sha256"] == sidecar.projection_sha256


def test_spdx_external_document_checksum_and_relationship_are_persisted(sbom_engine):
    scope = actor(sbom_engine)
    imported = save(sbom_engine, scope, spdx_document(), manifest_format="spdx_json")
    with Session(sbom_engine) as session:
        sidecar = InventoryService(session, scope).get_snapshot_sbom(
            imported.asset_id, imported.snapshot.snapshot_id
        )
    assert sidecar.spec_version == "SPDX-2.3"
    assert sidecar.component_sources[0].checksums[0].checksum_value == "b" * 64
    assert sidecar.external_documents[0].checksum.checksum_value == "c" * 64
    assert sidecar.external_documents[0].document_uri == "https://example.test/external"
    assert sidecar.dependency_edges[0].target_ref == "DocumentRef-external:SPDXRef-B"
    assert sidecar.dependency_edges[0].relationship == "DEPENDS_ON"
    assert imported.snapshot.inventory_completeness == "unknown"
    assert imported.snapshot.components[0].image_digest is None


@pytest.mark.parametrize("change", ["graph", "checksum", "composition", "opaque"])
def test_sidecar_only_change_is_new_history_and_publication(sbom_engine, change):
    scope = actor(sbom_engine)
    original = document()
    first = save(sbom_engine, scope, original)
    modified = document()
    if change == "graph":
        modified["dependencies"][0]["dependsOn"] = ["b"]
    elif change == "checksum":
        modified["components"][0]["hashes"][0]["content"] = "b" * 64
    elif change == "composition":
        modified["compositions"][0]["aggregate"] = "complete"
    else:
        modified["opaque"] = "changed-synthetic-private-marker"
    second = save(sbom_engine, scope, modified, asset_id=first.asset_id)
    assert not second.reused and second.snapshot.snapshot_number == 2
    assert first.snapshot.snapshot_sha256 == second.snapshot.snapshot_sha256
    assert first.snapshot.snapshot_id != second.snapshot.snapshot_id
    assert counts(sbom_engine, scope.tenant_id) == {
        "snapshots": 2,
        "sidecars": 2,
        "changes": 2,
        "outbox": 2,
    }
    with Session(sbom_engine) as session:
        reader = InventoryService(session, scope)
        before = reader.get_snapshot_sbom(first.asset_id, first.snapshot.snapshot_id)
        after = reader.get_snapshot_sbom(first.asset_id, second.snapshot.snapshot_id)
        assert before.combined_semantic_sha256 != after.combined_semantic_sha256
        assert reader.read_asset(first.asset_id).current_snapshot_id == second.snapshot.snapshot_id
    with sbom_engine.connect() as connection:
        payloads = (
            connection.execute(
                select(change_events.c.payload).where(
                    change_events.c.scope_key == "tenant:" + scope.tenant_id
                )
            )
            .scalars()
            .all()
        )
        assert {payload["combined_semantic_sha256"] for payload in payloads} == {
            before.combined_semantic_sha256,
            after.combined_semantic_sha256,
        }
        assert {payload["manifest_sha256"] for payload in payloads} == {
            first.snapshot.snapshot_sha256
        }
        assert all("sidecar_sha256" in payload for payload in payloads)


def test_semantic_repeat_raw_replay_and_a_b_a_do_not_restore_old_current(sbom_engine):
    scope = actor(sbom_engine)
    key = str(uuid4())
    first = save(sbom_engine, scope, key=key)
    formatted = json.dumps(dict(reversed(list(document().items()))), indent=2).encode()
    repeated = save(sbom_engine, scope, formatted, asset_id=first.asset_id)
    assert repeated.reused and repeated.snapshot.snapshot_id == first.snapshot.snapshot_id
    changed = document()
    changed["dependencies"][0]["dependsOn"] = ["b"]
    second = save(sbom_engine, scope, changed, asset_id=first.asset_id)
    replay = save(sbom_engine, scope, key=key)
    assert replay.reused and replay.snapshot.snapshot_id == first.snapshot.snapshot_id
    with Session(sbom_engine) as session:
        assert (
            InventoryService(session, scope).read_asset(first.asset_id).current_snapshot_id
            == second.snapshot.snapshot_id
        )
    third = save(sbom_engine, scope, asset_id=first.asset_id)
    assert not third.reused and third.snapshot.snapshot_number == 3
    assert (
        len({first.snapshot.snapshot_id, second.snapshot.snapshot_id, third.snapshot.snapshot_id})
        == 3
    )
    assert counts(sbom_engine, scope.tenant_id) == {
        "snapshots": 3,
        "sidecars": 3,
        "changes": 3,
        "outbox": 3,
    }


def test_same_key_with_different_sidecar_conflicts(sbom_engine):
    scope = actor(sbom_engine)
    key = str(uuid4())
    save(sbom_engine, scope, key=key)
    changed = document()
    changed["dependencies"][0]["dependsOn"] = ["b"]
    with pytest.raises(IdempotencyConflictError):
        save(sbom_engine, scope, changed, key=key)
    assert counts(sbom_engine, scope.tenant_id)["snapshots"] == 1


def test_same_combined_parallel_requests_publish_once(sbom_engine):
    scope = actor(sbom_engine)
    first = save(sbom_engine, scope)
    changed = document()
    changed["dependencies"][0]["dependsOn"] = ["b"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda _: save(sbom_engine, scope, changed, asset_id=first.asset_id), range(4))
        )
    assert sum(not result.reused for result in results) == 1
    assert len({result.snapshot.snapshot_id for result in results}) == 1
    assert counts(sbom_engine, scope.tenant_id)["outbox"] == 2


def test_sidecar_failed_publication_rolls_back_every_fact(sbom_engine, monkeypatch):
    scope = actor(sbom_engine)
    first = save(sbom_engine, scope)
    before = counts(sbom_engine, scope.tenant_id)

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic publication failure")

    monkeypatch.setattr("ai_intel.assets.inventory.save_change_publication", fail)
    changed = document()
    changed["dependencies"][0]["dependsOn"] = ["b"]
    with pytest.raises(RuntimeError, match="synthetic publication failure"):
        save(sbom_engine, scope, changed, asset_id=first.asset_id)
    assert counts(sbom_engine, scope.tenant_id) == before
    with Session(sbom_engine) as session:
        assert (
            InventoryService(session, scope).read_asset(first.asset_id).current_snapshot_id
            == first.snapshot.snapshot_id
        )


def test_sidecar_mutation_and_cross_tenant_snapshot_fk_are_rejected(sbom_engine):
    scope = actor(sbom_engine)
    first = save(sbom_engine, scope)
    table = asset_snapshot_sbom_sidecars
    for statement in (
        update(table)
        .where(table.c.snapshot_id == first.snapshot.snapshot_id)
        .values(spec_version="changed"),
        delete(table).where(table.c.snapshot_id == first.snapshot.snapshot_id),
    ):
        with pytest.raises(IntegrityError), sbom_engine.begin() as connection:
            connection.execute(statement)
    json_snapshot = save(
        sbom_engine,
        scope,
        {"format_version": 1, "components": [{"package_name": "a"}]},
        manifest_format="json_manifest_v1",
    )
    with sbom_engine.connect() as connection:
        copied = dict(
            connection.execute(
                select(table).where(table.c.snapshot_id == first.snapshot.snapshot_id)
            )
            .mappings()
            .one()
        )
    copied["snapshot_id"] = json_snapshot.snapshot.snapshot_id
    copied["tenant_id"] = "foreign-tenant"
    with pytest.raises(IntegrityError), sbom_engine.begin() as connection:
        connection.execute(insert(table).values(copied))


def test_reads_are_tenant_bound_and_historical_payload_never_reparsed(sbom_engine, monkeypatch):
    owner, foreign = actor(sbom_engine), actor(sbom_engine)
    first = save(sbom_engine, owner)

    def fail(*args, **kwargs):
        raise AssertionError("historical parser must not run")

    monkeypatch.setattr("ai_intel.assets.sbom_inventory.parse_sbom", fail)
    with Session(sbom_engine) as session:
        sidecar = InventoryService(session, owner).get_snapshot_sbom(
            first.asset_id, first.snapshot.snapshot_id
        )
        assert sidecar.component_sources[0].source_ref == "a"
        with pytest.raises(CrossTenantAccessError):
            InventoryService(session, foreign).get_snapshot_sbom(
                first.asset_id, first.snapshot.snapshot_id
            )


def test_cross_format_new_snapshot_keeps_legacy_dto_and_no_sidecar_extra(sbom_engine):
    scope = actor(sbom_engine)
    first = save(
        sbom_engine,
        scope,
        {"format_version": 1, "components": [{"package_name": "a", "version": "1"}]},
        manifest_format="json_manifest_v1",
    )
    sbom = document()
    sbom["components"] = sbom["components"][:1]
    second = save(sbom_engine, scope, sbom, asset_id=first.asset_id)
    assert first.snapshot.snapshot_sha256 == second.snapshot.snapshot_sha256
    assert second.snapshot.snapshot_number == 2 and not second.reused
    assert "combined_semantic_sha256" not in second.snapshot.model_dump()
    third = save(
        sbom_engine,
        scope,
        {"format_version": 1, "components": [{"package_name": "a", "version": "1"}]},
        asset_id=first.asset_id,
        manifest_format="json_manifest_v1",
    )
    assert third.snapshot.snapshot_number == 3 and not third.reused
    with Session(sbom_engine) as session, pytest.raises(CrossTenantAccessError):
        InventoryService(session, scope).get_snapshot_sbom(
            first.asset_id, third.snapshot.snapshot_id
        )


@pytest.fixture
def sbom_api(sbom_engine, register_sensitive_failure_value):
    authentication = AuthenticationSessionService(
        DatabaseUserDirectory(sbom_engine),
        (ORIGIN,),
        False,
        state_store=PgAuthenticationStateStore(sbom_engine),
    )
    app = FastAPI()
    app.include_router(
        build_auth_router(
            lambda: authentication, ApplicationSettings(app_env="test", data_mode="fixture")
        ),
        prefix="/api",
    )
    app.include_router(build_inventory_router(lambda: authentication, sbom_engine), prefix="/api")
    clients = []

    def login(role=Role.TENANT_ADMIN, tenant=None):
        username, password = "sbom-api-" + uuid4().hex, secrets.token_urlsafe(24)
        register_sensitive_failure_value(SecretStr(password))
        account = authentication.create_precreated_user(
            username, password, tenant or "sbom-api-" + uuid4().hex, role
        )
        client = TestClient(app)
        clients.append(client)
        response = client.post(
            "/api/auth/login",
            headers={"Origin": ORIGIN},
            json={"username": username, "password": password},
        )
        assert response.status_code == 200
        csrf = response.json()["csrf_token"]
        register_sensitive_failure_value(SecretStr(csrf))
        register_sensitive_failure_value(SecretStr(client.cookies.get("ai_intel_session")))
        return (
            client,
            {"Origin": ORIGIN, "X-CSRF-Token": csrf, "Idempotency-Key": str(uuid4())},
            account,
        )

    yield login, authentication
    for client in clients:
        client.close()


def upload(client, headers, raw=None, **params):
    return client.post(
        "/api/asset-imports",
        content=raw_document(document()) if raw is None else raw,
        headers=headers,
        params={
            "display_name": "Synthetic SBOM asset",
            "source_version": "synthetic-sbom-1",
            "observed_at": NOW.isoformat(),
            "manifest_format": "cyclonedx_json",
            **params,
        },
    )


def test_real_authenticated_upload_read_replay_and_acl(sbom_engine, sbom_api):
    login, authentication = sbom_api
    client, headers, account = login()
    first = upload(client, headers)
    assert first.status_code == 201
    identity, snapshot = first.json()["asset_id"], first.json()["snapshot"]["snapshot_id"]
    url = f"/api/assets/{identity}/snapshots/{snapshot}/sbom"
    read = client.get(url)
    assert read.status_code == 200 and read.json()["tenant_id"] == account.tenant_id
    assert read.json()["component_sources"][0]["checksums"][0]["checksum_value"] == "a" * 64
    assert "synthetic-private-marker" not in read.text
    assert "raw_input" not in read.text and "opaque" not in read.json()
    assert upload(client, headers).json()["reused"] is True
    assert set(client.get(f"/api/assets/{identity}/snapshots/{snapshot}").json()) == set(
        first.json()["snapshot"]
    )
    foreign, _, _ = login()
    assert foreign.get(url).status_code == 404
    analyst, analyst_headers, _ = login(Role.ANALYST, account.tenant_id)
    assert analyst.get(url).status_code == 200
    assert upload(analyst, analyst_headers).status_code == 403
    authentication.logout(client.cookies.get("ai_intel_session"))
    assert client.get(url).status_code == 401


@pytest.mark.parametrize("format_name", ["cyclonedx_json", "spdx_json"])
def test_http_10000_components_persist_exact_raw_and_every_source(
    sbom_engine, sbom_api, format_name
):
    login, _ = sbom_api
    client, headers, account = login()
    if format_name == "cyclonedx_json":
        value = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.7",
            "version": 1,
            "components": [
                {"type": "library", "name": f"p{i}", "version": "1", "purl": f"pkg:pypi/p{i}"}
                for i in range(10000)
            ],
        }
    else:
        value = spdx_document()
        value.pop("relationships")
        value.pop("externalDocumentRefs")
        value["packages"] = [
            {
                "SPDXID": f"SPDXRef-{i}",
                "name": f"p{i}",
                "versionInfo": "1",
                "downloadLocation": "NOASSERTION",
            }
            for i in range(10000)
        ]
    raw = raw_document(value)
    assert len(raw) < 1048576
    response = upload(client, headers, raw, manifest_format=format_name)
    assert response.status_code == 201
    snapshot = response.json()["snapshot"]
    assert len(snapshot["components"]) == 10000
    assert snapshot["components"][-1]["package_name"] == "p9999"
    assert {component["version"] for component in snapshot["components"]} == {"1"}
    url = f"/api/assets/{response.json()['asset_id']}/snapshots/{snapshot['snapshot_id']}/sbom"
    sidecar = client.get(url)
    assert sidecar.status_code == 200 and len(sidecar.json()["component_sources"]) == 10000
    with sbom_engine.connect() as connection:
        row = connection.execute(
            select(asset_snapshots.c.raw_input, asset_snapshots.c.raw_input_sha256).where(
                asset_snapshots.c.snapshot_id == snapshot["snapshot_id"]
            )
        ).one()
        assert bytes(row[0]) == raw and row[1] == hashlib.sha256(raw).hexdigest()
    assert counts(sbom_engine, account.tenant_id)["changes"] == 1


def test_sidecar_read_uses_role_at_transaction_entry(sbom_engine, sbom_api, monkeypatch):
    login, authentication = sbom_api
    client, headers, account = login()
    created = upload(client, headers)
    snapshot = created.json()["snapshot"]["snapshot_id"]
    url = f"/api/assets/{created.json()['asset_id']}/snapshots/{snapshot}/sbom"
    original = authentication.build_access_scope

    def revoke_read_permission(token):
        previous = original(token)
        with sbom_engine.begin() as connection:
            connection.execute(
                update(users)
                .where(users.c.user_id == account.user_id)
                .values(role=Role.VIEWER.value)
            )
        return previous

    monkeypatch.setattr(authentication, "build_access_scope", revoke_read_permission)
    response = client.get(url)
    assert response.status_code == 403
    assert "synthetic-private-marker" not in response.text


@pytest.mark.parametrize("corruption", ["binding", "shape"])
def test_inconsistent_stored_sidecar_is_unavailable_without_exposing_payload(
    sbom_engine, sbom_api, corruption
):
    login, _ = sbom_api
    client, headers, account = login()
    created = upload(client, headers)
    legacy = upload(
        client,
        {**headers, "Idempotency-Key": str(uuid4())},
        b'{"format_version":1,"components":[{"package_name":"a","version":"1"}]}',
        manifest_format="json_manifest_v1",
    )
    table = asset_snapshot_sbom_sidecars
    with sbom_engine.connect() as connection:
        copied = dict(
            connection.execute(
                select(table).where(
                    table.c.snapshot_id == created.json()["snapshot"]["snapshot_id"]
                )
            )
            .mappings()
            .one()
        )
    copied["asset_id"] = legacy.json()["asset_id"]
    copied["snapshot_id"] = legacy.json()["snapshot"]["snapshot_id"]
    if corruption == "shape":
        copied["canonical_payload"] = {"opaque": "synthetic-private-marker"}
    with sbom_engine.begin() as connection:
        connection.execute(insert(table).values(copied))
    url = f"/api/assets/{copied['asset_id']}/snapshots/{copied['snapshot_id']}/sbom"
    response = client.get(url)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "inventory_unavailable"
    assert "synthetic-private-marker" not in response.text
    assert account.tenant_id not in response.text


@pytest.mark.parametrize(
    "invalid", ["csrf", "origin", "tenant_parameter", "bad_format", "mapping", "path", "size"]
)
def test_http_upload_negative_boundaries_do_not_write(sbom_engine, sbom_api, invalid):
    login, _ = sbom_api
    client, headers, account = login()
    params, raw, expected = {}, raw_document(document()), 422
    if invalid == "csrf":
        headers = {**headers, "X-CSRF-Token": "invalid"}
        expected = 403
    elif invalid == "origin":
        headers = {**headers, "Origin": "https://unapproved.invalid"}
        expected = 403
    elif invalid == "tenant_parameter":
        params["tenant_id"] = "foreign"
    elif invalid == "bad_format":
        params["manifest_format"] = "auto"
    elif invalid == "mapping":
        params["csv_column_mapping"] = '{"package_name":"name"}'
    elif invalid == "path":
        raw = b"C:/private/manifest.json"
    else:
        raw = b"x" * 1048577
        expected = 413
    before = counts(sbom_engine, account.tenant_id)
    response = upload(client, headers, raw, **params)
    assert response.status_code == expected
    assert "C:/private" not in response.text
    assert counts(sbom_engine, account.tenant_id) == before
