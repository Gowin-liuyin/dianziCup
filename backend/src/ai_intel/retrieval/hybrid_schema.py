"""Proposed 0020 derived tables, separate metadata pending root migration integration."""

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    Table,
    Text,
)

hybrid_metadata = MetaData()

hybrid_index_generations = Table(
    "hybrid_index_generations",
    hybrid_metadata,
    Column("generation_id", Text(), primary_key=True),
    Column("index_name", Text(), nullable=False, unique=True),
    Column("model_version", Text(), nullable=False),
    Column("dimension", Integer(), nullable=False),
    Column("state", Text(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("dimension = 384", name="ck_hybrid_dimension"),
    CheckConstraint("state IN ('building','ready')", name="ck_hybrid_state"),
)

hybrid_chunks = Table(
    "hybrid_chunks",
    hybrid_metadata,
    Column("generation_id", Text(), primary_key=True),
    Column("chunk_id", Text(), primary_key=True),
    *(
        Column(f"{name}_id", Text(), nullable=False)
        for name in ("evidence", "revision", "document", "source", "event", "claim")
    ),
    Column("scope_key", Text(), nullable=False, index=True),
    Column("visibility", Text(), nullable=False),
    Column("tenant_id", Text()),
    Column("available_at", DateTime(timezone=True), nullable=False),
    Column("start_offset", Integer(), nullable=False),
    Column("end_offset", Integer(), nullable=False),
    Column("chunk_text", Text(), nullable=False),
    Column("text_sha256", Text(), nullable=False),
    Column("source_uri", Text(), nullable=False),
    Column("locator", Text(), nullable=False),
    Column("model_version", Text(), nullable=False),
    Column("embedding", VECTOR(384), nullable=False),
    Column("indexed_epoch", BigInteger(), nullable=False),
    Column("indexed_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(["generation_id"], [hybrid_index_generations.c.generation_id]),
    CheckConstraint("indexed_epoch >= 0", name="ck_hybrid_chunk_epoch"),
    CheckConstraint("end_offset > start_offset AND start_offset >= 0", name="ck_hybrid_offsets"),
    CheckConstraint(
        "(visibility = 'public' AND tenant_id IS NULL AND scope_key = 'public') OR "
        "(visibility = 'tenant' AND tenant_id IS NOT NULL AND scope_key = 'tenant:' || tenant_id)",
        name="ck_hybrid_chunk_scope",
    ),
)

hybrid_index_watermarks = Table(
    "hybrid_index_watermarks",
    hybrid_metadata,
    Column("generation_id", Text(), primary_key=True),
    Column("scope_key", Text(), primary_key=True),
    Column("indexed_epoch", BigInteger(), nullable=False),
    Column("outbox_id", Text(), nullable=False),
    Column("refreshed_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(["generation_id"], [hybrid_index_generations.c.generation_id]),
    CheckConstraint("indexed_epoch >= 0", name="ck_hybrid_watermark_epoch"),
)

hybrid_index_receipts = Table(
    "hybrid_index_receipts",
    hybrid_metadata,
    Column("generation_id", Text(), primary_key=True),
    Column("outbox_id", Text(), primary_key=True),
    Column("scope_key", Text(), nullable=False),
    Column("indexed_epoch", BigInteger(), nullable=False),
    Column("chunk_count", Integer(), nullable=False),
    Column("payload_sha256", Text(), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(["generation_id"], [hybrid_index_generations.c.generation_id]),
    CheckConstraint("indexed_epoch >= 0", name="ck_hybrid_receipt_epoch"),
)
