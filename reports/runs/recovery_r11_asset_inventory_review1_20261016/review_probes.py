"""Independent synthetic inputs test public behavior and real PG transaction edges."""

import hashlib
import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
from ai_intel.api.auth_state import auth_sessions
from ai_intel.assets.inventory import InventoryService
from ai_intel.assets.inventory_models import asset_import_receipts, asset_snapshots
from ai_intel.knowledge.models import scope_epochs
from ai_intel.knowledge.persistence_models import publication_receipts
from sqlalchemy import event, func, select, update
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "frozen_inventory_tests",
    ROOT / "backend/tests/integration/test_t24_asset_inventory.py",
)
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)
inventory_engine = original.inventory_engine
inventory_api = original.inventory_api
scope = original.scope
save = original.save
manifest = original.manifest
counts = original.counts
snapshot_request = original.snapshot_request


@pytest.fixture
def register_sensitive_failure_value():
    """No private fixture object is printed or recorded by this review probe."""
    return lambda value: None


def extra_counts(engine, tenant):
    with engine.connect() as connection:
        return {
            **counts(engine, tenant),
            "epoch": connection.scalar(
                select(scope_epochs.c.epoch).where(
                    scope_epochs.c.scope_key == "tenant:" + tenant
                )
            ),
            "publications": connection.scalar(
                select(func.count())
                .select_from(publication_receipts)
                .where(publication_receipts.c.scope_key == "tenant:" + tenant)
            ),
        }


def test_exact_one_mib_binary_upload_then_one_byte_rejection(
    inventory_engine, inventory_api
):
    login, _ = inventory_api
    client, headers, account = login()
    raw = manifest()
    raw += b" " * (1048576 - len(raw))
    params = {
        "display_name": "Synthetic boundary",
        "source_version": "probe-one-mib",
        "observed_at": original.OBSERVED.isoformat(),
        "manifest_format": "json_manifest_v1",
    }
    accepted = client.post(
        "/api/asset-imports", content=raw, params=params, headers=headers
    )
    assert accepted.status_code == 201
    before = extra_counts(inventory_engine, account.tenant_id)
    rejected = client.post(
        "/api/asset-imports",
        content=raw + b" ",
        params=params,
        headers={**headers, "Idempotency-Key": str(uuid4())},
    )
    assert rejected.status_code == 413
    assert extra_counts(inventory_engine, account.tenant_id) == before
    identity = accepted.json()["snapshot"]["snapshot_id"]
    with inventory_engine.connect() as connection:
        row = connection.execute(
            select(
                asset_snapshots.c.raw_input, asset_snapshots.c.raw_input_sha256
            ).where(asset_snapshots.c.snapshot_id == identity)
        ).one()
        assert len(row.raw_input) == 1048576
        assert row.raw_input_sha256 == hashlib.sha256(raw).hexdigest()


def test_failure_after_all_publication_writes_rolls_back_epoch_outbox_receipt(
    inventory_engine, monkeypatch
):
    from ai_intel.assets import inventory

    access = scope(inventory_engine)
    first = save(inventory_engine, access)
    before = extra_counts(inventory_engine, access.tenant_id)
    publish = inventory.save_change_publication

    def publish_then_fail(*args, **kwargs):
        publish(*args, **kwargs)
        raise RuntimeError("synthetic-after-outbox-failure")

    monkeypatch.setattr(inventory, "save_change_publication", publish_then_fail)
    with pytest.raises(RuntimeError, match="synthetic-after-outbox-failure"):
        save(inventory_engine, access, manifest("2.0"), asset_id=first.asset_id)
    assert extra_counts(inventory_engine, access.tenant_id) == before
    with Session(inventory_engine) as session:
        assert (
            InventoryService(session, access)
            .read_asset(first.asset_id)
            .current_snapshot_id
            == first.snapshot.snapshot_id
        )


def test_service_has_no_internal_commit_after_successful_import(inventory_engine):
    access = scope(inventory_engine)
    before = extra_counts(inventory_engine, access.tenant_id)
    with Session(inventory_engine) as session:
        saved = InventoryService(session, access).import_manifest(
            manifest(),
            manifest_format="json_manifest_v1",
            display_name="Synthetic rollback",
            source_version="probe-rollback",
            observed_at=original.OBSERVED,
            idempotency_key=str(uuid4()),
        )
        assert saved.snapshot.snapshot_number == 1
        session.rollback()
    assert extra_counts(inventory_engine, access.tenant_id) == before


def test_principal_route_receipts_same_current_do_not_duplicate_publication(
    inventory_engine,
):
    owner = scope(inventory_engine)
    other = scope(inventory_engine, tenant=owner.tenant_id)
    first = save(inventory_engine, owner)
    before = extra_counts(inventory_engine, owner.tenant_id)
    for access in (owner, other):
        for route in ("asset-imports", "asset-snapshots"):
            result = save(
                inventory_engine,
                access,
                key="same-independent-key",
                asset_id=first.asset_id,
                request_route=route,
            )
            assert (
                result.reused
                and result.snapshot.snapshot_id == first.snapshot.snapshot_id
            )
    after = extra_counts(inventory_engine, owner.tenant_id)
    assert after == {**before, "receipts": before["receipts"] + 4}
    with inventory_engine.connect() as connection:
        rows = connection.execute(
            select(
                asset_import_receipts.c.actor_user_id,
                asset_import_receipts.c.request_route,
            )
            .where(asset_import_receipts.c.tenant_id == owner.tenant_id)
            .where(asset_import_receipts.c.idempotency_key == "same-independent-key")
        ).all()
        assert len(set(rows)) == 4


def test_revoke_after_auth_lock_waits_for_commit_and_next_request_denied(
    inventory_engine, inventory_api, monkeypatch
):
    login, _ = inventory_api
    client, headers, account = login()
    entered, release, revoke_started = Event(), Event(), Event()
    import_manifest = InventoryService.import_manifest

    def paused(self, *args, **kwargs):
        entered.set()
        assert release.wait(5)
        return import_manifest(self, *args, **kwargs)

    def revoke():
        revoke_started.set()
        with inventory_engine.begin() as connection:
            connection.execute(
                update(auth_sessions)
                .where(auth_sessions.c.user_id == account.user_id)
                .values(revoked_at=datetime.now(UTC))
            )

    monkeypatch.setattr(InventoryService, "import_manifest", paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        request = pool.submit(
            client.post,
            "/api/asset-snapshots",
            json=snapshot_request(),
            headers=headers,
        )
        assert entered.wait(5)
        revoked = pool.submit(revoke)
        assert revoke_started.wait(5)
        assert not revoked.done()
        release.set()
        assert request.result(5).status_code == 201
        revoked.result(5)
    assert client.get("/api/assets").status_code == 401
    assert (
        client.post(
            "/api/asset-snapshots", json=snapshot_request(), headers=headers
        ).status_code
        == 401
    )
    assert counts(inventory_engine, account.tenant_id)["assets"] == 1


def test_actual_http_lock_order_contains_auth_asset_publication_epoch(
    inventory_engine, inventory_api
):
    login, _ = inventory_api
    client, headers, _ = login()
    first = client.post(
        "/api/asset-snapshots", json=snapshot_request(), headers=headers
    )
    trace = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        if "FOR SHARE" in statement and "auth_sessions" in statement:
            trace.append("auth-share")
        if "pg_advisory_xact_lock" in statement:
            values = " ".join(str(value) for value in parameters.values())
            if "asset-inventory-tenant:" in values:
                trace.append("tenant-advisory")
            elif "asset-inventory:" in values:
                trace.append("asset-advisory")
            elif "knowledge-publication:" in values:
                trace.append("publication-advisory")
        if "FROM assets" in statement and "FOR UPDATE" in statement:
            trace.append("asset-row")
        if "scope_epochs" in statement and (
            "INSERT" in statement or "UPDATE" in statement
        ):
            trace.append("epoch-write")

    event.listen(inventory_engine, "before_cursor_execute", observe)
    try:
        response = client.post(
            "/api/asset-snapshots",
            json=snapshot_request(
                asset_id=first.json()["asset_id"], snapshot=json.loads(manifest("2.0"))
            ),
            headers={**headers, "Idempotency-Key": str(uuid4())},
        )
    finally:
        event.remove(inventory_engine, "before_cursor_execute", observe)
    assert response.status_code == 201
    expected = [
        "auth-share",
        "tenant-advisory",
        "asset-advisory",
        "asset-row",
        "publication-advisory",
        "epoch-write",
    ]
    assert [trace.index(label) for label in expected] == sorted(
        trace.index(label) for label in expected
    )


def test_product_filter_uses_current_and_not_historical_component(inventory_engine):
    access = scope(inventory_engine)
    first = save(inventory_engine, access)
    replacement = json.dumps(
        {
            "format_version": 1,
            "components": [
                {"ecosystem": "pypi", "package_name": "llama-index", "version": "2.0"}
            ],
        }
    ).encode()
    save(inventory_engine, access, replacement, asset_id=first.asset_id)
    with Session(inventory_engine) as session:
        reader = InventoryService(session, access)
        assert reader.list_assets(product="langchain").items == ()
        assert [
            asset.asset_id for asset in reader.list_assets(product="llama-index").items
        ] == [first.asset_id]
        assert (
            reader.get_snapshot(first.asset_id, first.snapshot.snapshot_id)
            .components[0]
            .package_name
            == "langchain"
        )


def test_zero_components_unknown_is_kept_and_has_no_safe_claim(
    inventory_engine, inventory_api
):
    login, _ = inventory_api
    client, headers, _ = login()
    response = client.post(
        "/api/asset-snapshots",
        headers=headers,
        json=snapshot_request(
            snapshot={
                "format_version": 1,
                "components": [],
                "inventory_completeness": "unknown",
            }
        ),
    )
    assert response.status_code == 201
    snapshot = response.json()["snapshot"]
    assert (
        snapshot["inventory_completeness"] == "unknown" and snapshot["components"] == []
    )
    assert snapshot["tool_permissions"] is None and snapshot["input_channels"] is None
    assert snapshot["network_exposure"] is None
    assert not {"safe", "assessment_status", "excluded_with_evidence"}.intersection(
        snapshot
    )
