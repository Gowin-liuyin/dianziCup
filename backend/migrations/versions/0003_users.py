"""T06 审查修复 M4: 预创建用户持久化表。

Revision ID: 0003_users
Revises: 0002_constraints_and_text_blocks
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_users"
down_revision = "0002_constraints_and_text_blocks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """建立预创建用户表: 用户名唯一、仅存哈希、租户/角色约束。"""
    op.create_table(
        "users",
        sa.Column("user_id", sa.Text(), primary_key=True),
        sa.Column("username", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('tenant_admin', 'system_admin', 'analyst', 'viewer')",
            name="ck_users_role",
        ),
        sa.CheckConstraint(
            "(tenant_id IS NULL AND role = 'system_admin') OR tenant_id IS NOT NULL",
            name="ck_users_tenant_admin_requires_tenant",
        ),
    )


def downgrade() -> None:
    """回滚: 删除用户表。"""
    op.drop_table("users")
