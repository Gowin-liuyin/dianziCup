"""Immutable authenticated job ownership; job status and facts remain in existing PG tables."""

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Table, Text
from sqlalchemy.dialects.postgresql import JSONB

from ai_intel.knowledge.models import metadata

revalidation_job_bindings = Table(
    "revalidation_job_bindings",
    metadata,
    Column("job_id", Text, ForeignKey("job_runs.job_id"), primary_key=True),
    Column("actor_user_id", Text, ForeignKey("users.user_id"), nullable=False),
    Column("tenant_id", Text),
    Column("authorized_role", Text, nullable=False),
    Column("actor_reference", JSONB, nullable=False),
    Column("payload_sha256", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "authorized_role IN ('tenant_admin','system_admin','analyst','viewer')",
        name="ck_revalidation_actor_role",
    ),
    CheckConstraint("jsonb_typeof(actor_reference)='object'", name="ck_revalidation_actor_object"),
    CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_revalidation_payload_digest"),
)
