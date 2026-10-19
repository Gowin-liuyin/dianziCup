"""Workflow relations and external-call receipts reuse PostgreSQL's existing job authority."""

import hashlib

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import JSONB

from ai_intel.knowledge.models import TENANT_XOR, VISIBILITY_DOMAIN, metadata

enrichment_workflows = Table(
    "enrichment_workflows",
    metadata,
    Column("workflow_id", Text, primary_key=True),
    Column("parent_job_id", Text, ForeignKey("job_runs.job_id"), nullable=False),
    Column("actor_user_id", Text, ForeignKey("users.user_id"), nullable=False),
    Column("actor_session_hash", Text, nullable=False),
    Column("actor_tenant_id", Text),
    Column("actor_role", Text, nullable=False),
    Column("actor_permission_version", Integer, nullable=False, server_default="1"),
    Column("event_id", Text, ForeignKey("events.event_id"), nullable=False),
    Column("visibility", Text, nullable=False),
    Column("tenant_id", Text),
    Column("request_payload", JSONB, nullable=False),
    Column("request_sha256", Text, nullable=False),
    Column("rule_version", Text, nullable=False),
    Column("execution_policy", JSONB, nullable=False, server_default="{}"),
    Column(
        "execution_policy_sha256",
        Text,
        nullable=False,
        server_default=hashlib.sha256(b"{}").hexdigest(),
    ),
    Column("input_context", JSONB),
    Column("input_fingerprint", Text),
    Column("initialized_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("parent_job_id", name="uq_enrichment_workflow_parent_job"),
    CheckConstraint(VISIBILITY_DOMAIN, name="ck_enrichment_workflow_visibility"),
    CheckConstraint(TENANT_XOR, name="ck_enrichment_workflow_tenant"),
    CheckConstraint(
        "actor_session_hash ~ '^[0-9a-f]{64}$' AND request_sha256 ~ '^[0-9a-f]{64}$'",
        name="ck_enrichment_workflow_digests",
    ),
    CheckConstraint(
        "actor_role IN ('system_admin','tenant_admin','analyst','viewer')",
        name="ck_enrichment_workflow_actor_role",
    ),
    CheckConstraint(
        "actor_permission_version>0 AND execution_policy_sha256 ~ '^[0-9a-f]{64}$' AND "
        "jsonb_typeof(execution_policy)='object' AND octet_length(execution_policy::text)<=16384",
        name="ck_enrichment_workflow_execution_policy",
    ),
    CheckConstraint(
        "jsonb_typeof(request_payload)='object' AND octet_length(request_payload::text)<=8192",
        name="ck_enrichment_workflow_request",
    ),
    CheckConstraint(
        "(input_context IS NULL AND input_fingerprint IS NULL AND initialized_at IS NULL) OR "
        "(input_context IS NOT NULL AND jsonb_typeof(input_context)='object' AND "
        "input_fingerprint IS NOT NULL AND input_fingerprint ~ '^[0-9a-f]{64}$' "
        "AND initialized_at IS NOT NULL)",
        name="ck_enrichment_workflow_initialized",
    ),
)
Index(
    "ix_enrichment_workflow_event",
    enrichment_workflows.c.event_id,
    enrichment_workflows.c.created_at,
)
Index(
    "ix_enrichment_workflow_actor",
    enrichment_workflows.c.actor_user_id,
    enrichment_workflows.c.created_at,
)

enrichment_job_steps = Table(
    "enrichment_job_steps",
    metadata,
    Column("job_id", Text, ForeignKey("job_runs.job_id"), primary_key=True),
    Column("workflow_id", Text, ForeignKey("enrichment_workflows.workflow_id"), nullable=False),
    Column("step_key", Text, nullable=False),
    Column("dimension", Text),
    Column("provider", Text),
    Column("output_token_budget", Integer, nullable=False, server_default="0"),
    Column("model_call_reserved_at", DateTime(timezone=True)),
    Column("model_call_completed_at", DateTime(timezone=True)),
    Column("model_trace", JSONB, nullable=False, server_default="[]"),
    Column("result_payload", JSONB),
    Column("result_sha256", Text),
    Column("result_recorded_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("workflow_id", "step_key", name="uq_enrichment_workflow_step"),
    CheckConstraint(
        "dimension IS NULL OR dimension IN "
        "('cvss','epss','kev','cwe','atlas','versions','literature','poc','exposure')",
        name="ck_enrichment_step_dimension",
    ),
    CheckConstraint(
        "(step_key='publication' AND dimension IS NULL AND provider IS NULL) OR "
        "(dimension IS NOT NULL AND step_key=dimension AND provider IS NULL) OR "
        "(dimension IS NOT NULL AND dimension='exposure' AND provider IS NOT NULL "
        "AND provider IN ('hunter','quake') AND "
        "step_key='exposure:' || provider)",
        name="ck_enrichment_step_identity",
    ),
    CheckConstraint(
        "(dimension IN ('atlas','versions','literature','poc') AND output_token_budget=1024) OR "
        "((dimension IS NULL OR dimension NOT IN ('atlas','versions','literature','poc')) "
        "AND output_token_budget=0)",
        name="ck_enrichment_step_token_budget",
    ),
    CheckConstraint(
        "jsonb_typeof(model_trace)='array' AND octet_length(model_trace::text)<=65536",
        name="ck_enrichment_step_model_trace",
    ),
    CheckConstraint(
        "(dimension IS NOT NULL AND dimension IN ('atlas','versions','literature','poc')) OR "
        "(model_call_reserved_at IS NULL AND model_call_completed_at IS NULL "
        "AND model_trace='[]'::jsonb)",
        name="ck_enrichment_step_model_call_scope",
    ),
    CheckConstraint(
        "model_call_completed_at IS NULL OR "
        "(model_call_reserved_at IS NOT NULL AND "
        "model_call_completed_at>=model_call_reserved_at)",
        name="ck_enrichment_step_call_times",
    ),
    CheckConstraint(
        "(result_payload IS NULL AND result_sha256 IS NULL AND result_recorded_at IS NULL) OR "
        "(result_payload IS NOT NULL AND jsonb_typeof(result_payload)='object' AND "
        "octet_length(result_payload::text)<=2097152 AND "
        "result_sha256 IS NOT NULL AND result_sha256 ~ '^[0-9a-f]{64}$' "
        "AND result_recorded_at IS NOT NULL)",
        name="ck_enrichment_step_result",
    ),
)
Index("ix_enrichment_steps_workflow", enrichment_job_steps.c.workflow_id)
