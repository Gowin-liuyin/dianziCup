"""独立隐私、冲突标记与历史上下文探针，不修改被审业务或原断言。"""

import copy
import hashlib
from urllib.parse import quote
from uuid import uuid4

import pytest
import review_sbom_resource as resource
from pydantic import SecretStr
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from ai_intel.assets.inventory_models import asset_snapshots
from ai_intel.assets.sbom_inventory import freeze_sbom_sidecar, safe_sbom_sidecar
from ai_intel.assets.sbom_inventory_contracts import AssetSnapshotSbomResponse
from ai_intel.assets.sbom_persistence_models import asset_snapshot_sbom_sidecars
from ai_intel.domain.access import Role
from ai_intel.knowledge.models import users

sbom_engine = resource.sbom_engine
sbom_api = resource.sbom_api


def legacy_freeze(parsed):
    view = freeze_sbom_sidecar(parsed).model_dump()
    view.update(
        schema_version="r11-sbom-sidecar-1",
        component_sources=parsed.component_sources,
        dependency_edges=parsed.dependency_edges,
        completeness_declarations=parsed.completeness_declarations,
        external_documents=parsed.external_documents,
        unmapped_field_locators=parsed.unmapped_field_locators,
        redactions=(),
    )
    return AssetSnapshotSbomResponse.model_validate(view)


@pytest.mark.parametrize("encoding_depth", [1, 4, 5, 8])
def test_encoded_uri_pointer_is_never_disclosed(
    sbom_engine, sbom_api, register_sensitive_failure_value, encoding_depth
):
    private = "postgresql://synthetic_user:synthetic_password@db.internal/private"
    key = private
    for _ in range(encoding_depth):
        key = quote(key, safe="")
    register_sensitive_failure_value(SecretStr(key))
    register_sensitive_failure_value(SecretStr(private))
    login, _ = sbom_api
    client, headers, _ = login()
    document = resource.spdx_document()
    document[key] = "synthetic opaque"
    raw = resource.raw_document(document)
    created = resource.upload(client, headers, raw, manifest_format="spdx_json")
    assert created.status_code == 201
    asset_id = created.json()["asset_id"]
    snapshot_id = created.json()["snapshot"]["snapshot_id"]
    response = client.get(f"/api/assets/{asset_id}/snapshots/{snapshot_id}/sbom")
    assert response.status_code == 200
    assert key not in response.text
    assert "synthetic_password" not in response.text
    assert any("redacted-field:" in field for field in response.json()["unmapped_field_locators"])
    with sbom_engine.connect() as connection:
        saved = connection.execute(
            select(asset_snapshots.c.raw_input).where(asset_snapshots.c.snapshot_id == snapshot_id)
        ).scalar_one()
    assert bytes(saved) == raw


def cloned_history(engine, created):
    with engine.connect() as connection:
        snapshot = dict(
            connection.execute(
                select(asset_snapshots).where(
                    asset_snapshots.c.snapshot_id == created["snapshot"]["snapshot_id"]
                )
            )
            .mappings()
            .one()
        )
        sidecar = dict(
            connection.execute(
                select(asset_snapshot_sbom_sidecars).where(
                    asset_snapshot_sbom_sidecars.c.snapshot_id == created["snapshot"]["snapshot_id"]
                )
            )
            .mappings()
            .one()
        )
    snapshot, sidecar = copy.deepcopy(snapshot), copy.deepcopy(sidecar)
    previous = snapshot["snapshot_id"]
    identity = str(uuid4())
    snapshot.update(snapshot_id=identity, snapshot_number=2, previous_snapshot_id=previous)
    snapshot["canonical_payload"].update(snapshot_id=identity, snapshot_number=2)
    sidecar["snapshot_id"] = identity
    sidecar["canonical_payload"]["snapshot_id"] = identity
    return snapshot, sidecar


@pytest.mark.parametrize(
    "corruption", ["reused_locator_conflict", "extra", "no_marker", "duplicate"]
)
def test_conflicting_or_unbound_v2_metadata_is_503(
    sbom_engine, sbom_api, register_sensitive_failure_value, corruption
):
    private = "file:///C:/private/synthetic-parent"
    register_sensitive_failure_value(SecretStr(private))
    login, _ = sbom_api
    client, headers, account = login()
    value = resource.document()
    value["components"][0]["bom-ref"] = private
    value["dependencies"] = [{"ref": private, "dependsOn": ["b", private]}]
    value["compositions"][0]["assemblies"] = [private]
    created = resource.upload(client, headers, resource.raw_document(value))
    assert created.status_code == 201
    snapshot, sidecar = cloned_history(sbom_engine, created.json())
    body = sidecar["canonical_payload"]
    if corruption == "reused_locator_conflict":
        body["dependency_edges"][1]["source_ref"] = "public-ref"
    elif corruption == "extra":
        body["redactions"].append(
            {
                "source_field_locator": "/extra",
                "reason": "unsafe_uri_or_path",
                "replacement_ref": None,
            }
        )
    elif corruption == "no_marker":
        body["redactions"] = []
    else:
        body["redactions"].append(dict(body["redactions"][0]))
    with sbom_engine.begin() as connection:
        connection.execute(insert(asset_snapshots).values(snapshot))
        connection.execute(insert(asset_snapshot_sbom_sidecars).values(sidecar))
    response = client.get(
        f"/api/assets/{sidecar['asset_id']}/snapshots/{sidecar['snapshot_id']}/sbom"
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "inventory_unavailable"
    assert account.tenant_id not in response.text
    assert private not in response.text


@pytest.mark.parametrize("legacy", [False, True])
def test_encoded_purl_acl_history_and_current_state_are_preserved(
    sbom_engine, sbom_api, register_sensitive_failure_value, monkeypatch, legacy
):
    private_purl = (
        "pkg:generic/a@https%3A%2F%2Fsynthetic_user%3Asynthetic_password%40example.test%2Fsbom"
    )
    register_sensitive_failure_value(SecretStr(private_purl))
    if legacy:
        monkeypatch.setattr("ai_intel.assets.inventory.freeze_sbom_sidecar", legacy_freeze)
    login, _ = sbom_api
    client, headers, account = login()
    value = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "version": 1,
        "components": [{"type": "library", "name": "a", "purl": private_purl}],
    }
    raw = resource.raw_document(value)
    created = resource.upload(client, headers, raw)
    assert created.status_code == 201
    asset_id = created.json()["asset_id"]
    snapshot_id = created.json()["snapshot"]["snapshot_id"]
    analyst, _, _ = login(Role.ANALYST, account.tenant_id)
    foreign, _, _ = login()
    paths = [
        f"/api/assets/{asset_id}",
        f"/api/assets/{asset_id}/snapshots",
        f"/api/assets/{asset_id}/snapshots/{snapshot_id}",
        f"/api/assets/{asset_id}/snapshots/{snapshot_id}/sbom",
    ]
    for path in paths:
        assert analyst.get(path).status_code == 200
        assert private_purl not in analyst.get(path).text
        assert foreign.get(path).status_code == 404
    with sbom_engine.connect() as connection:
        frozen = dict(
            connection.execute(
                select(asset_snapshots).where(asset_snapshots.c.snapshot_id == snapshot_id)
            )
            .mappings()
            .one()
        )
    assert frozen["canonical_payload"]["components"][0]["purl"] == private_purl
    assert frozen["raw_input_sha256"] == hashlib.sha256(raw).hexdigest()
    with sbom_engine.begin() as connection:
        connection.execute(
            update(users).where(users.c.user_id == account.user_id).values(role=Role.VIEWER.value)
        )
    assert client.get(paths[-1]).status_code == 403
    assert resource.upload(client, headers, raw).status_code == 403


def test_purl_marker_without_context_and_double_projection_are_consistent(sbom_engine, sbom_api):
    login, _ = sbom_api
    client, headers, _ = login()
    value = resource.document()
    value["components"][0]["purl"] = (
        "pkg:generic/a@https%3A%2F%2Fsynthetic_user%3Asynthetic_password%40example.test%2Fsbom"
    )
    value["components"][0].pop("version")
    created = resource.upload(client, headers, resource.raw_document(value))
    assert created.status_code == 201
    with sbom_engine.connect() as connection:
        stored = dict(
            connection.execute(
                select(asset_snapshot_sbom_sidecars).where(
                    asset_snapshot_sbom_sidecars.c.snapshot_id
                    == created.json()["snapshot"]["snapshot_id"]
                )
            )
            .mappings()
            .one()
        )
    projection = AssetSnapshotSbomResponse.model_validate(stored["canonical_payload"])
    assert safe_sbom_sidecar(projection) == projection
    with Session(sbom_engine) as session:
        snapshot, sidecar = cloned_history(sbom_engine, created.json())
        body = snapshot["canonical_payload"]
        body["components"][0]["purl"] = "pkg:generic/a@1"
        with session.begin():
            session.execute(insert(asset_snapshots).values(snapshot))
            session.execute(insert(asset_snapshot_sbom_sidecars).values(sidecar))
    response = client.get(
        f"/api/assets/{sidecar['asset_id']}/snapshots/{sidecar['snapshot_id']}/sbom"
    )
    assert response.status_code == 503


@pytest.mark.parametrize("schema_version", ["r11-sbom-sidecar-1", "r11-sbom-sidecar-2"])
def test_null_external_document_without_redaction_binding_is_503(
    sbom_engine, sbom_api, schema_version
):
    login, _ = sbom_api
    client, headers, _ = login()
    created = resource.upload(
        client,
        headers,
        resource.raw_document(resource.spdx_document()),
        manifest_format="spdx_json",
    )
    assert created.status_code == 201
    snapshot, sidecar = cloned_history(sbom_engine, created.json())
    sidecar["canonical_payload"].update(schema_version=schema_version, redactions=[])
    sidecar["canonical_payload"]["external_documents"][0]["document_uri"] = None
    with sbom_engine.begin() as connection:
        connection.execute(insert(asset_snapshots).values(snapshot))
        connection.execute(insert(asset_snapshot_sbom_sidecars).values(sidecar))
    response = client.get(
        f"/api/assets/{sidecar['asset_id']}/snapshots/{sidecar['snapshot_id']}/sbom"
    )
    assert response.status_code == 503
