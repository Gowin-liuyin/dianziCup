"""持久化任务输入、交付重试与来源游标，不把Celery状态当业务权威。

Revision ID: 0011_job_delivery_and_cursors
Revises: 0010_enrichment_publications
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0011_job_delivery_and_cursors"
down_revision = "0010_enrichment_publications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """旧哈希引用保持原样，无法重放的旧任务显式处理，不猜其payload。"""
    op.drop_constraint("uq_job_idempotency_key", "job_runs", type_="unique")
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_job_scoped_idempotency ON job_runs "
            "(COALESCE(tenant_id, ''), job_type, idempotency_key)"
        )
    )
    for column in (
        sa.Column("next_retry_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.Text()),
        sa.Column("result_ref", sa.Text()),
    ):
        op.add_column("job_runs", column)
    op.create_index("ix_job_due", "job_runs", ["status", "next_retry_at", "lease_expires_at"])
    for column in (
        sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_delivery_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.Text()),
    ):
        op.add_column("outbox_events", column)
    op.create_table(
        "job_payloads",
        sa.Column("job_id", sa.Text(), sa.ForeignKey("job_runs.job_id"), primary_key=True),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("octet_length(payload) <= 1048576", name="ck_job_payload_bound"),
    )
    op.create_table(
        "job_transitions",
        sa.Column(
            "transition_sequence", sa.BigInteger(), sa.Identity(always=True), primary_key=True
        ),
        sa.Column("job_id", sa.Text(), sa.ForeignKey("job_runs.job_id"), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=False),
        sa.Column("to_status", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_job_transition_history", "job_transitions", ["job_id", "transition_sequence"]
    )
    op.create_table(
        "source_cursors",
        sa.Column("source_id", sa.Text(), sa.ForeignKey("sources.source_id"), primary_key=True),
        sa.Column("stream_kind", sa.Text(), primary_key=True),
        sa.Column("cursor_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("window_start", sa.DateTime(timezone=True)),
        sa.Column("window_end", sa.DateTime(timezone=True)),
        sa.Column("watermark_published_at", sa.DateTime(timezone=True)),
        sa.Column("last_successful_page", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_owner", sa.Text()),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("stream_kind IN ('live','backfill')", name="ck_source_cursor_stream"),
        sa.CheckConstraint("generation >= 0", name="ck_source_cursor_generation"),
    )
    op.create_table(
        "source_page_receipts",
        sa.Column("source_id", sa.Text(), primary_key=True),
        sa.Column("stream_kind", sa.Text(), primary_key=True),
        sa.Column("page_key", sa.Text(), primary_key=True),
        sa.Column("input_cursor", JSONB(), nullable=False),
        sa.Column("output_cursor", JSONB(), nullable=False),
        sa.Column("revision_ids", JSONB(), nullable=False),
        sa.Column("failed_job_ids", JSONB(), nullable=False),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id", "stream_kind"], ["source_cursors.source_id", "source_cursors.stream_kind"]
        ),
        sa.CheckConstraint("length(page_key)=64", name="ck_source_page_key"),
    )


def downgrade() -> None:
    """事实输入与游标历史不能安全退回内存；使用前向修复或备份恢复。"""
    raise RuntimeError("job payload and cursor history require forward-only recovery")
