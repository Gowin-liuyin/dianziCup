"""知识层表映射: 与 migrations/0001+0002 对应的 SQLAlchemy Table。"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Integer,
    LargeBinary,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

VISIBILITY_DOMAIN = "visibility IN ('public', 'tenant')"
TENANT_XOR = (
    "(visibility = 'public' AND tenant_id IS NULL) "
    "OR (visibility = 'tenant' AND tenant_id IS NOT NULL)"
)

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
    CheckConstraint(VISIBILITY_DOMAIN, name="ck_documents_visibility"),
    CheckConstraint(TENANT_XOR, name="ck_documents_tenant_xor"),
)

document_revisions = Table(
    "document_revisions",
    metadata,
    Column("revision_id", Text(), primary_key=True),
    Column("document_id", Text(), ForeignKey("documents.document_id"), nullable=False),
    Column("revision_number", Integer(), nullable=False),
    Column("content_hash", Text(), ForeignKey("content_objects.content_hash"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("is_current", Boolean(), nullable=False),
    Column(
        "previous_revision_id", Text(), ForeignKey("document_revisions.revision_id"), nullable=True
    ),
    Column("visibility", Text(), nullable=False),
    Column("tenant_id", Text(), nullable=True),
    Column("canonical_uri", Text()),
    Column("source_published_at", DateTime(timezone=True)),
    Column("source_modified_at", DateTime(timezone=True)),
    Column("first_observed_at", DateTime(timezone=True)),
    Column("ingested_at", DateTime(timezone=True)),
    Column("parser_version", Text()),
    Column("normalizer_version", Text()),
    Column("parse_status", Text(), nullable=False, server_default="legacy_unverified"),
    Column("source_response_hash", Text(), ForeignKey("content_objects.content_hash")),
    Column("source_json_pointer", Text()),
    Column("source_metadata", JSONB(), nullable=False, server_default="{}"),
    CheckConstraint(
        "jsonb_typeof(source_metadata) = 'object'", name="ck_revision_source_metadata_object"
    ),
    UniqueConstraint("document_id", "revision_number", name="uq_revision_per_document"),
    CheckConstraint(
        "parse_status IN ('pending','parsed','partial','failed','legacy_unverified')",
        name="ck_revision_parse_status",
    ),
    CheckConstraint(VISIBILITY_DOMAIN, name="ck_document_revisions_visibility"),
    CheckConstraint(TENANT_XOR, name="ck_document_revisions_tenant_xor"),
)

text_blocks = Table(
    "text_blocks",
    metadata,
    Column("block_id", Text(), primary_key=True),
    Column("revision_id", Text(), ForeignKey("document_revisions.revision_id"), nullable=False),
    Column("ordinal", Integer(), nullable=False),
    Column("start_offset", Integer(), nullable=False),
    Column("end_offset", Integer(), nullable=False),
    Column("text_sha256", Text(), nullable=False),
    Column("block_text", Text(), nullable=False),
    Column("block_type", Text(), nullable=False, server_default="paragraph"),
    Column("page_number", Integer()),
    Column("json_pointer", Text()),
    UniqueConstraint("revision_id", "ordinal", name="uq_block_ordinal_per_revision"),
    CheckConstraint("end_offset >= start_offset", name="ck_block_span_not_inverted"),
    CheckConstraint("page_number IS NULL OR page_number >= 1", name="ck_block_page_number"),
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
    Column("block_id", Text(), ForeignKey("text_blocks.block_id"), nullable=True),
    Column("quote_sha256", Text(), nullable=True),
    Column("verified_at", DateTime(timezone=True), nullable=True),
    Column("coordinate_version", Text(), nullable=False, server_default="legacy_unverified"),
    CheckConstraint("end_offset >= start_offset", name="ck_span_not_inverted"),
    CheckConstraint(VISIBILITY_DOMAIN, name="ck_evidence_visibility"),
    CheckConstraint(TENANT_XOR, name="ck_evidence_tenant_xor"),
)

users = Table(
    "users",
    metadata,
    Column("user_id", Text(), primary_key=True),
    Column("username", Text(), nullable=False, unique=True),
    Column("password_hash", Text(), nullable=False),
    Column("tenant_id", Text(), nullable=True),
    Column("role", Text(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "role IN ('tenant_admin', 'system_admin', 'analyst', 'viewer')",
        name="ck_users_role",
    ),
    CheckConstraint(
        "(tenant_id IS NULL AND role = 'system_admin') OR tenant_id IS NOT NULL",
        name="ck_users_tenant_admin_requires_tenant",
    ),
)

job_runs = Table(
    "job_runs",
    metadata,
    Column("job_id", Text(), primary_key=True),
    Column("tenant_id", Text(), nullable=True),
    Column("job_type", Text(), nullable=False),
    Column("status", Text(), nullable=False),
    Column("idempotency_key", Text(), nullable=True),
    Column("payload_sha256", Text(), nullable=True),
    Column("payload_ref", Text(), nullable=False),
    Column("attempt_count", Integer(), nullable=False, server_default="0"),
    Column("max_attempts", Integer(), nullable=False, server_default="5"),
    Column("lease_owner", Text(), nullable=True),
    Column("lease_expires_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("next_retry_at", DateTime(timezone=True)),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("error_code", Text()),
    Column("result_ref", Text()),
    CheckConstraint(
        "status IN ('queued','running','retry_wait','waiting_approval',"
        "'succeeded','partial','failed','cancelled','blocked')",
        name="ck_job_status",
    ),
)

outbox_events = Table(
    "outbox_events",
    metadata,
    Column("event_id", Text(), primary_key=True),
    Column("job_id", Text(), ForeignKey("job_runs.job_id"), nullable=False),
    Column("topic", Text(), nullable=False),
    Column("payload_ref", Text(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("published_at", DateTime(timezone=True), nullable=True),
    Column("delivery_attempts", Integer(), nullable=False, server_default="0"),
    Column("next_delivery_at", DateTime(timezone=True)),
    Column("last_error_code", Text()),
)

job_payloads = Table(
    "job_payloads",
    metadata,
    Column("job_id", Text(), ForeignKey("job_runs.job_id"), primary_key=True),
    Column("payload", LargeBinary(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

job_transitions = Table(
    "job_transitions",
    metadata,
    Column("transition_sequence", BigInteger(), Identity(always=True), primary_key=True),
    Column("job_id", Text(), ForeignKey("job_runs.job_id"), nullable=False),
    Column("attempt_count", Integer(), nullable=False),
    Column("from_status", Text(), nullable=False),
    Column("to_status", Text(), nullable=False),
    Column("reason", Text(), nullable=False),
    Column("changed_at", DateTime(timezone=True), nullable=False),
)

source_cursors = Table(
    "source_cursors",
    metadata,
    Column("source_id", Text(), ForeignKey("sources.source_id"), primary_key=True),
    Column("stream_kind", Text(), primary_key=True),
    Column("cursor_json", JSONB(), nullable=False),
    Column("window_start", DateTime(timezone=True)),
    Column("window_end", DateTime(timezone=True)),
    Column("watermark_published_at", DateTime(timezone=True)),
    Column("last_successful_page", Integer(), nullable=False),
    Column("lease_owner", Text()),
    Column("lease_expires_at", DateTime(timezone=True)),
    Column("generation", Integer(), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

source_page_receipts = Table(
    "source_page_receipts",
    metadata,
    Column("source_id", Text(), primary_key=True),
    Column("stream_kind", Text(), primary_key=True),
    Column("page_key", Text(), primary_key=True),
    Column("input_cursor", JSONB(), nullable=False),
    Column("output_cursor", JSONB(), nullable=False),
    Column("revision_ids", JSONB(), nullable=False),
    Column("failed_job_ids", JSONB(), nullable=False),
    Column("entry_count", Integer(), nullable=False),
    Column("request_sha256", Text(), nullable=True),
    Column("committed_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["source_id", "stream_kind"], ["source_cursors.source_id", "source_cursors.stream_kind"]
    ),
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
    Column("response_content_hash", Text(), ForeignKey("content_objects.content_hash")),
    Column("final_url", Text()),
)

runtime_observations = Table(
    "runtime_observations",
    metadata,
    Column("component", Text(), primary_key=True),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("platform_version", Text(), nullable=False),
    CheckConstraint("component IN ('worker', 'scheduler')", name="ck_runtime_component"),
)
