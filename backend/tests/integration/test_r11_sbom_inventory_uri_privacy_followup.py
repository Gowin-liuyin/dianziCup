"""同批复核遗漏的展示边界，真实PG不可变历史与原始输入不改写。"""

import hashlib
from urllib.parse import quote
from uuid import uuid4

import pytest
from sqlalchemy import insert, select
from tests.integration.test_r11_sbom_inventory_postgres import raw_document, spdx_document, upload
from tests.integration.test_r11_sbom_inventory_postgres import sbom_api as sbom_api
from tests.integration.test_r11_sbom_inventory_postgres import sbom_engine as sbom_engine
from tests.integration.test_r11_sbom_inventory_uri_privacy import legacy_freeze

from ai_intel.assets.inventory_models import asset_snapshots
from ai_intel.assets.sbom_persistence_models import asset_snapshot_sbom_sidecars
from ai_intel.domain.access import Role


@pytest.mark.parametrize("legacy", [False, True], ids=["fresh2", "historic1"])
@pytest.mark.parametrize("encoding", ["5", "8", "invalid_utf8"])
def test_deep_or_malformed_key_is_never_returned_from_immutable_history(
    sbom_engine, sbom_api, monkeypatch, caplog, legacy, encoding
):
    caplog.set_level("DEBUG")
    if legacy:
        monkeypatch.setattr("ai_intel.assets.inventory.freeze_sbom_sidecar", legacy_freeze)
    key = "https://synthetic_user:synthetic_password@example.test/sbom"
    if encoding == "invalid_utf8":
        key = "%FFsynthetic_password"
    else:
        for _ in range(int(encoding)):
            key = quote(key, safe="")
    login, _ = sbom_api
    client, headers, account = login()
    value = spdx_document()
    value[key] = "opaque"
    raw = raw_document(value)
    created = upload(client, headers, raw, manifest_format="spdx_json")
    assert created.status_code == 201
    identity, snapshot_id = created.json()["asset_id"], created.json()["snapshot"]["snapshot_id"]
    path = f"/api/assets/{identity}/snapshots/{snapshot_id}/sbom"
    with sbom_engine.connect() as connection:
        before = dict(
            connection.execute(
                select(asset_snapshot_sbom_sidecars).where(
                    asset_snapshot_sbom_sidecars.c.snapshot_id == snapshot_id
                )
            )
            .mappings()
            .one()
        )
        stored_raw = connection.scalar(
            select(asset_snapshots.c.raw_input).where(asset_snapshots.c.snapshot_id == snapshot_id)
        )
    response = client.get(path)
    assert response.status_code == 200
    body = response.json()
    assert key not in response.text and "synthetic_password" not in response.text
    assert any("redacted-field:" in item for item in body["unmapped_field_locators"])
    assert body["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert body["combined_semantic_sha256"] == before["combined_semantic_sha256"]
    assert body["sidecar_sha256"] == before["sidecar_sha256"]
    assert bytes(stored_raw) == raw
    assert client.get(path).json() == body
    analyst, _, _ = login(Role.ANALYST, account.tenant_id)
    assert analyst.get(path).json() == body
    assert upload(client, headers, raw, manifest_format="spdx_json").json()["reused"] is True
    with sbom_engine.connect() as connection:
        after = dict(
            connection.execute(
                select(asset_snapshot_sbom_sidecars).where(
                    asset_snapshot_sbom_sidecars.c.snapshot_id == snapshot_id
                )
            )
            .mappings()
            .one()
        )
    assert before == after
    assert key not in caplog.text and "synthetic_password" not in caplog.text


@pytest.mark.parametrize("replacement", ["safe-public-ref", "wrong_alias", "same_alias"])
def test_every_stored_repeated_ref_must_match_its_typed_replacement(
    sbom_engine, sbom_api, replacement
):
    """仅新建合成历史坏行；合法重复引用仍200，错值固定503且不回显私有值。"""
    login, _ = sbom_api
    client, headers, _ = login()
    private = "https://synthetic_user:synthetic_password@example.test/sbom"
    raw = raw_document(
        {
            "bomFormat": "CycloneDX",
            "specVersion": "1.7",
            "components": [
                {"type": "library", "name": "a", "bom-ref": private},
                {"type": "library", "name": "b", "bom-ref": "public-b"},
                {"type": "library", "name": "c", "bom-ref": "public-c"},
            ],
            "dependencies": [{"ref": private, "dependsOn": ["public-b", "public-c"]}],
        }
    )
    created = upload(client, headers, raw)
    assert created.status_code == 201
    table = asset_snapshot_sbom_sidecars
    with sbom_engine.connect() as connection:
        snapshot = dict(
            connection.execute(
                select(asset_snapshots).where(
                    asset_snapshots.c.snapshot_id == created.json()["snapshot"]["snapshot_id"]
                )
            )
            .mappings()
            .one()
        )
        sidecar = dict(
            connection.execute(select(table).where(table.c.snapshot_id == snapshot["snapshot_id"]))
            .mappings()
            .one()
        )
    snapshot.update(
        snapshot_id=str(uuid4()), snapshot_number=2, previous_snapshot_id=snapshot["snapshot_id"]
    )
    snapshot["canonical_payload"].update(snapshot_id=snapshot["snapshot_id"], snapshot_number=2)
    sidecar["snapshot_id"] = snapshot["snapshot_id"]
    body = sidecar["canonical_payload"]
    body["snapshot_id"] = sidecar["snapshot_id"]
    alias = body["dependency_edges"][0]["source_ref"]
    body["dependency_edges"][1]["source_ref"] = {
        "same_alias": alias,
        "wrong_alias": "redacted-ref:" + "f" * 64,
        "safe-public-ref": "safe-public-ref",
    }[replacement]
    with sbom_engine.begin() as connection:
        connection.execute(insert(asset_snapshots).values(snapshot))
        connection.execute(insert(table).values(sidecar))
    response = client.get(
        f"/api/assets/{sidecar['asset_id']}/snapshots/{sidecar['snapshot_id']}/sbom"
    )
    assert response.status_code == (200 if replacement == "same_alias" else 503)
    assert "synthetic_password" not in response.text
