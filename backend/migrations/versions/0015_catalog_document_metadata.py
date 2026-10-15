"""保留论文、仓库、标准和政策的来源原始字段与内容能力。

Revision ID: 0015_catalog_document_metadata
Revises: 0014_grounded_answer_vectors
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0015_catalog_document_metadata"
down_revision = "0014_grounded_answer_vectors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """只加修订级元数据，旧日期、内容和证据不推测重写。"""
    op.add_column(
        "document_revisions",
        sa.Column(
            "source_metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
    )
    op.create_check_constraint(
        "ck_revision_source_metadata_object",
        "document_revisions",
        "jsonb_typeof(source_metadata) = 'object'",
    )


def downgrade() -> None:
    """停新来源写入后以前向修复恢复，不删除来源与历史字段。"""
    raise RuntimeError("source document metadata requires forward-only recovery")
