"""Immutable SBOM sidecars bind to private PG snapshots; raw input stays in the snapshot."""

from sqlalchemy import (
    DDL,
    CheckConstraint,
    Column,
    ForeignKeyConstraint,
    Table,
    Text,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB

from ai_intel.assets.inventory_models import asset_snapshots

asset_snapshot_sbom_sidecars = Table(
    "asset_snapshot_sbom_sidecars",
    asset_snapshots.metadata,
    Column("snapshot_id", Text, primary_key=True),
    Column("asset_id", Text, nullable=False),
    Column("tenant_id", Text, nullable=False),
    Column("adapter_version", Text, nullable=False),
    Column("spec_version", Text, nullable=False),
    Column("sidecar_sha256", Text, nullable=False),
    Column("combined_semantic_sha256", Text, nullable=False),
    Column("canonical_payload", JSONB, nullable=False),
    ForeignKeyConstraint(
        ["asset_id", "tenant_id", "snapshot_id"],
        ["asset_snapshots.asset_id", "asset_snapshots.tenant_id", "asset_snapshots.snapshot_id"],
        name="fk_sbom_sidecar_snapshot_tenant",
    ),
    CheckConstraint("length(tenant_id) BETWEEN 1 AND 200", name="ck_sbom_sidecar_tenant"),
    CheckConstraint("length(adapter_version) BETWEEN 1 AND 200", name="ck_sbom_adapter_version"),
    CheckConstraint("length(spec_version) BETWEEN 1 AND 200", name="ck_sbom_spec_version"),
    CheckConstraint("sidecar_sha256 ~ '^[0-9a-f]{64}$'", name="ck_sbom_sidecar_sha256"),
    CheckConstraint("combined_semantic_sha256 ~ '^[0-9a-f]{64}$'", name="ck_sbom_combined_sha256"),
    CheckConstraint("jsonb_typeof(canonical_payload) = 'object'", name="ck_sbom_sidecar_payload"),
)

SIDECAR_IMMUTABILITY_SQL = """
CREATE OR REPLACE FUNCTION prevent_sbom_sidecar_changes() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
RAISE EXCEPTION 'SBOM sidecars are immutable' USING ERRCODE = '23514';
END $$;
CREATE TRIGGER asset_snapshot_sbom_sidecars_immutable BEFORE UPDATE OR DELETE
ON asset_snapshot_sbom_sidecars FOR EACH ROW EXECUTE FUNCTION prevent_sbom_sidecar_changes();
"""
event.listen(asset_snapshot_sbom_sidecars, "after_create", DDL(SIDECAR_IMMUTABILITY_SQL))
