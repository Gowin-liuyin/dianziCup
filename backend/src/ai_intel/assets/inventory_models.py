"""资产专用PG表提案；生产迁移由主控0018冻结，业务入口不自动建表。"""

from sqlalchemy import (
    DDL,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Table,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB

from ai_intel.knowledge.models import metadata

assets = Table(
    "assets",
    metadata,
    Column("asset_id", Text, primary_key=True),
    Column("tenant_id", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("criticality", Text, nullable=False, server_default="unknown"),
    Column("active", Boolean, nullable=False, server_default="true"),
    Column("current_snapshot_id", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("asset_id", "tenant_id", name="uq_asset_tenant_identity"),
    CheckConstraint("length(tenant_id) BETWEEN 1 AND 200", name="ck_asset_tenant"),
    CheckConstraint("length(display_name) BETWEEN 1 AND 200", name="ck_asset_display_name"),
    ForeignKeyConstraint(
        ["asset_id", "tenant_id", "current_snapshot_id"],
        ["asset_snapshots.asset_id", "asset_snapshots.tenant_id", "asset_snapshots.snapshot_id"],
        name="fk_asset_current_snapshot_tenant",
        deferrable=True,
        initially="DEFERRED",
        use_alter=True,
    ),
)
Index("ix_assets_tenant_created", assets.c.tenant_id, assets.c.created_at, assets.c.asset_id)

asset_snapshots = Table(
    "asset_snapshots",
    metadata,
    Column("snapshot_id", Text, primary_key=True),
    Column("asset_id", Text, nullable=False),
    Column("tenant_id", Text, nullable=False),
    Column("snapshot_number", Integer, nullable=False),
    Column("previous_snapshot_id", Text),
    Column("manifest_sha256", Text, nullable=False),
    Column("raw_input_sha256", Text, nullable=False),
    Column("schema_version", Text, nullable=False),
    Column("parser_version", Text, nullable=False),
    Column("source_kind", Text, nullable=False),
    Column("source_version", Text, nullable=False),
    Column("canonical_payload", JSONB, nullable=False),
    Column("raw_input", LargeBinary, nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    Column("actor_user_id", Text, ForeignKey("users.user_id"), nullable=False),
    UniqueConstraint("asset_id", "tenant_id", "snapshot_id", name="uq_snapshot_tenant_identity"),
    UniqueConstraint("asset_id", "tenant_id", "snapshot_number", name="uq_asset_snapshot_number"),
    ForeignKeyConstraint(
        ["asset_id", "tenant_id"],
        ["assets.asset_id", "assets.tenant_id"],
        name="fk_snapshot_asset_tenant",
    ),
    ForeignKeyConstraint(
        ["asset_id", "tenant_id", "previous_snapshot_id"],
        ["asset_snapshots.asset_id", "asset_snapshots.tenant_id", "asset_snapshots.snapshot_id"],
        name="fk_previous_snapshot_asset_tenant",
    ),
    CheckConstraint("snapshot_number > 0", name="ck_asset_snapshot_number"),
    CheckConstraint("manifest_sha256 ~ '^[0-9a-f]{64}$'", name="ck_asset_manifest_sha256"),
    CheckConstraint("raw_input_sha256 ~ '^[0-9a-f]{64}$'", name="ck_asset_raw_sha256"),
    CheckConstraint("jsonb_typeof(canonical_payload) = 'object'", name="ck_snapshot_payload"),
    CheckConstraint("octet_length(raw_input) BETWEEN 1 AND 1048576", name="ck_snapshot_raw_size"),
)
Index(
    "ix_snapshots_tenant_asset_number",
    asset_snapshots.c.tenant_id,
    asset_snapshots.c.asset_id,
    asset_snapshots.c.snapshot_number.desc(),
)

asset_import_receipts = Table(
    "asset_import_receipts",
    metadata,
    Column("tenant_id", Text, primary_key=True),
    Column("actor_user_id", Text, ForeignKey("users.user_id"), primary_key=True),
    Column("request_route", Text, primary_key=True),
    Column("idempotency_key", Text, primary_key=True),
    Column("request_sha256", Text, nullable=False),
    Column("asset_id", Text, nullable=False),
    Column("snapshot_id", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["asset_id", "tenant_id", "snapshot_id"],
        ["asset_snapshots.asset_id", "asset_snapshots.tenant_id", "asset_snapshots.snapshot_id"],
        name="fk_import_snapshot_asset_tenant",
    ),
    CheckConstraint("length(idempotency_key) BETWEEN 1 AND 200", name="ck_asset_import_key"),
    CheckConstraint(
        "request_route IN ('asset-imports','asset-snapshots')", name="ck_asset_import_route"
    ),
    CheckConstraint("request_sha256 ~ '^[0-9a-f]{64}$'", name="ck_asset_request_sha256"),
)

SNAPSHOT_IMMUTABILITY_SQL = """
CREATE OR REPLACE FUNCTION prevent_asset_snapshot_changes() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
RAISE EXCEPTION 'asset snapshots are immutable' USING ERRCODE = '23514';
END $$;
CREATE TRIGGER asset_snapshots_immutable BEFORE UPDATE OR DELETE ON asset_snapshots
FOR EACH ROW EXECUTE FUNCTION prevent_asset_snapshot_changes();
"""
event.listen(asset_snapshots, "after_create", DDL(SNAPSHOT_IMMUTABILITY_SQL))

CURRENT_SNAPSHOT_REQUIRED_SQL = """
CREATE OR REPLACE FUNCTION require_asset_current_snapshot() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
IF EXISTS (SELECT 1 FROM assets WHERE asset_id = NEW.asset_id
AND tenant_id = NEW.tenant_id AND current_snapshot_id IS NULL) THEN
RAISE EXCEPTION 'asset current snapshot required' USING ERRCODE = '23514';
END IF;
RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER asset_current_snapshot_required AFTER INSERT OR UPDATE ON assets
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION require_asset_current_snapshot();
"""
event.listen(assets, "after_create", DDL(CURRENT_SNAPSHOT_REQUIRED_SQL))

ASSET_TABLES = (assets, asset_snapshots, asset_import_receipts)
