"""真实PG新导入/历史schema1均安全展示；原文、hash、幂等和冻结事实不被脱敏改写。"""

import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import insert, select
from review_sbom_resource import raw_document, spdx_document, upload
from review_sbom_resource import sbom_api as sbom_api
from review_sbom_resource import sbom_engine as sbom_engine

from ai_intel.assets.inventory_models import asset_snapshots
from ai_intel.assets.sbom_inventory import freeze_sbom_sidecar
from ai_intel.assets.sbom_inventory_contracts import AssetSnapshotSbomResponse
from ai_intel.assets.sbom_persistence_models import asset_snapshot_sbom_sidecars
from ai_intel.domain.access import Role


def legacy_freeze(parsed):
    payload = freeze_sbom_sidecar(parsed).model_dump()
    payload.update(
        schema_version="r11-sbom-sidecar-1",
        component_sources=parsed.component_sources,
        dependency_edges=parsed.dependency_edges,
        completeness_declarations=parsed.completeness_declarations,
        external_documents=parsed.external_documents,
        unmapped_field_locators=parsed.unmapped_field_locators,
        redactions=(),
    )
    return AssetSnapshotSbomResponse.model_validate(payload)


@pytest.mark.parametrize("legacy", [False, True], ids=["fresh2", "historic1"])
@pytest.mark.parametrize(
    "uri",
    [
        "postgresql://synthetic_user:synthetic_password@db.internal:5432/private",
        "file:///C:/private/synthetic-parent",
        "https://synthetic_user:synthetic_password@example.test/sbom",
        "https://example.test/sbom?token=synthetic_password",
        "http://127.0.0.1/sbom",
        "https://db.internal/sbom",
    ],
    ids=["connection", "file", "userinfo", "query", "private_ip", "internal_host"],
)
def test_uri_redacted_for_new_and_immutable_history(
    sbom_engine, sbom_api, monkeypatch, caplog, legacy, uri
):
    caplog.set_level("DEBUG")
    if legacy:
        monkeypatch.setattr("ai_intel.assets.inventory.freeze_sbom_sidecar", legacy_freeze)
    login, _ = sbom_api
    client, headers, account = login()
    value = spdx_document()
    value["externalDocumentRefs"][0]["spdxDocument"] = uri
    raw = raw_document(value)
    created = upload(client, headers, raw, manifest_format="spdx_json")
    assert created.status_code == 201
    identity, snapshot = created.json()["asset_id"], created.json()["snapshot"]["snapshot_id"]
    path = f"/api/assets/{identity}/snapshots/{snapshot}/sbom"
    with sbom_engine.connect() as connection:
        stored = dict(
            connection.execute(
                select(asset_snapshot_sbom_sidecars).where(
                    asset_snapshot_sbom_sidecars.c.snapshot_id == snapshot
                )
            )
            .mappings()
            .one()
        )
        input_row = connection.execute(
            select(asset_snapshots.c.raw_input, asset_snapshots.c.raw_input_sha256).where(
                asset_snapshots.c.snapshot_id == snapshot
            )
        ).one()
    read = client.get(path)
    assert read.status_code == 200
    public = read.json()
    assert public["schema_version"] == "r11-sbom-sidecar-2"
    assert public["external_documents"][0]["document_uri"] is None
    assert public["external_documents"][0]["checksum"]["checksum_value"] == "c" * 64
    assert public["external_documents"][0]["document_ref"] == "DocumentRef-external"
    assert public["sidecar_sha256"] == stored["sidecar_sha256"]
    assert public["combined_semantic_sha256"] == stored["combined_semantic_sha256"]
    assert uri not in read.text and "synthetic_password" not in read.text
    assert public["redactions"] == [
        {
            "source_field_locator": "/externalDocumentRefs/0/spdxDocument",
            "reason": "unsafe_uri_or_path",
            "replacement_ref": None,
        }
    ]
    assert bytes(input_row[0]) == raw and input_row[1] == hashlib.sha256(raw).hexdigest()
    assert upload(client, headers, raw, manifest_format="spdx_json").json()["reused"] is True
    same = upload(
        client,
        {**headers, "Idempotency-Key": str(uuid4())},
        raw,
        manifest_format="spdx_json",
        asset_id=identity,
    )
    assert same.status_code == 201 and same.json()["reused"] is True
    analyst, _, _ = login(Role.ANALYST, account.tenant_id)
    assert analyst.get(path).json() == public
    with sbom_engine.connect() as connection:
        after = dict(
            connection.execute(
                select(asset_snapshot_sbom_sidecars).where(
                    asset_snapshot_sbom_sidecars.c.snapshot_id == snapshot
                )
            )
            .mappings()
            .one()
        )
    assert stored == after
    assert uri not in caplog.text and "synthetic_password" not in caplog.text


@pytest.mark.parametrize("legacy", [False, True])
def test_encoded_purl_is_private_on_all_snapshot_routes(sbom_engine, sbom_api, monkeypatch, legacy):
    if legacy:
        monkeypatch.setattr("ai_intel.assets.inventory.freeze_sbom_sidecar", legacy_freeze)
    login, _ = sbom_api
    client, headers, _ = login()
    purl = "pkg:generic/a@https%3A%2F%2Fsynthetic_user%3Asynthetic_password%40example.test%2Fsbom"
    value = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "version": 1,
        "components": [{"type": "library", "name": "a", "purl": purl}],
    }
    raw = raw_document(value)
    created = upload(client, headers, raw)
    assert created.status_code == 201
    identity, snapshot = created.json()["asset_id"], created.json()["snapshot"]["snapshot_id"]
    paths = [
        f"/api/assets/{identity}",
        "/api/assets",
        f"/api/assets/{identity}/snapshots",
        f"/api/assets/{identity}/snapshots/{snapshot}",
        f"/api/assets/{identity}/snapshots/{snapshot}/sbom",
    ]
    assert created.json()["snapshot"]["components"][0]["purl"] is None
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200
        assert purl not in response.text and "synthetic_password" not in response.text
    replay = upload(client, headers, raw)
    assert replay.json()["snapshot"]["components"][0]["purl"] is None
    sidecar = client.get(paths[-1]).json()
    assert sidecar["redactions"] == [
        {
            "source_field_locator": "/components/0/purl",
            "reason": "unsafe_uri_or_path",
            "replacement_ref": None,
        }
    ]
    with sbom_engine.connect() as connection:
        stored = (
            connection.execute(
                select(asset_snapshots).where(asset_snapshots.c.snapshot_id == snapshot)
            )
            .mappings()
            .one()
        )
    assert stored["canonical_payload"]["components"][0]["purl"] == purl
    assert bytes(stored["raw_input"]) == raw
    assert stored["manifest_sha256"] == created.json()["snapshot"]["snapshot_sha256"]


@pytest.mark.parametrize("legacy", [False, True])
def test_uri_in_unmapped_key_has_safe_pointer_and_private_raw(
    sbom_engine, sbom_api, monkeypatch, legacy
):
    if legacy:
        monkeypatch.setattr("ai_intel.assets.inventory.freeze_sbom_sidecar", legacy_freeze)
    login, _ = sbom_api
    client, headers, _ = login()
    key = "postgresql://synthetic_user:synthetic_password@db.internal/private"
    value = spdx_document()
    value[key] = "synthetic opaque"
    created = upload(client, headers, raw_document(value), manifest_format="spdx_json")
    assert created.status_code == 201
    sidecar = client.get(
        f"/api/assets/{created.json()['asset_id']}/snapshots/{created.json()['snapshot']['snapshot_id']}/sbom"
    )
    assert sidecar.status_code == 200
    assert "synthetic_password" not in sidecar.text and "postgresql:" not in sidecar.text
    assert any("redacted-field:" in item for item in sidecar.json()["unmapped_field_locators"])
    assert all(
        "synthetic_password" not in item["source_field_locator"]
        for item in sidecar.json()["redactions"]
    )


@pytest.mark.parametrize("legacy", [False, True])
def test_http_reference_topology_keeps_aliases_distinct_and_history_replay(
    sbom_engine, sbom_api, monkeypatch, legacy
):
    if legacy:
        monkeypatch.setattr("ai_intel.assets.inventory.freeze_sbom_sidecar", legacy_freeze)
    login, _ = sbom_api
    client, headers, _ = login()
    private = "file:///C:/private/synthetic-parent"
    alias = "redacted-ref:" + hashlib.sha256(private.encode()).hexdigest()
    value = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "version": 1,
        "components": [
            {"type": "library", "name": "a", "bom-ref": private},
            {"type": "library", "name": "b", "bom-ref": alias},
            {"type": "library", "name": "c", "bom-ref": "public-ref"},
        ],
        "dependencies": [{"ref": private, "dependsOn": [alias, "public-ref"]}],
        "compositions": [
            {
                "aggregate": "unknown",
                "assemblies": [private, alias],
                "dependencies": [private],
                "vulnerabilities": [private],
            }
        ],
    }
    raw = raw_document(value)
    created = upload(client, headers, raw)
    assert created.status_code == 201
    identity = created.json()["asset_id"]
    snapshot_id = created.json()["snapshot"]["snapshot_id"]
    url = f"/api/assets/{identity}/snapshots/{snapshot_id}/sbom"
    first = client.get(url)
    second = client.get(url)
    assert first.status_code == second.status_code == 200 and first.json() == second.json()
    body = first.json()
    refs = [item["source_ref"] for item in body["component_sources"]]
    assert len(set(refs)) == 3 and refs[0] == alias and refs[1] != alias
    assert body["dependency_edges"][0]["source_ref"] == refs[0]
    assert body["dependency_edges"][0]["target_ref"] == refs[1]
    assert body["completeness_declarations"][0]["assemblies"] == refs[:2]
    assert private not in first.text
    assert upload(client, headers, raw).json()["reused"] is True


def test_purl_download_uri_qualifier_remains_explicitly_rejected(sbom_api):
    login, _ = sbom_api
    client, headers, _ = login()
    purl = (
        "pkg:generic/a?download_url=https%3A%2F%2F"
        "synthetic_user%3Asynthetic_password%40example.test"
    )
    value = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "components": [{"type": "library", "name": "a", "purl": purl}],
    }
    response = upload(client, headers, raw_document(value))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_purl_features"
    assert "synthetic_password" not in response.text


@pytest.mark.parametrize("spoof", ["wrong_alias", "wrong_locator", "legacy_metadata"])
def test_forged_stored_projection_metadata_is_not_trusted(sbom_engine, sbom_api, spoof):
    """仅新增合成非current历史来造坏投影，保留合法scope/hash绑定且不改immutable旧行。"""
    login, _ = sbom_api
    client, headers, _ = login()
    created = upload(client, headers)
    table = asset_snapshot_sbom_sidecars
    with sbom_engine.connect() as connection:
        payload = dict(
            connection.execute(
                select(table).where(
                    table.c.snapshot_id == created.json()["snapshot"]["snapshot_id"]
                )
            )
            .mappings()
            .one()
        )
        snapshot = dict(
            connection.execute(
                select(asset_snapshots).where(
                    asset_snapshots.c.snapshot_id == created.json()["snapshot"]["snapshot_id"]
                )
            )
            .mappings()
            .one()
        )
    previous = snapshot["snapshot_id"]
    snapshot.update(snapshot_id=str(uuid4()), snapshot_number=2, previous_snapshot_id=previous)
    snapshot["canonical_payload"].update(snapshot_id=snapshot["snapshot_id"], snapshot_number=2)
    payload["snapshot_id"] = snapshot["snapshot_id"]
    body = payload["canonical_payload"]
    body["snapshot_id"] = payload["snapshot_id"]
    body["component_sources"][0]["source_ref"] = "redacted-ref:" + "b" * 64
    body["schema_version"] = (
        "r11-sbom-sidecar-2" if spoof != "legacy_metadata" else "r11-sbom-sidecar-1"
    )
    body["redactions"] = [
        {
            "source_field_locator": "/wrong"
            if spoof == "wrong_locator"
            else "/components/0/bom-ref",
            "reason": "unsafe_uri_or_path",
            "replacement_ref": "redacted-ref:" + "a" * 64,
        }
    ]
    with sbom_engine.begin() as connection:
        connection.execute(insert(asset_snapshots).values(snapshot))
        connection.execute(insert(table).values(payload))
    response = client.get(
        f"/api/assets/{payload['asset_id']}/snapshots/{payload['snapshot_id']}/sbom"
    )
    assert response.status_code == 503
