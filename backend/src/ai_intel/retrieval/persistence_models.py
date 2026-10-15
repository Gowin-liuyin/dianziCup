"""检索块是可重建派生数据，永久证据与事实仍归原有PG知识表。"""

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Table, Text
from sqlalchemy.dialects.postgresql import JSONB

from ai_intel.knowledge.models import metadata

retrieval_chunks = Table(
    "retrieval_chunks",
    metadata,
    Column("chunk_id", Text(), primary_key=True),
    Column("evidence_id", Text(), ForeignKey("evidence.evidence_id"), nullable=False),
    Column("revision_id", Text(), ForeignKey("document_revisions.revision_id"), nullable=False),
    Column("start_offset", Integer(), nullable=False),
    Column("end_offset", Integer(), nullable=False),
    Column("chunk_text", Text(), nullable=False),
    Column("text_sha256", Text(), nullable=False),
    Column("model_version", Text(), nullable=False),
    Column("embedding", VECTOR(384), nullable=False),
    Column("indexed_at", DateTime(timezone=True), nullable=False),
)

grounded_answers = Table(
    "grounded_answers",
    metadata,
    Column("answer_id", Text(), primary_key=True),
    Column("user_id", Text(), ForeignKey("users.user_id"), nullable=False),
    Column("tenant_id", Text()),
    Column("question_text", Text(), nullable=False),
    Column("response", JSONB(), nullable=False),
    Column("scope_epochs", JSONB(), nullable=False),
    Column("model_trace", JSONB(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
