"""Freeze private asset identities, immutable snapshots and import receipts.

Revision ID: 0018_asset_inventory
Revises: 0017_enrichment_job_workflows
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0018_asset_inventory"
down_revision = "0017_enrichment_job_workflows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Current pointers can be populated within a transaction; history remains immutable."""
    op.create_table(
        "assets",
        sa.Column("asset_id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("criticality", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("current_snapshot_id", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("asset_id", "tenant_id", name="uq_asset_tenant_identity"),
        sa.CheckConstraint("length(tenant_id) BETWEEN 1 AND 200", name="ck_asset_tenant"),
        sa.CheckConstraint("length(display_name) BETWEEN 1 AND 200", name="ck_asset_display_name"),
    )
    op.create_index("ix_assets_tenant_created", "assets", ["tenant_id", "created_at", "asset_id"])
    op.create_table(
        "asset_snapshots",
        sa.Column("snapshot_id", sa.Text(), primary_key=True),
        sa.Column("asset_id", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("snapshot_number", sa.Integer(), nullable=False),
        sa.Column("previous_snapshot_id", sa.Text()),
        sa.Column("manifest_sha256", sa.Text(), nullable=False),
        sa.Column("raw_input_sha256", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("parser_version", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("source_version", sa.Text(), nullable=False),
        sa.Column("canonical_payload", JSONB(), nullable=False),
        sa.Column("raw_input", sa.LargeBinary(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", sa.Text(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.UniqueConstraint(
            "asset_id", "tenant_id", "snapshot_id", name="uq_snapshot_tenant_identity"
        ),
        sa.UniqueConstraint(
            "asset_id", "tenant_id", "snapshot_number", name="uq_asset_snapshot_number"
        ),
        sa.ForeignKeyConstraint(
            ["asset_id", "tenant_id"],
            ["assets.asset_id", "assets.tenant_id"],
            name="fk_snapshot_asset_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id", "tenant_id", "previous_snapshot_id"],
            [
                "asset_snapshots.asset_id",
                "asset_snapshots.tenant_id",
                "asset_snapshots.snapshot_id",
            ],
            name="fk_previous_snapshot_asset_tenant",
        ),
        sa.CheckConstraint("snapshot_number > 0", name="ck_asset_snapshot_number"),
        sa.CheckConstraint("manifest_sha256 ~ '^[0-9a-f]{64}$'", name="ck_asset_manifest_sha256"),
        sa.CheckConstraint("raw_input_sha256 ~ '^[0-9a-f]{64}$'", name="ck_asset_raw_sha256"),
        sa.CheckConstraint(
            "jsonb_typeof(canonical_payload) = 'object'", name="ck_snapshot_payload"
        ),
        sa.CheckConstraint(
            "octet_length(raw_input) BETWEEN 1 AND 1048576", name="ck_snapshot_raw_size"
        ),
    )
    op.create_index(
        "ix_snapshots_tenant_asset_number",
        "asset_snapshots",
        ["tenant_id", "asset_id", sa.text("snapshot_number DESC")],
    )
    op.create_foreign_key(
        "fk_asset_current_snapshot_tenant",
        "assets",
        "asset_snapshots",
        ["asset_id", "tenant_id", "current_snapshot_id"],
        ["asset_id", "tenant_id", "snapshot_id"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_table(
        "asset_import_receipts",
        sa.Column("tenant_id", sa.Text(), primary_key=True),
        sa.Column("actor_user_id", sa.Text(), sa.ForeignKey("users.user_id"), primary_key=True),
        sa.Column("request_route", sa.Text(), primary_key=True),
        sa.Column("idempotency_key", sa.Text(), primary_key=True),
        sa.Column("request_sha256", sa.Text(), nullable=False),
        sa.Column("asset_id", sa.Text(), nullable=False),
        sa.Column("snapshot_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_id", "tenant_id", "snapshot_id"],
            [
                "asset_snapshots.asset_id",
                "asset_snapshots.tenant_id",
                "asset_snapshots.snapshot_id",
            ],
            name="fk_import_snapshot_asset_tenant",
        ),
        sa.CheckConstraint("length(idempotency_key) BETWEEN 1 AND 200", name="ck_asset_import_key"),
        sa.CheckConstraint(
            "request_route IN ('asset-imports','asset-snapshots')",
            name="ck_asset_import_route",
        ),
        sa.CheckConstraint("request_sha256 ~ '^[0-9a-f]{64}$'", name="ck_asset_request_sha256"),
    )
    op.execute("""
        CREATE FUNCTION prevent_asset_snapshot_changes() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        RAISE EXCEPTION 'asset snapshots are immutable' USING ERRCODE = '23514';
        END $$
    """)
    op.execute("""
        CREATE TRIGGER asset_snapshots_immutable BEFORE UPDATE OR DELETE ON asset_snapshots
        FOR EACH ROW EXECUTE FUNCTION prevent_asset_snapshot_changes()
    """)
    op.execute("""
        CREATE FUNCTION require_asset_current_snapshot() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        IF EXISTS (SELECT 1 FROM assets WHERE asset_id = NEW.asset_id
        AND tenant_id = NEW.tenant_id AND current_snapshot_id IS NULL) THEN
        RAISE EXCEPTION 'asset current snapshot required' USING ERRCODE = '23514';
        END IF;
        RETURN NULL;
        END $$
    """)
    op.execute("""
        CREATE CONSTRAINT TRIGGER asset_current_snapshot_required AFTER INSERT OR UPDATE ON assets
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION require_asset_current_snapshot()
    """)


def downgrade() -> None:
    """Private asset history requires forward repair or backup recovery."""
    raise RuntimeError("asset inventory history requires forward-only recovery")
