"""Received response receipts survive normalization and business transaction rollback."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Table,
    Text,
    UniqueConstraint,
)

from ai_intel.knowledge.models import metadata

source_response_receipts = Table(
    "source_response_receipts",
    metadata,
    Column("receipt_id", Text(), primary_key=True),
    Column("schema_version", Integer(), nullable=False, server_default="1"),
    Column("job_id", Text(), nullable=False),
    Column("attempt_count", Integer(), nullable=False),
    Column("response_ordinal", Integer(), nullable=False),
    Column("source_kind", Text(), nullable=False),
    Column("source_id", Text(), nullable=False),
    Column("stream_kind", Text(), nullable=False),
    Column("window_end", DateTime(timezone=True), nullable=False),
    Column("input_cursor_sha256", Text(), nullable=False),
    Column("request_fingerprint_sha256", Text(), nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("http_status", Integer()),
    Column("content_type", Text()),
    Column("response_content_hash", Text(), ForeignKey("content_objects.content_hash")),
    Column("response_size_bytes", BigInteger()),
    Column("parse_outcome", Text(), nullable=False),
    Column("error_code", Text()),
    UniqueConstraint(
        "job_id", "attempt_count", "response_ordinal", name="uq_source_response_attempt"
    ),
    CheckConstraint("schema_version = 1", name="ck_source_response_schema"),
    CheckConstraint("attempt_count > 0", name="ck_source_response_attempt"),
    CheckConstraint("response_ordinal BETWEEN 1 AND 2", name="ck_source_response_ordinal"),
    CheckConstraint("stream_kind IN ('live','backfill')", name="ck_source_response_stream"),
    CheckConstraint(
        "source_kind IN ('nvd_ollama','vllm_vendor','osv_ollama',"
        "'avid_community','ollama_releases','trailofbits_blog',"
        "'arxiv_security','nist_ai_rmf','cac_generative_ai')",
        name="ck_source_response_kind",
    ),
    CheckConstraint("http_status BETWEEN 100 AND 599", name="ck_source_response_http_status"),
    CheckConstraint(
        "content_type IN ('application/json','application/xml','text/xml',"
        "'application/atom+xml','application/rss+xml','text/html',"
        "'application/pdf','text/plain','application/octet-stream')",
        name="ck_source_response_content_type",
    ),
    CheckConstraint(
        "input_cursor_sha256 ~ '^[0-9a-f]{64}$' AND request_fingerprint_sha256 ~ '^[0-9a-f]{64}$'",
        name="ck_source_response_fingerprints",
    ),
    CheckConstraint(
        "(response_content_hash IS NULL AND response_size_bytes IS NULL) "
        "OR (response_content_hash IS NOT NULL AND response_size_bytes IS "
        "NOT NULL AND response_content_hash ~ '^[0-9a-f]{64}$' AND "
        "response_size_bytes BETWEEN 0 AND 5242880)",
        name="ck_source_response_content_pair",
    ),
    CheckConstraint(
        "parse_outcome IN ('received','normalized','normalization_failed','transport_failed')",
        name="ck_source_response_outcome",
    ),
    CheckConstraint(
        "parse_outcome NOT IN ('normalized','normalization_failed') OR "
        "(http_status IS NOT NULL AND http_status = 200 AND "
        "response_content_hash IS NOT NULL)",
        name="ck_source_response_parse_body",
    ),
    CheckConstraint(
        "parse_outcome NOT IN ('normalization_failed','transport_failed') "
        "OR error_code IS NOT NULL",
        name="ck_source_response_failed_reason",
    ),
    CheckConstraint(
        "parse_outcome != 'normalized' OR error_code IS NULL",
        name="ck_source_response_normalized_error",
    ),
    CheckConstraint(
        "parse_outcome != 'transport_failed' OR response_content_hash IS NULL",
        name="ck_source_response_transport_body",
    ),
    CheckConstraint("error_code ~ '^[a-z0-9_]{1,120}$'", name="ck_source_response_error_code"),
)
Index(
    "ix_source_response_observed",
    source_response_receipts.c.source_kind,
    source_response_receipts.c.observed_at,
)
Index(
    "ix_source_response_job",
    source_response_receipts.c.job_id,
    source_response_receipts.c.attempt_count,
)
