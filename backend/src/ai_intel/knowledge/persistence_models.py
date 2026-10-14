"""0007已有claims及知识发布表映射；与运行中的唯一PG事实库共享metadata。"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB

from ai_intel.knowledge.models import metadata

claims = Table(
    "claims",
    metadata,
    Column("claim_id", Text(), primary_key=True),
    Column("subject", Text(), nullable=False),
    Column("predicate", Text(), nullable=False),
    Column("object_value", Text(), nullable=False),
    Column("claim_status", Text(), nullable=False),
    Column("claim_origin", Text(), nullable=False),
    Column("condition_value", Text(), nullable=False),
    Column("freshness", Text(), nullable=False),
    Column("asserted_at", DateTime(timezone=True), nullable=False),
    Column("observed_at", DateTime(timezone=True)),
    Column("visibility", Text(), nullable=False),
    Column("tenant_id", Text()),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("object_json", JSONB()),
    Column("value_kind", Text(), nullable=False, server_default="text"),
    Column("provenance_status", Text(), nullable=False, server_default="legacy_unverified"),
    Column("field_fingerprint", Text()),
    Column("is_current", Boolean(), nullable=False, server_default="true"),
    Column("schema_version", Integer(), nullable=False, server_default="1"),
    Column("source_revision_id", Text(), ForeignKey("document_revisions.revision_id")),
)

claim_evidence = Table(
    "claim_evidence",
    metadata,
    Column("claim_id", Text(), ForeignKey("claims.claim_id"), primary_key=True),
    Column("evidence_id", Text(), ForeignKey("evidence.evidence_id"), primary_key=True),
    Column("support_kind", Text(), nullable=False),
    Column("validation_status", Text(), nullable=False),
)

claim_assertions = Table(
    "claim_assertions",
    metadata,
    Column("assertion_id", Text(), primary_key=True),
    Column("claim_id", Text(), ForeignKey("claims.claim_id"), nullable=False),
    Column("source_id", Text(), ForeignKey("sources.source_id"), nullable=False),
    Column("revision_id", Text(), ForeignKey("document_revisions.revision_id"), nullable=False),
    Column("json_path", Text(), nullable=False),
    Column("scoring_authority", Text(), nullable=False),
    Column("assertion_kind", Text(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

claim_status_history = Table(
    "claim_status_history",
    metadata,
    Column("history_id", Text(), primary_key=True),
    Column("transition_sequence", BigInteger(), Identity(always=True), nullable=False),
    Column("claim_id", Text(), ForeignKey("claims.claim_id"), nullable=False),
    Column("status", Text(), nullable=False),
    Column("reason", Text(), nullable=False),
    Column("changed_at", DateTime(timezone=True), nullable=False),
)

claim_relations = Table(
    "claim_relations",
    metadata,
    Column("relation_id", Text(), primary_key=True),
    Column("left_claim_id", Text(), ForeignKey("claims.claim_id"), nullable=False),
    Column("right_claim_id", Text(), ForeignKey("claims.claim_id"), nullable=False),
    Column("relation_type", Text(), nullable=False),
    Column("reason", Text(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

entities = Table(
    "entities",
    metadata,
    Column("entity_id", Text(), primary_key=True),
    Column("entity_type", Text(), nullable=False),
    Column("ecosystem", Text(), nullable=False),
    Column("canonical_name", Text(), nullable=False),
    Column("scope_key", Text(), nullable=False),
    Column("visibility", Text(), nullable=False),
    Column("tenant_id", Text()),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

entity_aliases = Table(
    "entity_aliases",
    metadata,
    Column("alias_id", Text(), primary_key=True),
    Column("entity_id", Text(), ForeignKey("entities.entity_id"), nullable=False),
    Column("source_id", Text(), ForeignKey("sources.source_id"), nullable=False),
    Column("revision_id", Text(), ForeignKey("document_revisions.revision_id"), nullable=False),
    Column("evidence_id", Text(), ForeignKey("evidence.evidence_id"), nullable=False),
    Column("alias_value", Text(), nullable=False),
    Column("status", Text(), nullable=False),
    Column("valid_from", DateTime(timezone=True)),
    Column("valid_to", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

events = Table(
    "events",
    metadata,
    Column("event_id", Text(), primary_key=True),
    Column("event_type", Text(), nullable=False),
    Column("title", Text(), nullable=False),
    Column("scope_key", Text(), nullable=False),
    Column("visibility", Text(), nullable=False),
    Column("tenant_id", Text()),
    Column("status", Text(), nullable=False),
    Column("first_seen_at", DateTime(timezone=True), nullable=False),
    Column("business_version", Integer(), nullable=False, server_default="1"),
)

event_external_ids = Table(
    "event_external_ids",
    metadata,
    Column("event_id", Text(), ForeignKey("events.event_id"), primary_key=True),
    Column("id_type", Text(), primary_key=True),
    Column("id_value", Text(), primary_key=True),
    Column("scope_key", Text(), nullable=False),
)

event_documents = Table(
    "event_documents",
    metadata,
    Column("event_id", Text(), ForeignKey("events.event_id"), primary_key=True),
    Column("revision_id", Text(), ForeignKey("document_revisions.revision_id"), primary_key=True),
    Column("active", Boolean(), nullable=False, server_default="true"),
    Column("associated_at", DateTime(timezone=True), nullable=False),
    Column("superseded_at", DateTime(timezone=True)),
)

event_operations = Table(
    "event_operations",
    metadata,
    Column("operation_id", Text(), primary_key=True),
    Column("operation_type", Text(), nullable=False),
    Column("source_event_id", Text(), ForeignKey("events.event_id"), nullable=False),
    Column("target_event_id", Text(), ForeignKey("events.event_id"), nullable=False),
    Column("source_business_version", Integer()),
    Column("target_business_version", Integer()),
    Column("inverse_operation_id", Text(), ForeignKey("event_operations.operation_id")),
    Column("source_revision_ids", JSONB(), nullable=False),
    Column("target_revision_ids", JSONB(), nullable=False),
    Column("reason", Text(), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
)

change_events = Table(
    "change_events",
    metadata,
    Column("change_id", Text(), primary_key=True),
    Column("scope_key", Text(), nullable=False),
    Column("epoch", BigInteger(), nullable=False),
    Column("change_type", Text(), nullable=False),
    Column("entity_ids", JSONB(), nullable=False),
    Column("payload", JSONB(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

publication_receipts = Table(
    "publication_receipts",
    metadata,
    Column("receipt_id", Text(), primary_key=True),
    Column("scope_key", Text(), nullable=False),
    Column("publication_key", Text(), nullable=False),
    Column("payload_sha256", Text(), nullable=False),
    Column("claim_ids", JSONB(), nullable=False),
    Column("epoch", BigInteger(), nullable=False),
    Column("job_id", Text(), ForeignKey("job_runs.job_id"), nullable=False),
    Column("outbox_id", Text(), ForeignKey("outbox_events.event_id"), nullable=False),
    Column("change_id", Text(), ForeignKey("change_events.change_id"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
