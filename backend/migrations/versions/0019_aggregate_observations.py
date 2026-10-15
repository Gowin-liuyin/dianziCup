"""Freeze safe, immutable public or tenant aggregate observations.

Revision ID: 0019_aggregate_observations
Revises: 0018_asset_inventory
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0019_aggregate_observations"
down_revision = "0018_asset_inventory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Append observations without changing existing facts, cursors or historical jobs."""
    op.create_table(
        "r08_aggregate_observations",
        sa.Column("observation_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("canonical_json", JSONB(), nullable=False),
        sa.Column("payload_sha256", sa.Text(), nullable=False),
        sa.Column("call_key", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("query_id", sa.Text(), nullable=False),
        sa.Column("query_version", sa.Text(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True)),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text()),
        sa.Column("data_mode", sa.Text(), nullable=False),
        sa.Column("fee_status", sa.Text(), nullable=False),
        sa.Column("visibility", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text()),
        sa.Column("scope_key", sa.Text(), nullable=False),
        sa.CheckConstraint("schema_version = 'r08-aggregate-observation-1'", name="ck_r08_schema"),
        sa.CheckConstraint("provider IN ('hunter','quake')", name="ck_r08_provider"),
        sa.CheckConstraint("query_id IN ('ollama','vllm')", name="ck_r08_query"),
        sa.CheckConstraint("query_version = 'r08-product-name-1'", name="ck_r08_query_version"),
        sa.CheckConstraint("data_mode IN ('live','fixture')", name="ck_r08_mode"),
        sa.CheckConstraint("fee_status = 'unknown'", name="ck_r08_fee"),
        sa.CheckConstraint(
            "outcome = 'available' OR error_code IS NOT NULL",
            name="ck_r08_required_error",
        ),
        sa.CheckConstraint(
            "payload_sha256 ~ '^[0-9a-f]{64}$' AND call_key ~ '^[0-9a-f]{64}$'",
            name="ck_r08_hashes",
        ),
        sa.CheckConstraint(
            "(visibility='public' AND tenant_id IS NULL AND scope_key='public') OR "
            "(visibility='tenant' AND tenant_id IS NOT NULL AND scope_key='tenant:' || tenant_id)",
            name="ck_r08_scope",
        ),
        sa.CheckConstraint(
            "(outcome='available' AND error_code IS NULL) OR "
            "(outcome='unknown' AND error_code='missing_total') OR "
            "(outcome='unauthorized' AND error_code='provider_unauthorized') OR "
            "(outcome='rate_limited' AND error_code='provider_rate_limited') OR "
            "(outcome='not_configured' AND error_code='credential_missing') OR "
            "(outcome='failed' AND error_code IN "
            "('invalid_total','invalid_response','provider_http_error','provider_error',"
            "'network_error','network_dns_error','network_tls_error','network_timeout',"
            "'network_policy_violation','response_too_large','unsupported_content_type'))",
            name="ck_r08_outcome",
        ),
    )
    op.create_index(
        "ix_r08_current",
        "r08_aggregate_observations",
        [
            "call_key",
            "scope_key",
            sa.text("retrieved_at DESC"),
            sa.text("recorded_at DESC"),
            sa.text("(outcome = 'available') ASC"),
            sa.text("observation_id DESC"),
        ],
    )
    op.execute("""
        CREATE FUNCTION r08_reject_aggregate_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'aggregate observation history is immutable' USING ERRCODE = '55000';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER r08_aggregate_observations_immutable
        BEFORE UPDATE OR DELETE ON r08_aggregate_observations
        FOR EACH ROW EXECUTE FUNCTION r08_reject_aggregate_mutation()
    """)


def downgrade() -> None:
    """Aggregate observation history requires forward repair or backup recovery."""
    raise RuntimeError("aggregate observation history requires forward-only recovery")
