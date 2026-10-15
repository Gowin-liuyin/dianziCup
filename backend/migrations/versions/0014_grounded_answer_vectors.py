"""保存真实模型空间的派生检索块与用户拥有的引用回答。

Revision ID: 0014_grounded_answer_vectors
Revises: 0013_revision_source_metadata
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects.postgresql import JSONB

revision = "0014_grounded_answer_vectors"
down_revision = "0013_revision_source_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """仅新增派生数据和答案，不重写原文、证据、事实或历史游标。"""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public")
    op.execute(
        "SELECT set_config('search_path', current_setting('search_path') || ',public', true)"
    )
    op.create_table(
        "retrieval_chunks",
        sa.Column("chunk_id", sa.Text(), primary_key=True),
        sa.Column("evidence_id", sa.Text(), sa.ForeignKey("evidence.evidence_id"), nullable=False),
        sa.Column(
            "revision_id",
            sa.Text(),
            sa.ForeignKey("document_revisions.revision_id"),
            nullable=False,
        ),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.Text(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("embedding", VECTOR(384), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "start_offset >= 0 AND end_offset > start_offset", name="ck_chunk_offsets"
        ),
        sa.CheckConstraint(
            "end_offset - start_offset = char_length(chunk_text)", name="ck_chunk_length"
        ),
        sa.CheckConstraint("char_length(model_version) BETWEEN 1 AND 200", name="ck_chunk_space"),
        sa.UniqueConstraint(
            "evidence_id",
            "start_offset",
            "end_offset",
            "model_version",
            name="uq_evidence_chunk_space",
        ),
    )
    op.create_index(
        "ix_chunks_revision_space", "retrieval_chunks", ["revision_id", "model_version"]
    )
    op.create_table(
        "grounded_answers",
        sa.Column("answer_id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("tenant_id", sa.Text()),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("response", JSONB(), nullable=False),
        sa.Column("scope_epochs", JSONB(), nullable=False),
        sa.Column("model_trace", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(question_text) BETWEEN 1 AND 4096", name="ck_answer_question_length"
        ),
        sa.CheckConstraint("jsonb_typeof(response) = 'object'", name="ck_answer_response_object"),
        sa.CheckConstraint("jsonb_typeof(scope_epochs) = 'object'", name="ck_answer_epochs_object"),
        sa.CheckConstraint("jsonb_typeof(model_trace) = 'object'", name="ck_answer_trace_object"),
    )
    op.create_index("ix_answers_owner_created", "grounded_answers", ["user_id", "created_at"])


def downgrade() -> None:
    """答案保留历史证据与费用轨迹；关闭功能后前向修复，不破坏历史。"""
    raise RuntimeError("grounded answer history requires forward-only recovery")
