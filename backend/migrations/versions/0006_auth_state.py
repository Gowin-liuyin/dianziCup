"""R02共享认证状态；仅扩展表，不替换已有用户或业务事实。

Revision ID: 0006_auth_state
Revises: 0005_runtime_observations
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_auth_state"
down_revision = "0005_runtime_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """会话只保存hash；按客户端桶序列化失败与在途占位；审计使用固定字段。"""
    op.create_table(
        "auth_sessions",
        sa.Column("session_hash", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("csrf_token", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(session_hash) = 64", name="ck_auth_session_hash_length"),
        sa.CheckConstraint("expires_at > issued_at", name="ck_auth_session_expiry"),
    )
    op.create_index("ix_auth_sessions_user", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expiry", "auth_sessions", ["expires_at"])
    op.create_table(
        "auth_login_buckets",
        sa.Column("client_key_hash", sa.Text(), primary_key=True),
        sa.CheckConstraint("length(client_key_hash) = 64", name="ck_auth_client_hash_length"),
    )
    op.create_table(
        "auth_login_attempts",
        sa.Column("attempt_id", sa.Text(), primary_key=True),
        sa.Column(
            "client_key_hash",
            sa.Text(),
            sa.ForeignKey("auth_login_buckets.client_key_hash"),
            nullable=False,
        ),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_auth_login_attempts_window", "auth_login_attempts", ["client_key_hash", "attempted_at"]
    )
    op.create_table(
        "auth_audit_events",
        sa.Column("audit_id", sa.Text(), primary_key=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.Text(), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("tenant_id", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("submitted_keys", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auth_audit_scope_time", "auth_audit_events", ["tenant_id", "created_at"])


def downgrade() -> None:
    """仅供显式隔离恢复设计；批处理不在有数据环境自动执行降级。"""
    op.drop_table("auth_audit_events")
    op.drop_table("auth_login_attempts")
    op.drop_table("auth_login_buckets")
    op.drop_table("auth_sessions")
