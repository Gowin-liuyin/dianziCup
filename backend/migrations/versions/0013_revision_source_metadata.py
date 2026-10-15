"""按修订保留真实来源与解析定位，旧数据不推测补齐。

Revision ID: 0013_revision_source_metadata
Revises: 0012_source_page_fingerprint
"""

import sqlalchemy as sa
from alembic import op

revision = "0013_revision_source_metadata"
down_revision = "0012_source_page_fingerprint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """仅添加列；旧事实、时间、文本与已保存坐标完全保留。"""
    for name in ("canonical_uri", "parser_version", "normalizer_version", "source_json_pointer"):
        op.add_column("document_revisions", sa.Column(name, sa.Text()))
    for name in ("source_published_at", "source_modified_at", "first_observed_at", "ingested_at"):
        op.add_column("document_revisions", sa.Column(name, sa.DateTime(timezone=True)))
    op.add_column(
        "document_revisions",
        sa.Column("parse_status", sa.Text(), nullable=False, server_default="legacy_unverified"),
    )
    op.add_column("document_revisions", sa.Column("source_response_hash", sa.Text()))
    op.create_foreign_key(
        "fk_revision_source_response",
        "document_revisions",
        "content_objects",
        ["source_response_hash"],
        ["content_hash"],
    )
    op.create_check_constraint(
        "ck_revision_parse_status",
        "document_revisions",
        "parse_status IN ('pending','parsed','partial','failed','legacy_unverified')",
    )
    op.add_column(
        "text_blocks",
        sa.Column("block_type", sa.Text(), nullable=False, server_default="paragraph"),
    )
    op.add_column("text_blocks", sa.Column("page_number", sa.Integer()))
    op.add_column("text_blocks", sa.Column("json_pointer", sa.Text()))
    op.create_check_constraint(
        "ck_block_page_number", "text_blocks", "page_number IS NULL OR page_number >= 1"
    )
    op.add_column("fetch_attempts", sa.Column("response_content_hash", sa.Text()))
    op.add_column("fetch_attempts", sa.Column("final_url", sa.Text()))
    op.create_foreign_key(
        "fk_fetch_response_content",
        "fetch_attempts",
        "content_objects",
        ["response_content_hash"],
        ["content_hash"],
    )


def downgrade() -> None:
    """来源与历史定位不可丢弃，回退必须停用新写入并前向修复。"""
    raise RuntimeError("revision provenance requires forward-only recovery")
