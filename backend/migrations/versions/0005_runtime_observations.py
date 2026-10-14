"""R01运行观测；新增独立表，不修改已有业务记录。

Revision ID: 0005_runtime_observations
Revises: 0004_jobs_outbox
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_runtime_observations"
down_revision = "0004_jobs_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """记录worker/scheduler实际执行时点，健康检查据此判断失效。"""
    op.create_table(
        "runtime_observations",
        sa.Column("component", sa.Text(), primary_key=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("platform_version", sa.Text(), nullable=False),
        sa.CheckConstraint("component IN ('worker', 'scheduler')", name="ck_runtime_component"),
    )


def downgrade() -> None:
    """仅删运行观测；恢复现有应用时不需要删除事实或任务。"""
    op.drop_table("runtime_observations")
