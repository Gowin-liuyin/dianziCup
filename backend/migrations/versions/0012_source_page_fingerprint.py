"""保存服务端页面请求指纹，旧回执留空并要求显式恢复。

Revision ID: 0012_source_page_fingerprint
Revises: 0011_job_delivery_and_cursors
"""

import sqlalchemy as sa
from alembic import op

revision = "0012_source_page_fingerprint"
down_revision = "0011_job_delivery_and_cursors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """不能从条数和游标伪造旧页面正文指纹。"""
    op.add_column("source_page_receipts", sa.Column("request_sha256", sa.Text()))
    op.create_check_constraint(
        "ck_source_page_request_sha256",
        "source_page_receipts",
        "request_sha256 IS NULL OR request_sha256 ~ '^[0-9a-f]{64}$'",
    )


def downgrade() -> None:
    """回退会丢失幂等输入依据，只允许前向修复或隔离备份恢复。"""
    raise RuntimeError("source page request fingerprints require forward-only recovery")
