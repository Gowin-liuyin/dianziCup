"""逐维结果和历史持久化；失败结果不能修改已经保存的事实。

Revision ID: 0009_enrichment_results
Revises: 0008_event_operation_versions
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009_enrichment_results"
down_revision = "0008_event_operation_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """新增结果表，旧事实、事件和未知状态保持原值。"""
    op.create_table(
        "enrichment_results",
        sa.Column("result_id", sa.Text(), primary_key=True),
        sa.Column("event_id", sa.Text(), sa.ForeignKey("events.event_id"), nullable=False),
        sa.Column("dimension", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("claim_ids", JSONB(), nullable=False),
        sa.Column("reference_ids", JSONB(), nullable=False),
        sa.Column("error_code", sa.Text()),
        sa.Column("searched_at", sa.DateTime(timezone=True)),
        sa.Column("source_scope", JSONB(), nullable=False),
        sa.Column("last_job_id", sa.Text(), sa.ForeignKey("job_runs.job_id")),
        sa.Column("input_fingerprint", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "status IN ('available','not_found','not_applicable','conflict',"
            "'blocked','failed','pending')",
            name="ck_enrichment_result_status",
        ),
        sa.CheckConstraint("length(input_fingerprint)=64", name="ck_enrichment_input_fingerprint"),
        sa.CheckConstraint(
            "jsonb_typeof(claim_ids)='array' AND jsonb_typeof(reference_ids)='array' "
            "AND jsonb_typeof(source_scope)='array'",
            name="ck_enrichment_result_arrays",
        ),
        sa.UniqueConstraint(
            "event_id", "dimension", "input_fingerprint", name="uq_enrichment_result_input"
        ),
    )
    op.create_index(
        "uq_enrichment_result_current",
        "enrichment_results",
        ["event_id", "dimension"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )
    op.create_index(
        "ix_enrichment_result_history", "enrichment_results", ["event_id", "recorded_at"]
    )


def downgrade() -> None:
    """有结果历史的库只做前向修复或隔离恢复，不自动执行降级。"""
    op.drop_table("enrichment_results")
