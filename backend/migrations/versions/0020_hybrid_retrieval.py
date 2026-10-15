"""Add rebuildable hybrid projections linked to authoritative PG facts and outbox.

Revision ID: 0020_hybrid_retrieval
Revises: 0019_aggregate_observations
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR

revision = "0020_hybrid_retrieval"
down_revision = "0019_aggregate_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Keep existing facts and legacy vector space unchanged; derive only new indexes."""
    op.execute(
        "SELECT set_config('search_path', current_setting('search_path') || ',public', true)"
    )
    op.create_table(
        "hybrid_index_generations",
        sa.Column("generation_id", sa.Text(), primary_key=True),
        sa.Column("index_name", sa.Text(), nullable=False, unique=True),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("dimension = 384", name="ck_hybrid_dimension"),
        sa.CheckConstraint("state IN ('building','ready')", name="ck_hybrid_state"),
    )
    op.create_table(
        "hybrid_chunks",
        sa.Column(
            "generation_id",
            sa.Text(),
            sa.ForeignKey("hybrid_index_generations.generation_id"),
            primary_key=True,
        ),
        sa.Column("chunk_id", sa.Text(), primary_key=True),
        *(
            sa.Column(column, sa.Text(), sa.ForeignKey(target), nullable=False)
            for column, target in (
                ("evidence_id", "evidence.evidence_id"),
                ("revision_id", "document_revisions.revision_id"),
                ("document_id", "documents.document_id"),
                ("source_id", "sources.source_id"),
                ("event_id", "events.event_id"),
                ("claim_id", "claims.claim_id"),
            )
        ),
        sa.Column("scope_key", sa.Text(), nullable=False),
        sa.Column("visibility", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text()),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.Text(), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=False),
        sa.Column("locator", sa.Text(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("embedding", VECTOR(384), nullable=False),
        sa.Column("indexed_epoch", sa.BigInteger(), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("indexed_epoch >= 0", name="ck_hybrid_chunk_epoch"),
        sa.CheckConstraint(
            "end_offset > start_offset AND start_offset >= 0", name="ck_hybrid_offsets"
        ),
        sa.CheckConstraint(
            "(visibility = 'public' AND tenant_id IS NULL AND scope_key = 'public') OR "
            "(visibility = 'tenant' AND tenant_id IS NOT NULL "
            "AND scope_key = 'tenant:' || tenant_id)",
            name="ck_hybrid_chunk_scope",
        ),
    )
    op.create_index("ix_hybrid_chunks_scope_key", "hybrid_chunks", ["scope_key"])
    op.create_table(
        "hybrid_index_watermarks",
        sa.Column(
            "generation_id",
            sa.Text(),
            sa.ForeignKey("hybrid_index_generations.generation_id"),
            primary_key=True,
        ),
        sa.Column("scope_key", sa.Text(), primary_key=True),
        sa.Column("indexed_epoch", sa.BigInteger(), nullable=False),
        sa.Column("outbox_id", sa.Text(), sa.ForeignKey("outbox_events.event_id"), nullable=False),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("indexed_epoch >= 0", name="ck_hybrid_watermark_epoch"),
    )
    op.create_table(
        "hybrid_index_receipts",
        sa.Column(
            "generation_id",
            sa.Text(),
            sa.ForeignKey("hybrid_index_generations.generation_id"),
            primary_key=True,
        ),
        sa.Column(
            "outbox_id", sa.Text(), sa.ForeignKey("outbox_events.event_id"), primary_key=True
        ),
        sa.Column("scope_key", sa.Text(), nullable=False),
        sa.Column("indexed_epoch", sa.BigInteger(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("payload_sha256", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("indexed_epoch >= 0", name="ck_hybrid_receipt_epoch"),
    )


def downgrade() -> None:
    """Drop only rebuildable projections after workers are disabled and evidence backed up."""
    for table in (
        "hybrid_index_receipts",
        "hybrid_index_watermarks",
        "hybrid_chunks",
        "hybrid_index_generations",
    ):
        op.drop_table(table)
