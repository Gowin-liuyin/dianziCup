"""知识层表映射: 与 migrations/0001_core_tables 一一对应的 SQLAlchemy Table。"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
)

metadata = MetaData()

scope_epochs = Table(
    "scope_epochs",
    metadata,
    Column("scope_key", Text(), primary_key=True),
    Column("epoch", BigInteger(), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

content_objects = Table(
    "content_objects",
    metadata,
    Column("content_hash", Text(), primary_key=True),
    Column("size_bytes", BigInteger(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

documents = Table(
    "documents",
    metadata,
    Column("document_id", Text(), primary_key=True),
    Column("source_id", Text(), ForeignKey("sources.source_id"), nullable=False),
    Column("kind", Text(), nullable=False),
    Column("title", Text(), nullable=False),
    Column("published_at", DateTime(timezone=True), nullable=True),
    Column("retrieved_at", DateTime(timezone=True), nullable=False),
    Column("content_hash", Text(), ForeignKey("content_objects.content_hash"), nullable=False),
    Column("visibility", Text(), nullable=False),
    Column("tenant_id", Text(), nullable=True),
    Column("schema_version", Integer(), nullable=False),
)

document_revisions = Table(
    "document_revisions",
    metadata,
    Column("revision_id", Text(), primary_key=True),
    Column("document_id", Text(), ForeignKey("documents.document_id"), nullable=False),
    Column("revision_index", Integer(), nullable=False),
    Column("content_hash", Text(), ForeignKey("content_objects.content_hash"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("is_current", Boolean(), nullable=False),
    Column("supersedes_id", Text(), ForeignKey("document_revisions.revision_id"), nullable=True),
    Column("visibility", Text(), nullable=False),
    Column("tenant_id", Text(), nullable=True),
    UniqueConstraint("document_id", "revision_index", name="uq_revision_per_document"),
)

evidence = Table(
    "evidence",
    metadata,
    Column("evidence_id", Text(), primary_key=True),
    Column("revision_id", Text(), ForeignKey("document_revisions.revision_id"), nullable=False),
    Column("start_offset", Integer(), nullable=False),
    Column("end_offset", Integer(), nullable=False),
    Column("locator", Text(), nullable=False),
    Column("quote", Text(), nullable=False),
    Column("supports_claim", Boolean(), nullable=False),
    Column("visibility", Text(), nullable=False),
    Column("tenant_id", Text(), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("end_offset >= start_offset", name="ck_span_not_inverted"),
)

fetch_attempts = Table(
    "fetch_attempts",
    metadata,
    Column("attempt_id", Text(), primary_key=True),
    Column("source_id", Text(), ForeignKey("sources.source_id"), nullable=False),
    Column("attempted_at", DateTime(timezone=True), nullable=False),
    Column("outcome", Text(), nullable=False),
    Column("http_status", Integer(), nullable=True),
    Column("new_event_count", Integer(), nullable=False, server_default="0"),
)
