"""Retain bounded raw response identities independently of parsing success.

Revision ID: 0016_source_response_receipts
Revises: 0015_catalog_document_metadata
"""

import sqlalchemy as sa
from alembic import op

revision = "0016_source_response_receipts"
down_revision = "0015_catalog_document_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No source/job FK waits on locks held by the collecting transaction."""
    op.create_table(
        "source_response_receipts",
        sa.Column("receipt_id", sa.Text(), primary_key=True),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("response_ordinal", sa.Integer(), nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("stream_kind", sa.Text(), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_cursor_sha256", sa.Text(), nullable=False),
        sa.Column("request_fingerprint_sha256", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("http_status", sa.Integer()),
        sa.Column("content_type", sa.Text()),
        sa.Column(
            "response_content_hash", sa.Text(), sa.ForeignKey("content_objects.content_hash")
        ),
        sa.Column("response_size_bytes", sa.BigInteger()),
        sa.Column("parse_outcome", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text()),
        sa.UniqueConstraint(
            "job_id", "attempt_count", "response_ordinal", name="uq_source_response_attempt"
        ),
        sa.CheckConstraint("schema_version = 1", name="ck_source_response_schema"),
        sa.CheckConstraint("attempt_count > 0", name="ck_source_response_attempt"),
        sa.CheckConstraint("response_ordinal BETWEEN 1 AND 2", name="ck_source_response_ordinal"),
        sa.CheckConstraint("stream_kind IN ('live','backfill')", name="ck_source_response_stream"),
        sa.CheckConstraint(
            "source_kind IN ('nvd_ollama','vllm_vendor','osv_ollama',"
            "'avid_community','ollama_releases','trailofbits_blog',"
            "'arxiv_security','nist_ai_rmf','cac_generative_ai')",
            name="ck_source_response_kind",
        ),
        sa.CheckConstraint(
            "http_status BETWEEN 100 AND 599", name="ck_source_response_http_status"
        ),
        sa.CheckConstraint(
            "content_type IN ('application/json','application/xml','text/xml',"
            "'application/atom+xml','application/rss+xml','text/html',"
            "'application/pdf','text/plain','application/octet-stream')",
            name="ck_source_response_content_type",
        ),
        sa.CheckConstraint(
            "input_cursor_sha256 ~ '^[0-9a-f]{64}$' AND "
            "request_fingerprint_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_source_response_fingerprints",
        ),
        sa.CheckConstraint(
            "(response_content_hash IS NULL AND response_size_bytes IS NULL) "
            "OR (response_content_hash IS NOT NULL AND response_size_bytes IS "
            "NOT NULL AND response_content_hash ~ '^[0-9a-f]{64}$' AND "
            "response_size_bytes BETWEEN 0 AND 5242880)",
            name="ck_source_response_content_pair",
        ),
        sa.CheckConstraint(
            "parse_outcome IN ('received','normalized','normalization_failed','transport_failed')",
            name="ck_source_response_outcome",
        ),
        sa.CheckConstraint(
            "parse_outcome NOT IN ('normalized','normalization_failed') OR "
            "(http_status IS NOT NULL AND http_status = 200 AND "
            "response_content_hash IS NOT NULL)",
            name="ck_source_response_parse_body",
        ),
        sa.CheckConstraint(
            "parse_outcome NOT IN ('normalization_failed','transport_failed') "
            "OR error_code IS NOT NULL",
            name="ck_source_response_failed_reason",
        ),
        sa.CheckConstraint(
            "parse_outcome != 'normalized' OR error_code IS NULL",
            name="ck_source_response_normalized_error",
        ),
        sa.CheckConstraint(
            "parse_outcome != 'transport_failed' OR response_content_hash IS NULL",
            name="ck_source_response_transport_body",
        ),
        sa.CheckConstraint(
            "error_code ~ '^[a-z0-9_]{1,120}$'", name="ck_source_response_error_code"
        ),
    )
    op.create_index(
        "ix_source_response_observed", "source_response_receipts", ["source_kind", "observed_at"]
    )
    op.create_index(
        "ix_source_response_job", "source_response_receipts", ["job_id", "attempt_count"]
    )


def downgrade() -> None:
    """Captured raw and failure history require forward recovery, not deletion."""
    raise RuntimeError("source response history requires forward-only recovery")
