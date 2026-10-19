"""Extra default-HTTP historical locator boundaries and safe positive cases."""

import copy
import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import insert, select
from test_original_default_api import api as api, default_engine as default_engine
from test_original_default_api import document, spdx_document, raw_document, upload, path

from ai_intel.assets.inventory_models import asset_snapshots
from ai_intel.assets.sbom_persistence_models import asset_snapshot_sbom_sidecars

pytestmark = pytest.mark.real_pg


def pointer(value):
    return value.replace("~", "~0").replace("/", "~1")


def saved_rows(engine, created):
    with engine.connect() as connection:
        snapshot = copy.deepcopy(dict(connection.execute(select(asset_snapshots).where(asset_snapshots.c.snapshot_id == created["snapshot"]["snapshot_id"])).mappings().one()))
        sidecar = copy.deepcopy(dict(connection.execute(select(asset_snapshot_sbom_sidecars).where(asset_snapshot_sbom_sidecars.c.snapshot_id == snapshot["snapshot_id"])).mappings().one()))
    identity = str(uuid4())
    snapshot.update(snapshot_id=identity, snapshot_number=2, previous_snapshot_id=snapshot["snapshot_id"])
    snapshot["canonical_payload"].update(snapshot_id=identity, snapshot_number=2)
    sidecar["snapshot_id"] = identity
    sidecar["canonical_payload"]["snapshot_id"] = identity
    return snapshot, sidecar


def save_rows(engine, snapshot, sidecar):
    with engine.begin() as connection:
        connection.execute(insert(asset_snapshots).values(snapshot))
        connection.execute(insert(asset_snapshot_sbom_sidecars).values(sidecar))


@pytest.mark.parametrize("field", ["component", "field_source", "checksum", "edge", "composition", "external_document", "external_checksum"])
@pytest.mark.parametrize("private", ["../private/sbom.json", "postgresql://synthetic_user:synthetic_password@db.internal/private"])
def test_each_typed_source_locator_fails_closed_in_actual_default_get(default_engine, api, field, private):
    login, _, _ = api
    client, headers, _ = login()
    format_name = "spdx_json" if field.startswith("external_") else "cyclonedx_json"
    value = spdx_document() if format_name == "spdx_json" else document()
    if format_name == "cyclonedx_json":
        value["dependencies"][0]["dependsOn"] = ["b"]
    result = upload(client, headers, raw_document(value), manifest_format=format_name)
    assert result.status_code == 201
    created = result.json()
    old = client.get(path(created))
    assert old.status_code == 200
    snapshot, sidecar = saved_rows(default_engine, created)
    payload = sidecar["canonical_payload"]
    locator = "/safe/" + pointer(private) + "/0/public"
    targets = {
        "component": lambda: payload["component_sources"][0],
        "field_source": lambda: payload["component_sources"][0]["field_sources"][0],
        "checksum": lambda: payload["component_sources"][0]["checksums"][0],
        "edge": lambda: payload["dependency_edges"][0],
        "composition": lambda: payload["completeness_declarations"][0],
        "external_document": lambda: payload["external_documents"][0],
        "external_checksum": lambda: payload["external_documents"][0]["checksum"],
    }
    targets[field]()["source_field_locator"] = locator
    save_rows(default_engine, snapshot, sidecar)
    route = f"/v1/assets/{created['asset_id']}/snapshots/{snapshot['snapshot_id']}/sbom"
    for _ in range(2):
        response = client.get(route)
        assert response.status_code == 503
        assert "private" not in response.text and "synthetic_password" not in response.text
    assert client.get(path(created)).json() == old.json()
    with default_engine.connect() as connection:
        assert connection.scalar(select(asset_snapshot_sbom_sidecars.c.canonical_payload).where(asset_snapshot_sbom_sidecars.c.snapshot_id == sidecar["snapshot_id"])) == payload


@pytest.mark.parametrize("kind", ["historic1", "frozen2"])
def test_repeated_placeholder_segments_keep_safe_parents_and_hashes(default_engine, api, kind):
    login, _, _ = api
    client, headers, _ = login()
    result = upload(client, headers)
    assert result.status_code == 201
    created = result.json()
    snapshot, sidecar = saved_rows(default_engine, created)
    first = "../private/sbom.json"
    second = "file:///C:/private/history"
    safe = "/public/redacted-field:" + hashlib.sha256(first.encode()).hexdigest() + "/0/redacted-field:" + hashlib.sha256(second.encode()).hexdigest() + "/公开字段"
    body = sidecar["canonical_payload"]
    body.update(unmapped_field_locators=["/public/" + pointer(first) + "/0/" + pointer(second) + "/公开字段"] if kind == "historic1" else [safe],
                schema_version="r11-sbom-sidecar-1" if kind == "historic1" else "r11-sbom-sidecar-2",
                redactions=[] if kind == "historic1" else [{"source_field_locator": safe, "reason": "unsafe_uri_or_path", "replacement_ref": None}])
    save_rows(default_engine, snapshot, sidecar)
    route = f"/v1/assets/{created['asset_id']}/snapshots/{snapshot['snapshot_id']}/sbom"
    read = client.get(route)
    assert read.status_code == 200
    assert read.json()["unmapped_field_locators"] == [safe]
    assert read.json()["redactions"] == [{"source_field_locator": safe, "reason": "unsafe_uri_or_path", "replacement_ref": None}]
    assert client.get(route).json() == read.json()
    assert read.json()["raw_sha256"] == snapshot["raw_input_sha256"]
    assert read.json()["combined_semantic_sha256"] == sidecar["combined_semantic_sha256"]


@pytest.mark.parametrize("key", ["pkg:npm/public/pkg@1.0", "pkg:pypi/a@1.0", "普通字段", "a~b", "0"])
def test_safe_purl_and_unicode_raw_keys_remain_visible(default_engine, api, key):
    login, _, _ = api
    client, headers, _ = login()
    value = document()
    value[key] = "synthetic opaque"
    raw = raw_document(value)
    result = upload(client, headers, raw)
    assert result.status_code == 201
    read = client.get(path(result.json()))
    assert read.status_code == 200
    assert "/" + pointer(key) in read.json()["unmapped_field_locators"]
    assert read.json()["raw_sha256"] == hashlib.sha256(raw).hexdigest()
