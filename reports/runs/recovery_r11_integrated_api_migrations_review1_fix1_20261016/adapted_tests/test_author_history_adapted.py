"""默认API的合成历史事故验证；不主张客户端可任意写PostgreSQL。"""

import copy
import hashlib
import logging
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select
from test_original_default_api import (
    api as api,
)
from test_original_default_api import (
    default_engine as default_engine,
)
from test_original_default_api import (
    document,
    path,
    raw_document,
    row_counts,
    upload,
)

from ai_intel.api.app import create_application
from ai_intel.assets.inventory_models import asset_snapshots
from ai_intel.assets.sbom_persistence_models import asset_snapshot_sbom_sidecars


def history_rows(engine, created):
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
                    asset_snapshot_sbom_sidecars.c.snapshot_id == snapshot["snapshot_id"]
                )
            )
            .mappings()
            .one()
        )
    snapshot, sidecar = copy.deepcopy(snapshot), copy.deepcopy(sidecar)
    identity = str(uuid4())
    snapshot.update(
        snapshot_id=identity, snapshot_number=2, previous_snapshot_id=snapshot["snapshot_id"]
    )
    snapshot["canonical_payload"].update(snapshot_id=identity, snapshot_number=2)
    sidecar["snapshot_id"] = identity
    sidecar["canonical_payload"]["snapshot_id"] = identity
    return snapshot, sidecar


def save_history(engine, snapshot, sidecar):
    with engine.begin() as connection:
        connection.execute(insert(asset_snapshots).values(snapshot))
        connection.execute(insert(asset_snapshot_sbom_sidecars).values(sidecar))


@pytest.mark.parametrize(
    "key",
    [
        "../../private/sbom.json",
        "..\\..\\private\\sbom.json",
        "private/sbom.json",
        "%252E%252E%252Fprivate",
    ],
)
@pytest.mark.parametrize("historical", [False, True])
def test_new_and_schema1_history_paths_keep_hashes_scope_and_restart(
    default_engine, api, key, historical, caplog
):
    caplog.set_level(logging.DEBUG)
    login, settings, _ = api
    client, headers, account = login()
    value = document()
    value["components"][0][key] = "synthetic-opaque"
    raw = raw_document(value)
    result = upload(client, headers, raw)
    assert result.status_code == 201
    created = result.json()
    route = path(created)
    if historical:
        snapshot, sidecar = history_rows(default_engine, created)
        source = "/components/0/" + key.replace("~", "~0").replace("/", "~1")
        sidecar["canonical_payload"].update(
            schema_version="r11-sbom-sidecar-1", unmapped_field_locators=[source], redactions=[]
        )
        save_history(default_engine, snapshot, sidecar)
        route = f"/v1/assets/{created['asset_id']}/snapshots/{snapshot['snapshot_id']}/sbom"
    response = client.get(route)
    assert response.status_code == 200
    body = response.json()
    expected = "/components/0/redacted-field:" + hashlib.sha256(key.encode()).hexdigest()
    assert expected in body["unmapped_field_locators"]
    assert any(
        marker["source_field_locator"] == expected and marker["replacement_ref"] is None
        for marker in body["redactions"]
    )
    assert "private" not in response.text and "sbom.json" not in response.text
    with default_engine.connect() as connection:
        saved = (
            connection.execute(
                select(asset_snapshots).where(asset_snapshots.c.snapshot_id == body["snapshot_id"])
            )
            .mappings()
            .one()
        )
        frozen = connection.execute(
            select(asset_snapshot_sbom_sidecars.c.canonical_payload).where(
                asset_snapshot_sbom_sidecars.c.snapshot_id == body["snapshot_id"]
            )
        ).scalar_one()
    assert bytes(saved["raw_input"]) == raw
    assert saved["raw_input_sha256"] == hashlib.sha256(raw).hexdigest() == body["raw_sha256"]
    assert frozen["schema_version"] == (
        "r11-sbom-sidecar-1" if historical else "r11-sbom-sidecar-2"
    )
    assert body["projection_sha256"] == created["snapshot"]["snapshot_sha256"]
    replay = upload(client, headers, raw)
    assert replay.status_code == 201 and replay.json()["reused"]
    foreign, _, _ = login()
    assert foreign.get(route).status_code == 404
    assert row_counts(default_engine, account.tenant_id) == (
        1,
        2 if historical else 1,
        2 if historical else 1,
    )
    default_engine.dispose()
    with TestClient(create_application(settings=settings)) as reopened:
        reopened.cookies.update(client.cookies)
        assert reopened.get(route).json() == body
    assert key not in caplog.text and "synthetic-opaque" not in caplog.text


@pytest.mark.parametrize(
    "tail",
    [
        "..~1private",
        "..\\private",
        "postgresql:~1~1synthetic_user:synthetic_password@db.internal~1private",
        "%00",
        "%FF",
    ],
)
@pytest.mark.parametrize("placeholder_first", [True, False])
def test_bad_schema2_history_fails_closed_without_state_changes(
    default_engine, api, tail, placeholder_first, caplog
):
    caplog.set_level(logging.DEBUG)
    login, settings, _ = api
    client, headers, account = login()
    created = upload(client, headers).json()
    snapshot, sidecar = history_rows(default_engine, created)
    fields = ["redacted-field:" + "a" * 64, tail]
    if not placeholder_first:
        fields.reverse()
    locator = "/" + "/".join(fields)
    sidecar["canonical_payload"].update(
        unmapped_field_locators=[locator],
        redactions=[
            {
                "source_field_locator": locator,
                "reason": "unsafe_uri_or_path",
                "replacement_ref": None,
            }
        ],
    )
    save_history(default_engine, snapshot, sidecar)
    before = row_counts(default_engine, account.tenant_id)
    route = f"/v1/assets/{created['asset_id']}/snapshots/{snapshot['snapshot_id']}/sbom"
    for _ in range(2):
        response = client.get(route)
        assert response.status_code == 503
        assert (
            "private" not in response.text
            and "synthetic_password" not in response.text
            and locator not in response.text
        )
    assert client.get(path(created)).status_code == 200
    assert (
        client.get("/v1/assets/" + created["asset_id"]).json()["current_snapshot_id"]
        == created["snapshot"]["snapshot_id"]
    )
    assert row_counts(default_engine, account.tenant_id) == before
    foreign, _, _ = login()
    assert foreign.get(route).status_code == 404
    default_engine.dispose()
    with TestClient(create_application(settings=settings)) as reopened:
        reopened.cookies.update(client.cookies)
        assert reopened.get(route).status_code == 503
    with default_engine.connect() as connection:
        saved = connection.execute(
            select(asset_snapshot_sbom_sidecars.c.canonical_payload).where(
                asset_snapshot_sbom_sidecars.c.snapshot_id == snapshot["snapshot_id"]
            )
        ).scalar_one()
    assert saved == sidecar["canonical_payload"]
    assert "synthetic_password" not in caplog.text and locator not in caplog.text
