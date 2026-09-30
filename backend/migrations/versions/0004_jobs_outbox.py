"""T07: 任务、事务 outbox、租约与幂等键表。

Revision ID: 0004_jobs_outbox
Revises: 0003_users
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_jobs_outbox"
down_revision = "0003_users"
branch_labels = None
depends_on = None

JOB_STATUS = (
    "status IN ('queued','running','retry_wait','waiting_approval',"
    "'succeeded','partial','failed','cancelled','blocked')"
)


def upgrade() -> None:
    """建 JobRun/OutboxEvent/租约与幂等键表: 业务记录与 outbox 同事务提交的基础。"""
    op.create_table(
        "job_runs",
        sa.Column("job_id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=True),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("payload_sha256", sa.Text(), nullable=True),
        sa.Column("payload_ref", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("lease_owner", sa.Text(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_job_idempotency_key"),
        sa.CheckConstraint(JOB_STATUS, name="ck_job_status"),
    )
    op.create_index("ix_job_runs_tenant", "job_runs", ["tenant_id"])
    op.create_table(
        "outbox_events",
        sa.Column("event_id", sa.Text(), primary_key=True),
        sa.Column("job_id", sa.Text(), sa.ForeignKey("job_runs.job_id"), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("payload_ref", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_unpublished", "outbox_events", ["published_at"])


def downgrade() -> None:
    """回滚: 删除 outbox 与任务表。"""
    op.drop_table("outbox_events")
    op.drop_table("job_runs")
