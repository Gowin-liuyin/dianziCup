"""Add frozen immutable R11 history through the production forward chain.

Revision ID: 0022_sbom_sidecars
Revises: 0021_condition_assessments
"""

from alembic import op

revision = "0022_sbom_sidecars"
down_revision = "0021_condition_assessments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create only new tables; existing facts, bytes and hashes are unchanged."""
    op.execute(
        """
CREATE TABLE asset_snapshot_sbom_sidecars (
snapshot_id TEXT NOT NULL,
asset_id TEXT NOT NULL,
tenant_id TEXT NOT NULL,
adapter_version TEXT NOT NULL,
spec_version TEXT NOT NULL,
sidecar_sha256 TEXT NOT NULL,
combined_semantic_sha256 TEXT NOT NULL,
canonical_payload JSONB NOT NULL,
PRIMARY KEY (snapshot_id),
CONSTRAINT fk_sbom_sidecar_snapshot_tenant FOREIGN KEY(asset_id, tenant_id, snapshot_id)
REFERENCES asset_snapshots (asset_id, tenant_id, snapshot_id),
CONSTRAINT ck_sbom_sidecar_tenant CHECK (length(tenant_id) BETWEEN 1 AND 200),
CONSTRAINT ck_sbom_adapter_version CHECK (length(adapter_version) BETWEEN 1 AND 200),
CONSTRAINT ck_sbom_spec_version CHECK (length(spec_version) BETWEEN 1 AND 200),
CONSTRAINT ck_sbom_sidecar_sha256 CHECK (sidecar_sha256 ~ '^[0-9a-f]{64}$'),
CONSTRAINT ck_sbom_combined_sha256 CHECK (combined_semantic_sha256 ~ '^[0-9a-f]{64}$'),
CONSTRAINT ck_sbom_sidecar_payload CHECK (jsonb_typeof(canonical_payload) = 'object')
)
        """
    )
    op.execute(
        """
CREATE OR REPLACE FUNCTION prevent_sbom_sidecar_changes() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
RAISE EXCEPTION 'SBOM sidecars are immutable' USING ERRCODE = '23514';
END $$;
CREATE TRIGGER asset_snapshot_sbom_sidecars_immutable BEFORE UPDATE OR DELETE
ON asset_snapshot_sbom_sidecars FOR EACH ROW EXECUTE FUNCTION
prevent_sbom_sidecar_changes();
        """
    )


def downgrade() -> None:
    """Preserve evidence history; disable writers and use an approved forward repair."""
    raise RuntimeError("R11 immutable history cannot be downgraded; use forward repair")
