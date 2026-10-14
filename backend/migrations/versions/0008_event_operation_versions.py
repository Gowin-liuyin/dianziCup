"""事件撤销使用实际merge前版本栅栏，无法确认的旧操作保持待核验。

Revision ID: 0008_event_operation_versions
Revises: 0007_knowledge_state
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_event_operation_versions"
down_revision = "0007_knowledge_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """旧行不猜默认版本，新操作显式写入两端版本用于安全undo。"""
    op.add_column("event_operations", sa.Column("source_business_version", sa.Integer()))
    op.add_column("event_operations", sa.Column("target_business_version", sa.Integer()))
    op.create_check_constraint(
        "ck_event_operation_versions",
        "event_operations",
        "(source_business_version IS NULL AND target_business_version IS NULL) OR "
        "(source_business_version IS NOT NULL AND target_business_version IS NOT NULL "
        "AND source_business_version >= 1 AND target_business_version >= 1)",
    )


def downgrade() -> None:
    """不在有历史数据环境自动执行降级。"""
    op.drop_constraint("ck_event_operation_versions", "event_operations", type_="check")
    op.drop_column("event_operations", "target_business_version")
    op.drop_column("event_operations", "source_business_version")
