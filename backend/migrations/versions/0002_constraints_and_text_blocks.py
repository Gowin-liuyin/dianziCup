"""T05 审查修复: 租户/可见性 CHECK、合同索引、当前修订部分唯一、TextBlock 与证据一致性字段。

Revision ID: 0002_constraints_and_text_blocks
Revises: 0001_core_tables
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_constraints_and_text_blocks"
down_revision = "0001_core_tables"
branch_labels = None
depends_on = None

VISIBILITY_CHECK = "visibility IN ('public', 'tenant')"
TENANT_XOR_CHECK = (
    "(visibility = 'public' AND tenant_id IS NULL) "
    "OR (visibility = 'tenant' AND tenant_id IS NOT NULL)"
)


def upgrade() -> None:
    """补齐 03 §1/§4 约束: 可见性域、public/tenant 与 tenant_id 互斥、合同索引与 TextBlock。"""
    for table_name in ("sources", "documents", "document_revisions", "evidence", "claims"):
        op.create_check_constraint(f"ck_{table_name}_visibility", table_name, VISIBILITY_CHECK)
        op.create_check_constraint(f"ck_{table_name}_tenant_xor", table_name, TENANT_XOR_CHECK)
    op.create_index(
        "ix_claims_subject_predicate_status",
        "claims",
        ["subject", "predicate", "claim_status"],
    )
    op.create_index(
        "uq_current_revision_per_document",
        "document_revisions",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )
    op.create_table(
        "text_blocks",
        sa.Column("block_id", sa.Text(), primary_key=True),
        sa.Column(
            "revision_id",
            sa.Text(),
            sa.ForeignKey("document_revisions.revision_id"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("text_sha256", sa.Text(), nullable=False),
        sa.Column("block_text", sa.Text(), nullable=False),
        sa.UniqueConstraint("revision_id", "ordinal", name="uq_block_ordinal_per_revision"),
        sa.CheckConstraint("end_offset >= start_offset", name="ck_block_span_not_inverted"),
    )
    op.add_column(
        "evidence",
        sa.Column("block_id", sa.Text(), sa.ForeignKey("text_blocks.block_id"), nullable=True),
    )
    op.add_column("evidence", sa.Column("quote_sha256", sa.Text(), nullable=True))
    op.add_column("evidence", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("document_revisions", "revision_index", new_column_name="revision_number")
    op.alter_column("document_revisions", "supersedes_id", new_column_name="previous_revision_id")


def downgrade() -> None:
    """回滚本迁移: 删除 TextBlock 与证据一致性字段, 恢复 0001 结构。"""
    op.alter_column("document_revisions", "previous_revision_id", new_column_name="supersedes_id")
    op.alter_column("document_revisions", "revision_number", new_column_name="revision_index")
    op.drop_column("evidence", "verified_at")
    op.drop_column("evidence", "quote_sha256")
    op.drop_column("evidence", "block_id")
    op.drop_table("text_blocks")
    op.drop_index("uq_current_revision_per_document", table_name="document_revisions")
    op.drop_index("ix_claims_subject_predicate_status", table_name="claims")
    for table_name in ("claims", "evidence", "document_revisions", "documents", "sources"):
        op.drop_constraint(f"ck_{table_name}_tenant_xor", table_name, type_="check")
        op.drop_constraint(f"ck_{table_name}_visibility", table_name, type_="check")
