"""最终冻结版本独立HTTP边界；原13条输入断言仍保留原字节。"""

import hashlib
from urllib.parse import quote

import pytest
import review_sbom_resource as resource
from pydantic import SecretStr
from sqlalchemy import select

from ai_intel.assets.inventory_models import asset_snapshots
from ai_intel.assets.sbom_inventory import safe_sbom_sidecar
from ai_intel.assets.sbom_inventory_contracts import AssetSnapshotSbomResponse
from ai_intel.assets.sbom_persistence_models import asset_snapshot_sbom_sidecars

sbom_engine = resource.sbom_engine
sbom_api = resource.sbom_api


@pytest.mark.parametrize("key", ["malformed%", "malformed%2", "malformed%GG", "%FF", "%C0%AF", "%ED%A0%80", "%00"])
def test_malformed_keys_have_bound_nonleaking_http_placeholders(
    sbom_engine, sbom_api, register_sensitive_failure_value, key
):
    register_sensitive_failure_value(SecretStr(key))
    login, _ = sbom_api
    client, headers, _ = login()
    value = resource.spdx_document()
    value[key] = "opaque"
    raw = resource.raw_document(value)
    created = resource.upload(client, headers, raw, manifest_format="spdx_json")
    assert created.status_code == 201
    snapshot_id = created.json()["snapshot"]["snapshot_id"]
    path = f"/api/assets/{created.json()['asset_id']}/snapshots/{snapshot_id}/sbom"
    response = client.get(path)
    assert response.status_code == 200
    payload = response.json()
    placeholders = [item for item in payload["unmapped_field_locators"] if "redacted-field:" in item]
    assert len(placeholders) == 1 and "/" + key not in payload["unmapped_field_locators"]
    assert any(item["source_field_locator"] == placeholders[0] and item["replacement_ref"] is None for item in payload["redactions"])
    assert payload["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert safe_sbom_sidecar(AssetSnapshotSbomResponse.model_validate(payload)).model_dump(mode="json") == payload
    with sbom_engine.connect() as connection:
        stored = connection.scalar(select(asset_snapshots.c.raw_input).where(asset_snapshots.c.snapshot_id == snapshot_id))
    assert bytes(stored) == raw
    assert client.get(path).json() == payload


def test_distinct_deep_keys_preserve_positions_and_ordinary_unicode(sbom_engine, sbom_api, register_sensitive_failure_value):
    private = "https://synthetic_user:synthetic_password@example.test/private"
    keys = []
    for depth in (0, 4, 5, 64):
        key = private
        for _ in range(depth):
            key = quote(key, safe="")
        keys.append(key)
        register_sensitive_failure_value(SecretStr(key))
    login, _ = sbom_api
    client, headers, _ = login()
    value = resource.spdx_document()
    value.update(dict.fromkeys(keys, "opaque"))
    value["公开字段"] = "ordinary"
    created = resource.upload(client, headers, resource.raw_document(value), manifest_format="spdx_json")
    assert created.status_code == 201
    snapshot_id = created.json()["snapshot"]["snapshot_id"]
    response = client.get(f"/api/assets/{created.json()['asset_id']}/snapshots/{snapshot_id}/sbom")
    assert response.status_code == 200
    payload = response.json()
    placeholders = [item for item in payload["unmapped_field_locators"] if "redacted-field:" in item]
    assert len(placeholders) == len(set(placeholders)) == 4
    assert "/公开字段" in payload["unmapped_field_locators"]
    assert all(key not in response.text for key in keys)
    assert safe_sbom_sidecar(AssetSnapshotSbomResponse.model_validate(payload)).model_dump(mode="json") == payload


def test_duplicate_graph_and_none_marker_remain_bound_without_parser_reentry(sbom_engine, sbom_api, monkeypatch, register_sensitive_failure_value):
    private = "file:///C:/private/synthetic-parent"
    register_sensitive_failure_value(SecretStr(private))
    login, _ = sbom_api
    client, headers, _ = login()
    value = {
        "bomFormat": "CycloneDX", "specVersion": "1.7",
        "components": [{"type": "library", "name": "a", "bom-ref": private}, {"type": "library", "name": "b", "bom-ref": "b"}, {"type": "library", "name": "c", "bom-ref": "c"}],
        "dependencies": [{"ref": private, "dependsOn": ["b", "c"]}],
    }
    created = resource.upload(client, headers, resource.raw_document(value))
    assert created.status_code == 201
    snapshot_id = created.json()["snapshot"]["snapshot_id"]
    path = f"/api/assets/{created.json()['asset_id']}/snapshots/{snapshot_id}/sbom"
    with sbom_engine.connect() as connection:
        before = dict(connection.execute(select(asset_snapshot_sbom_sidecars).where(asset_snapshot_sbom_sidecars.c.snapshot_id == snapshot_id)).mappings().one())

    def unexpected_parse(*args, **kwargs):
        raise AssertionError("historical read must use frozen payload")

    monkeypatch.setattr("ai_intel.assets.sbom_inventory.parse_sbom", unexpected_parse)
    response = client.get(path)
    assert response.status_code == 200
    payload = response.json()
    edges = payload["dependency_edges"]
    assert len(edges) == 2 and edges[0]["source_ref"] == edges[1]["source_ref"]
    assert edges[0]["target_ref"] != edges[1]["target_ref"]
    alias = "redacted-ref:" + hashlib.sha256(private.encode()).hexdigest()
    assert edges[0]["source_ref"] == alias
    assert safe_sbom_sidecar(AssetSnapshotSbomResponse.model_validate(payload)).model_dump(mode="json") == payload
    with sbom_engine.connect() as connection:
        after = dict(connection.execute(select(asset_snapshot_sbom_sidecars).where(asset_snapshot_sbom_sidecars.c.snapshot_id == snapshot_id)).mappings().one())
    assert before == after
