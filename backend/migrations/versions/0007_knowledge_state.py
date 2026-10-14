"""R02已有claims增量与可重放知识发布收据，不覆盖历史原文或旧事实。

Revision ID: 0007_knowledge_state
Revises: 0006_auth_state
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007_knowledge_state"
down_revision = "0006_auth_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """旧数据保留为legacy，只有经过验证的新发布才获得可用provenance。"""
    for column in (
        sa.Column("object_json", JSONB(), nullable=True),
        sa.Column("value_kind", sa.Text(), nullable=False, server_default="text"),
        sa.Column(
            "provenance_status", sa.Text(), nullable=False, server_default="legacy_unverified"
        ),
        sa.Column("field_fingerprint", sa.Text(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_revision_id", sa.Text(), sa.ForeignKey("document_revisions.revision_id")),
    ):
        op.add_column("claims", column)
    op.create_index("ix_claims_field_fingerprint", "claims", ["field_fingerprint"], unique=True)
    op.add_column(
        "evidence",
        sa.Column(
            "coordinate_version", sa.Text(), nullable=False, server_default="legacy_unverified"
        ),
    )
    op.create_table(
        "claim_evidence",
        sa.Column("claim_id", sa.Text(), sa.ForeignKey("claims.claim_id"), primary_key=True),
        sa.Column(
            "evidence_id", sa.Text(), sa.ForeignKey("evidence.evidence_id"), primary_key=True
        ),
        sa.Column("support_kind", sa.Text(), nullable=False),
        sa.Column("validation_status", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "support_kind IN ('supports','refutes','context')",
            name="ck_claim_evidence_support_kind",
        ),
        sa.CheckConstraint(
            "validation_status IN ('validated','unverified')",
            name="ck_claim_evidence_validation_status",
        ),
    )
    op.create_table(
        "claim_assertions",
        sa.Column("assertion_id", sa.Text(), primary_key=True),
        sa.Column("claim_id", sa.Text(), sa.ForeignKey("claims.claim_id"), nullable=False),
        sa.Column("source_id", sa.Text(), sa.ForeignKey("sources.source_id"), nullable=False),
        sa.Column(
            "revision_id",
            sa.Text(),
            sa.ForeignKey("document_revisions.revision_id"),
            nullable=False,
        ),
        sa.Column("json_path", sa.Text(), nullable=False),
        sa.Column("scoring_authority", sa.Text(), nullable=False),
        sa.Column("assertion_kind", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "claim_id",
            "source_id",
            "revision_id",
            "json_path",
            "scoring_authority",
            name="uq_claim_assertion_source",
        ),
    )
    op.create_table(
        "claim_status_history",
        sa.Column("history_id", sa.Text(), primary_key=True),
        sa.Column("transition_sequence", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("claim_id", sa.Text(), sa.ForeignKey("claims.claim_id"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "claim_relations",
        sa.Column("relation_id", sa.Text(), primary_key=True),
        sa.Column("left_claim_id", sa.Text(), sa.ForeignKey("claims.claim_id"), nullable=False),
        sa.Column("right_claim_id", sa.Text(), sa.ForeignKey("claims.claim_id"), nullable=False),
        sa.Column("relation_type", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "left_claim_id", "right_claim_id", "relation_type", name="uq_claim_relation"
        ),
        sa.CheckConstraint(
            "relation_type IN ('supersedes','disputed')", name="ck_claim_relation_type"
        ),
    )
    op.create_table(
        "entities",
        sa.Column("entity_id", sa.Text(), primary_key=True),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("ecosystem", sa.Text(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("scope_key", sa.Text(), nullable=False),
        sa.Column("visibility", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "scope_key", "entity_type", "ecosystem", "canonical_name", name="uq_entity_key"
        ),
        sa.CheckConstraint("visibility IN ('public','tenant')", name="ck_entities_visibility"),
        sa.CheckConstraint(
            "(visibility='public' AND tenant_id IS NULL) OR "
            "(visibility='tenant' AND tenant_id IS NOT NULL)",
            name="ck_entities_scope",
        ),
    )
    op.create_table(
        "entity_aliases",
        sa.Column("alias_id", sa.Text(), primary_key=True),
        sa.Column("entity_id", sa.Text(), sa.ForeignKey("entities.entity_id"), nullable=False),
        sa.Column("source_id", sa.Text(), sa.ForeignKey("sources.source_id"), nullable=False),
        sa.Column(
            "revision_id",
            sa.Text(),
            sa.ForeignKey("document_revisions.revision_id"),
            nullable=False,
        ),
        sa.Column("evidence_id", sa.Text(), sa.ForeignKey("evidence.evidence_id"), nullable=False),
        sa.Column("alias_value", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "entity_id", "alias_value", "evidence_id", name="uq_entity_alias_evidence"
        ),
    )
    op.create_table(
        "events",
        sa.Column("event_id", sa.Text(), primary_key=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("scope_key", sa.Text(), nullable=False),
        sa.Column("visibility", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("business_version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("visibility IN ('public','tenant')", name="ck_events_visibility"),
        sa.CheckConstraint(
            "(visibility='public' AND tenant_id IS NULL) OR "
            "(visibility='tenant' AND tenant_id IS NOT NULL)",
            name="ck_events_scope",
        ),
    )
    op.create_table(
        "event_external_ids",
        sa.Column("event_id", sa.Text(), sa.ForeignKey("events.event_id"), primary_key=True),
        sa.Column("id_type", sa.Text(), primary_key=True),
        sa.Column("id_value", sa.Text(), primary_key=True),
        sa.Column("scope_key", sa.Text(), nullable=False),
        sa.UniqueConstraint("scope_key", "id_type", "id_value", name="uq_event_external_scope"),
    )
    op.create_table(
        "event_documents",
        sa.Column("event_id", sa.Text(), sa.ForeignKey("events.event_id"), primary_key=True),
        sa.Column(
            "revision_id",
            sa.Text(),
            sa.ForeignKey("document_revisions.revision_id"),
            primary_key=True,
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("associated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "event_operations",
        sa.Column("operation_id", sa.Text(), primary_key=True),
        sa.Column("operation_type", sa.Text(), nullable=False),
        sa.Column("source_event_id", sa.Text(), sa.ForeignKey("events.event_id"), nullable=False),
        sa.Column("target_event_id", sa.Text(), sa.ForeignKey("events.event_id"), nullable=False),
        sa.Column(
            "inverse_operation_id", sa.Text(), sa.ForeignKey("event_operations.operation_id")
        ),
        sa.Column("source_revision_ids", JSONB(), nullable=False),
        sa.Column("target_revision_ids", JSONB(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("operation_type IN ('merge','undo')", name="ck_event_operation_type"),
    )
    op.create_table(
        "change_events",
        sa.Column("change_id", sa.Text(), primary_key=True),
        sa.Column("scope_key", sa.Text(), nullable=False),
        sa.Column("epoch", sa.BigInteger(), nullable=False),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column("entity_ids", JSONB(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scope_key", "epoch", name="uq_change_scope_epoch"),
    )
    op.create_table(
        "publication_receipts",
        sa.Column("receipt_id", sa.Text(), primary_key=True),
        sa.Column("scope_key", sa.Text(), nullable=False),
        sa.Column("publication_key", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.Text(), nullable=False),
        sa.Column("claim_ids", JSONB(), nullable=False),
        sa.Column("epoch", sa.BigInteger(), nullable=False),
        sa.Column("job_id", sa.Text(), sa.ForeignKey("job_runs.job_id"), nullable=False),
        sa.Column("outbox_id", sa.Text(), sa.ForeignKey("outbox_events.event_id"), nullable=False),
        sa.Column("change_id", sa.Text(), sa.ForeignKey("change_events.change_id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scope_key", "publication_key", name="uq_publication_key"),
    )
    for table, columns in (
        ("claim_assertions", ["source_id", "revision_id"]),
        ("claim_status_history", ["claim_id", "changed_at"]),
        ("entity_aliases", ["entity_id", "alias_value"]),
        ("change_events", ["scope_key", "created_at"]),
    ):
        op.create_index("ix_" + table + "_lookup", table, columns)


def downgrade() -> None:
    """有数据时采用前向修复/备份恢复，不自动运行此破坏性降级。"""
    for table in (
        "publication_receipts",
        "change_events",
        "event_operations",
        "event_documents",
        "event_external_ids",
        "events",
        "entity_aliases",
        "entities",
        "claim_relations",
        "claim_status_history",
        "claim_assertions",
        "claim_evidence",
    ):
        op.drop_table(table)
    op.drop_column("evidence", "coordinate_version")
    op.drop_index("ix_claims_field_fingerprint", table_name="claims")
    for column in (
        "source_revision_id",
        "schema_version",
        "is_current",
        "field_fingerprint",
        "provenance_status",
        "value_kind",
        "object_json",
    ):
        op.drop_column("claims", column)
