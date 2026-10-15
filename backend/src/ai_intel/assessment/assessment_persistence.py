"""Append-only assessment outputs and explicit scope snapshots; T36 dispatch is separate."""

from sqlalchemy import (
    DDL,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Table,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB

from ai_intel.assessment.rule_persistence import condition_rule_versions
from ai_intel.assets.inventory_models import asset_snapshots
from ai_intel.knowledge.models import metadata

assessment_results = Table(
    "assessment_results",
    metadata,
    Column("assessment_id", Text, primary_key=True),
    Column("tenant_id", Text, nullable=False),
    Column("asset_id", Text, nullable=False),
    Column("asset_snapshot_id", Text, nullable=False),
    Column("event_id", Text, ForeignKey("events.event_id"), nullable=False),
    Column("rule_id", Text, nullable=False),
    Column("rule_version", Integer, nullable=False),
    Column("knowledge_epoch", BigInteger),
    Column("scope_epoch_map", JSONB, nullable=False),
    Column("policy_version", Text, nullable=False),
    Column("input_digest", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("freshness", Text, nullable=False),
    Column("result_payload", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["asset_id", "tenant_id", "asset_snapshot_id"],
        [asset_snapshots.c.asset_id, asset_snapshots.c.tenant_id, asset_snapshots.c.snapshot_id],
        name="fk_assessment_asset_snapshot_tenant",
    ),
    ForeignKeyConstraint(
        ["rule_id", "rule_version"],
        [condition_rule_versions.c.rule_id, condition_rule_versions.c.version],
        name="fk_assessment_rule_version",
    ),
    UniqueConstraint(
        "tenant_id",
        "asset_snapshot_id",
        "rule_id",
        "rule_version",
        "input_digest",
        "policy_version",
        name="uq_assessment_execution",
    ),
    CheckConstraint("input_digest ~ '^[0-9a-f]{64}$'", name="ck_assessment_input_digest"),
    CheckConstraint("freshness IN ('current','stale','unknown')", name="ck_assessment_freshness"),
    CheckConstraint(
        "status IN ('supported_applicability','excluded_with_evidence',"
        "'insufficient_evidence','conflicting_evidence')",
        name="ck_assessment_status",
    ),
    CheckConstraint("jsonb_typeof(result_payload)='object'", name="ck_assessment_payload"),
)
Index(
    "ix_assessment_tenant_asset",
    assessment_results.c.tenant_id,
    assessment_results.c.asset_id,
    assessment_results.c.created_at,
)

assessment_scope_watches = Table(
    "assessment_scope_watches",
    metadata,
    Column("assessment_id", Text, ForeignKey("assessment_results.assessment_id"), primary_key=True),
    Column("tenant_id", Text, nullable=False),
    Column("event_ids", JSONB, nullable=False),
    Column("package_keys", JSONB, nullable=False),
    Column("rule_id", Text, nullable=False),
    Column("rule_version", Integer, nullable=False),
    Column("rule_kind", Text, nullable=False),
    Column("scope_epoch_map", JSONB, nullable=False),
    Column("selected_rule_ids", JSONB, nullable=False),
    Column("no_published_rule", Boolean, nullable=False),
    CheckConstraint("jsonb_array_length(event_ids)>0", name="ck_assessment_watch_event"),
)
for _table in (assessment_results, assessment_scope_watches):
    event.listen(
        _table,
        "after_create",
        DDL(
            f"CREATE TRIGGER {_table.name}_immutable BEFORE UPDATE OR DELETE ON {_table.name} "
            "FOR EACH ROW EXECUTE FUNCTION r11_require_append_only();"
        ),
    )

ASSESSMENT_TABLES = (assessment_results, assessment_scope_watches)
