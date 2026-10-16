"""独立审查探针只创建合成资产，复用授权资源与共享失败脱敏钩子。"""

import hashlib
import importlib.util
import json
import time
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_intel.assets.inventory import InventoryService
from ai_intel.assets.inventory_models import asset_import_receipts, asset_snapshots, assets
from ai_intel.assets.sbom_persistence_models import asset_snapshot_sbom_sidecars
from ai_intel.knowledge.models import scope_epochs

RUN = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "review_resource", RUN / "resources/test_r11_sbom_inventory_postgres.py"
)
resource = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resource)
sbom_engine = resource.sbom_engine
sbom_api = resource.sbom_api


def all_counts(engine, tenant):
    result = resource.counts(engine, tenant)
    with engine.connect() as connection:
        result["assets"] = connection.scalar(
            select(func.count()).select_from(assets).where(assets.c.tenant_id == tenant)
        )
        result["receipts"] = connection.scalar(
            select(func.count())
            .select_from(asset_import_receipts)
            .where(asset_import_receipts.c.tenant_id == tenant)
        )
        result["epoch"] = connection.scalar(
            select(scope_epochs.c.epoch).where(scope_epochs.c.scope_key == "tenant:" + tenant)
        )
    return result


@pytest.mark.parametrize("manifest_format", ["cyclonedx_json", "spdx_json"])
def test_raw_bytes_update_and_delete_are_rejected(sbom_engine, manifest_format):
    scope = resource.actor(sbom_engine)
    document = (
        resource.document() if manifest_format == "cyclonedx_json" else resource.spdx_document()
    )
    result = resource.save(sbom_engine, scope, document, manifest_format=manifest_format)
    for statement in (
        update(asset_snapshots)
        .where(asset_snapshots.c.snapshot_id == result.snapshot.snapshot_id)
        .values(raw_input=b"changed"),
        delete(asset_snapshots).where(asset_snapshots.c.snapshot_id == result.snapshot.snapshot_id),
    ):
        with pytest.raises(IntegrityError) as raised, sbom_engine.begin() as connection:
            connection.execute(statement)
        assert raised.value.orig.sqlstate == "23514"
    with sbom_engine.connect() as connection:
        raw, digest = connection.execute(
            select(asset_snapshots.c.raw_input, asset_snapshots.c.raw_input_sha256).where(
                asset_snapshots.c.snapshot_id == result.snapshot.snapshot_id
            )
        ).one()
    assert bytes(raw) == resource.raw_document(document)
    assert digest == hashlib.sha256(bytes(raw)).hexdigest()


@pytest.mark.parametrize(
    "field,value,state",
    [
        ("adapter_version", "", "23514"),
        ("spec_version", "", "23514"),
        ("adapter_version", "x" * 201, "23514"),
        ("spec_version", "x" * 201, "23514"),
        ("sidecar_sha256", "A" * 64, "23514"),
        ("combined_semantic_sha256", "a" * 63, "23514"),
        ("canonical_payload", [], "23514"),
        ("adapter_version", None, "23502"),
        ("snapshot_id", "unbound", "23503"),
        ("tenant_id", "foreign", "23503"),
    ],
)
def test_sidecar_physical_checks_and_fk_are_effective(sbom_engine, field, value, state):
    scope = resource.actor(sbom_engine)
    first = resource.save(sbom_engine, scope)
    unused = resource.save(
        sbom_engine,
        scope,
        {"format_version": 1, "components": []},
        manifest_format="json_manifest_v1",
    )
    table = asset_snapshot_sbom_sidecars
    with sbom_engine.connect() as connection:
        copied = dict(
            connection.execute(
                select(table).where(table.c.snapshot_id == first.snapshot.snapshot_id)
            )
            .mappings()
            .one()
        )
    copied.update(asset_id=unused.asset_id, snapshot_id=unused.snapshot.snapshot_id)
    copied[field] = value
    before = all_counts(sbom_engine, scope.tenant_id)
    with pytest.raises(IntegrityError) as raised, sbom_engine.begin() as connection:
        connection.execute(insert(table).values(copied))
    assert raised.value.orig.sqlstate == state
    assert all_counts(sbom_engine, scope.tenant_id) == before


def test_receipt_failure_rolls_back_every_publication_and_asset(sbom_engine):
    scope = resource.actor(sbom_engine)
    before = all_counts(sbom_engine, scope.tenant_id)

    def fail_receipt(connection, cursor, statement, parameters, context, many):
        if statement.startswith("INSERT INTO asset_import_receipts"):
            raise RuntimeError("synthetic final receipt failure")

    event.listen(sbom_engine, "before_cursor_execute", fail_receipt)
    try:
        with pytest.raises(RuntimeError, match="synthetic final receipt failure"):
            resource.save(sbom_engine, scope)
    finally:
        event.remove(sbom_engine, "before_cursor_execute", fail_receipt)
    assert all_counts(sbom_engine, scope.tenant_id) == before


def test_10000_components_use_constant_sql_count(sbom_engine):
    measurements = []
    for count in (1, 10000):
        scope = resource.actor(sbom_engine)
        value = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.7",
            "version": 1,
            "components": [
                {"type": "library", "name": f"p{i}", "version": "1", "purl": f"pkg:pypi/p{i}@1"}
                for i in range(count)
            ],
        }
        raw = resource.raw_document(value)
        assert len(raw) <= 1048576
        statements = []

        def observe(
            connection, cursor, statement, parameters, context, many, statements=statements
        ):
            statements.append(statement.split()[0])

        event.listen(sbom_engine, "before_cursor_execute", observe)
        started = time.perf_counter()
        try:
            imported = resource.save(sbom_engine, scope, raw)
            elapsed = time.perf_counter() - started
            with Session(sbom_engine) as session:
                sidecar = InventoryService(session, scope).get_snapshot_sbom(
                    imported.asset_id, imported.snapshot.snapshot_id
                )
        finally:
            event.remove(sbom_engine, "before_cursor_execute", observe)
        assert len(imported.snapshot.components) == len(sidecar.component_sources) == count
        measurements.append(
            {
                "components": count,
                "raw_bytes": len(raw),
                "write_seconds": elapsed,
                "write_and_sidecar_read_sql_count": len(statements),
                "verbs": statements,
            }
        )
    (RUN / "sql_capacity_measurements.json").write_text(
        json.dumps(measurements, indent=2), encoding="utf-8"
    )
    assert (
        measurements[0]["write_and_sidecar_read_sql_count"]
        == measurements[1]["write_and_sidecar_read_sql_count"]
    )


@pytest.mark.parametrize(
    "private_uri",
    [
        "postgresql://synthetic_user:synthetic_password@db.internal:5432/private",
        "file:///C:/private/synthetic-parent",
        "https://synthetic_user:synthetic_password@example.test/sbom",
    ],
)
def test_sidecar_http_does_not_expose_protected_uri_values(sbom_engine, sbom_api, private_uri):
    login, _ = sbom_api
    client, headers, _ = login()
    value = resource.spdx_document()
    value["externalDocumentRefs"][0]["spdxDocument"] = private_uri
    response = resource.upload(
        client, headers, resource.raw_document(value), manifest_format="spdx_json"
    )
    if response.status_code in {400, 422}:
        return
    assert response.status_code == 201
    snapshot = response.json()["snapshot"]["snapshot_id"]
    sidecar = client.get(f"/api/assets/{response.json()['asset_id']}/snapshots/{snapshot}/sbom")
    assert sidecar.status_code == 200
    assert private_uri not in sidecar.text


def test_opaque_internal_values_stay_private_and_digest_mismatch_is_503(sbom_engine, sbom_api):
    login, _ = sbom_api
    client, headers, account = login()
    value = resource.document()
    value["opaque"] = {
        "dsn": "postgresql://synthetic:synthetic@internal/private",
        "parent": "C:/private/synthetic",
    }
    imported = resource.upload(client, headers, resource.raw_document(value))
    assert imported.status_code == 201
    asset_id = imported.json()["asset_id"]
    snapshot_id = imported.json()["snapshot"]["snapshot_id"]
    url = f"/api/assets/{asset_id}/snapshots/{snapshot_id}/sbom"
    read = client.get(url)
    assert read.status_code == 200
    assert "postgresql://" not in read.text and "C:/private/" not in read.text
    with sbom_engine.connect() as connection:
        copied = dict(
            connection.execute(
                select(asset_snapshot_sbom_sidecars).where(
                    asset_snapshot_sbom_sidecars.c.snapshot_id
                    == imported.json()["snapshot"]["snapshot_id"]
                )
            )
            .mappings()
            .one()
        )
    other = resource.upload(
        client,
        {**headers, "Idempotency-Key": str(uuid4())},
        b'{"format_version":1,"components":[]}',
        manifest_format="json_manifest_v1",
    )
    copied.update(
        asset_id=other.json()["asset_id"],
        snapshot_id=other.json()["snapshot"]["snapshot_id"],
        combined_semantic_sha256="0" * 64,
    )
    with sbom_engine.begin() as connection:
        connection.execute(insert(asset_snapshot_sbom_sidecars).values(copied))
    response = client.get(
        f"/api/assets/{copied['asset_id']}/snapshots/{copied['snapshot_id']}/sbom"
    )
    assert response.status_code == 503
    assert "postgresql://" not in response.text and account.tenant_id not in response.text
