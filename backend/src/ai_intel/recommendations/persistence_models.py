"""Four PG tables; root-owned 0027 migration installs the immutable-content triggers."""

from sqlalchemy import (
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
)
from sqlalchemy.dialects.postgresql import JSONB

from ai_intel.knowledge.models import metadata
from ai_intel.knowledge.persistence_models import events

r15_subscriptions = Table(
    "r15_subscriptions",
    metadata,
    Column("id", Text, primary_key=True),
    Column("tenant_id", Text, nullable=False),
    Column("user_id", Text, ForeignKey("users.user_id"), nullable=False),
    Column("version", Integer, nullable=False),
    Column("enabled", Boolean, nullable=False),
    Column("spec_payload", JSONB, nullable=False),
    Column("spec_sha256", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("id", "tenant_id", "user_id", name="uq_r15_subscription_owner"),
    CheckConstraint("version >= 1", name="ck_r15_subscription_version"),
    CheckConstraint("jsonb_typeof(spec_payload)='object'", name="ck_r15_subscription_spec"),
    CheckConstraint("spec_sha256 ~ '^[0-9a-f]{64}$'", name="ck_r15_subscription_sha"),
)
Index(
    "ix_r15_subscription_owner",
    r15_subscriptions.c.tenant_id,
    r15_subscriptions.c.user_id,
    r15_subscriptions.c.created_at,
)

r15_generations = Table(
    "r15_generations",
    metadata,
    Column("id", Text, primary_key=True),
    Column("subscription_id", Text, nullable=False),
    Column("tenant_id", Text, nullable=False),
    Column("user_id", Text, nullable=False),
    Column("subscription_version", Integer, nullable=False),
    Column("cutoff_at", DateTime(timezone=True), nullable=False),
    Column("input_sha256", Text, nullable=False),
    Column("policy_version", Text, nullable=False),
    Column("scope_epochs", JSONB, nullable=False),
    Column("result_payload", JSONB, nullable=False),
    Column("content_sha256", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["subscription_id", "tenant_id", "user_id"],
        ["r15_subscriptions.id", "r15_subscriptions.tenant_id", "r15_subscriptions.user_id"],
        name="fk_r15_generation_owner",
    ),
    UniqueConstraint(
        "id", "subscription_id", "tenant_id", "user_id", name="uq_r15_generation_owner"
    ),
    UniqueConstraint(
        "subscription_id",
        "subscription_version",
        "input_sha256",
        "policy_version",
        name="uq_r15_generation_execution",
    ),
    CheckConstraint("subscription_version >= 1", name="ck_r15_generation_version"),
    CheckConstraint(
        "input_sha256 ~ '^[0-9a-f]{64}$' AND content_sha256 ~ '^[0-9a-f]{64}$'",
        name="ck_r15_generation_sha",
    ),
    CheckConstraint(
        "jsonb_typeof(scope_epochs)='object' AND jsonb_typeof(result_payload)='object'",
        name="ck_r15_generation_payload",
    ),
)

r15_recommendations = Table(
    "r15_recommendations",
    metadata,
    Column("id", Text, primary_key=True),
    Column("subscription_id", Text, nullable=False),
    Column("tenant_id", Text, nullable=False),
    Column("user_id", Text, nullable=False),
    Column("generation_id", Text, nullable=False),
    Column("event_id", Text, ForeignKey(events.c.event_id), nullable=False),
    Column("material_version", Text, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("content_sha256", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("read_at", DateTime(timezone=True)),
    Column("current_status", Text, nullable=False),
    Column("current_reason", Text, nullable=False),
    Column("current_checked_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["generation_id", "subscription_id", "tenant_id", "user_id"],
        [
            "r15_generations.id",
            "r15_generations.subscription_id",
            "r15_generations.tenant_id",
            "r15_generations.user_id",
        ],
        name="fk_r15_recommendation_generation_owner",
    ),
    UniqueConstraint(
        "subscription_id", "event_id", "material_version", name="uq_r15_recommendation_material"
    ),
    CheckConstraint(
        "material_version ~ '^[0-9a-f]{64}$' AND content_sha256 ~ '^[0-9a-f]{64}$'",
        name="ck_r15_recommendation_sha",
    ),
    CheckConstraint("jsonb_typeof(payload)='object'", name="ck_r15_recommendation_payload"),
    CheckConstraint(
        "current_status IN ('current','stale','withdrawn','unknown')",
        name="ck_r15_recommendation_current",
    ),
)
Index(
    "ix_r15_recommendation_owner",
    r15_recommendations.c.tenant_id,
    r15_recommendations.c.user_id,
    r15_recommendations.c.created_at,
)

r15_reports = Table(
    "r15_reports",
    metadata,
    Column("id", Text, primary_key=True),
    Column("subscription_id", Text, nullable=False),
    Column("tenant_id", Text, nullable=False),
    Column("user_id", Text, nullable=False),
    Column("generation_id", Text, nullable=False),
    Column("frequency", Text, nullable=False),
    Column("cutoff_at", DateTime(timezone=True), nullable=False),
    Column("generated_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("content_sha256", Text, nullable=False),
    Column("current_status", Text, nullable=False),
    Column("current_reason", Text, nullable=False),
    Column("current_checked_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["generation_id", "subscription_id", "tenant_id", "user_id"],
        [
            "r15_generations.id",
            "r15_generations.subscription_id",
            "r15_generations.tenant_id",
            "r15_generations.user_id",
        ],
        name="fk_r15_report_generation_owner",
    ),
    UniqueConstraint("generation_id", "frequency", "cutoff_at", name="uq_r15_report_execution"),
    CheckConstraint("frequency IN ('day','week')", name="ck_r15_report_frequency"),
    CheckConstraint(
        "content_sha256 ~ '^[0-9a-f]{64}$' AND jsonb_typeof(payload)='object'",
        name="ck_r15_report_payload",
    ),
    CheckConstraint(
        "current_status IN ('current','stale','withdrawn','unknown')", name="ck_r15_report_current"
    ),
)
Index(
    "ix_r15_report_owner",
    r15_reports.c.tenant_id,
    r15_reports.c.user_id,
    r15_reports.c.generated_at,
)

R15_TABLES = (r15_subscriptions, r15_generations, r15_recommendations, r15_reports)
