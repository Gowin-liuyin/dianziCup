"""只在独占PG库建立损坏合成记录，隔离验证冻结摘要和shape检查。"""

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import insert, update

from ai_intel.assets.inventory_contracts import AssetSnapshotResponse
from ai_intel.assets.inventory_models import asset_snapshots, assets
from ai_intel.assets.sbom_inventory import freeze_sbom_sidecar, parse_inventory_input
from ai_intel.assets.sbom_persistence_models import asset_snapshot_sbom_sidecars
from ai_intel.domain.access import AccessScope, Role

RUN = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "digest_resource", RUN / "resources/test_r11_sbom_inventory_postgres.py"
)
resource = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resource)
sbom_engine = resource.sbom_engine
sbom_api = resource.sbom_api


@pytest.mark.parametrize("corruption", ["shape", "sidecar_sha256", "combined_semantic_sha256"])
def test_real_sbom_identity_with_only_shape_or_digest_corruption_returns_503(
    sbom_engine, sbom_api, corruption
):
    login, _ = sbom_api
    client, _, account = login()
    asset_id = str(uuid4())
    scope = AccessScope.for_authenticated_user(
        account.user_id, account.tenant_id, Role.TENANT_ADMIN
    )
    raw = resource.raw_document(resource.document())
    parsed = parse_inventory_input(
        raw,
        manifest_format="cyclonedx_json",
        scope=scope,
        authorized_asset_tenant_id=account.tenant_id,
        asset_id=asset_id,
        snapshot_number=1,
        source_version="synthetic-review-corruption",
        observed_at=resource.NOW,
        recorded_at=resource.NOW,
    )
    snapshot = AssetSnapshotResponse.model_validate(parsed.manifest.snapshot)
    sidecar = freeze_sbom_sidecar(parsed.sbom)
    sidecar_row = {
        "snapshot_id": snapshot.snapshot_id,
        "asset_id": asset_id,
        "tenant_id": account.tenant_id,
        "adapter_version": sidecar.adapter_version,
        "spec_version": sidecar.spec_version,
        "sidecar_sha256": sidecar.sidecar_sha256,
        "combined_semantic_sha256": sidecar.combined_semantic_sha256,
        "canonical_payload": sidecar.model_dump(mode="json"),
    }
    if corruption == "shape":
        sidecar_row["canonical_payload"] = {"opaque": "synthetic-private-shape-marker"}
    else:
        sidecar_row[corruption] = "0" * 64
    with sbom_engine.begin() as connection:
        connection.execute(
            insert(assets).values(
                asset_id=asset_id,
                tenant_id=account.tenant_id,
                display_name="Synthetic corrupted fixture",
                created_at=resource.NOW,
                updated_at=resource.NOW,
            )
        )
        connection.execute(
            insert(asset_snapshots).values(
                snapshot_id=snapshot.snapshot_id,
                asset_id=asset_id,
                tenant_id=account.tenant_id,
                snapshot_number=1,
                manifest_sha256=snapshot.snapshot_sha256,
                raw_input_sha256=parsed.manifest.source_sha256,
                schema_version=snapshot.schema_version,
                parser_version=parsed.manifest.parser_version,
                source_kind=snapshot.source_kind,
                source_version="synthetic-review-corruption",
                canonical_payload=snapshot.model_dump(mode="json"),
                raw_input=raw,
                observed_at=resource.NOW,
                recorded_at=resource.NOW,
                actor_user_id=account.user_id,
            )
        )
        connection.execute(insert(asset_snapshot_sbom_sidecars).values(sidecar_row))
        connection.execute(
            update(assets)
            .where(assets.c.asset_id == asset_id)
            .values(current_snapshot_id=snapshot.snapshot_id)
        )
    response = client.get(f"/api/assets/{asset_id}/snapshots/{snapshot.snapshot_id}/sbom")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "inventory_unavailable"
    assert account.tenant_id not in response.text
    assert "synthetic-private" not in response.text
