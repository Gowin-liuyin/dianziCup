"""核心表: 来源、原文、修订、证据、论断、抓取尝试与 scope epoch。

Revision ID: 0001_core_tables
Revises:
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_core_tables"
down_revision = None
branch_labels = None
depends_on = None

CONTENT_HASH_TARGET = "content_objects.content_hash"
REVISION_TARGET = "document_revisions.revision_id"


def upgrade() -> None:
    """建立当前数据链所需核心表、外键、唯一键与索引。"""
    op.create_table(
        "scope_epochs",
        sa.Column("scope_key", sa.Text(), primary_key=True),
        sa.Column("epoch", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "sources",
        sa.Column("source_id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("base_origin", sa.Text(), nullable=False),
        sa.Column("visibility", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "content_objects",
        sa.Column("content_hash", sa.Text(), primary_key=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "documents",
        sa.Column("document_id", sa.Text(), primary_key=True),
        sa.Column("source_id", sa.Text(), sa.ForeignKey("sources.source_id"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.Text(), sa.ForeignKey(CONTENT_HASH_TARGET), nullable=False),
        sa.Column("visibility", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
    )
    op.create_index("ix_documents_source", "documents", ["source_id"])
    op.create_table(
        "document_revisions",
        sa.Column("revision_id", sa.Text(), primary_key=True),
        sa.Column("document_id", sa.Text(), sa.ForeignKey("documents.document_id"), nullable=False),
        sa.Column("revision_index", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.Text(), sa.ForeignKey(CONTENT_HASH_TARGET), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("supersedes_id", sa.Text(), sa.ForeignKey(REVISION_TARGET), nullable=True),
        sa.Column("visibility", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=True),
        sa.UniqueConstraint("document_id", "revision_index", name="uq_revision_per_document"),
    )
    op.create_index("ix_revisions_document", "document_revisions", ["document_id"])
    op.create_table(
        "evidence",
        sa.Column("evidence_id", sa.Text(), primary_key=True),
        sa.Column("revision_id", sa.Text(), sa.ForeignKey(REVISION_TARGET), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("locator", sa.Text(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("supports_claim", sa.Boolean(), nullable=False),
        sa.Column("visibility", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("end_offset >= start_offset", name="ck_span_not_inverted"),
    )
    op.create_index("ix_evidence_revision", "evidence", ["revision_id"])
    op.create_table(
        "claims",
        sa.Column("claim_id", sa.Text(), primary_key=True),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("predicate", sa.Text(), nullable=False),
        sa.Column("object_value", sa.Text(), nullable=False),
        sa.Column("claim_status", sa.Text(), nullable=False),
        sa.Column("claim_origin", sa.Text(), nullable=False),
        sa.Column("condition_value", sa.Text(), nullable=False),
        sa.Column("freshness", sa.Text(), nullable=False),
        sa.Column("asserted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("visibility", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_claims_subject", "claims", ["subject"])
    op.create_table(
        "fetch_attempts",
        sa.Column("attempt_id", sa.Text(), primary_key=True),
        sa.Column("source_id", sa.Text(), sa.ForeignKey("sources.source_id"), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("new_event_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_fetch_attempts_source", "fetch_attempts", ["source_id"])


def downgrade() -> None:
    """回滚: 按依赖逆序删除本迁移创建的表; 不触碰迁移版本表本身。"""
    op.drop_table("fetch_attempts")
    op.drop_table("claims")
    op.drop_table("evidence")
    op.drop_table("document_revisions")
    op.drop_table("documents")
    op.drop_table("content_objects")
    op.drop_table("sources")
    op.drop_table("scope_epochs")
