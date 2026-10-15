"""Persist enrichment workflow relations and irreversible external-call reservations.

Revision ID: 0017_enrichment_job_workflows
Revises: 0016_source_response_receipts
"""

import hashlib

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0017_enrichment_job_workflows"
down_revision = "0016_source_response_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Existing jobs and facts retain authority; metadata stores no duplicate job status."""
    op.create_table(
        "enrichment_workflows",
        sa.Column("workflow_id", sa.Text(), primary_key=True),
        sa.Column("parent_job_id", sa.Text(), sa.ForeignKey("job_runs.job_id"), nullable=False),
        sa.Column("actor_user_id", sa.Text(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("actor_session_hash", sa.Text(), nullable=False),
        sa.Column("actor_tenant_id", sa.Text()),
        sa.Column("actor_role", sa.Text(), nullable=False),
        sa.Column("actor_permission_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("event_id", sa.Text(), sa.ForeignKey("events.event_id"), nullable=False),
        sa.Column("visibility", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text()),
        sa.Column("request_payload", JSONB(), nullable=False),
        sa.Column("request_sha256", sa.Text(), nullable=False),
        sa.Column("rule_version", sa.Text(), nullable=False),
        sa.Column(
            "execution_policy", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "execution_policy_sha256",
            sa.Text(),
            nullable=False,
            server_default=hashlib.sha256(b"{}").hexdigest(),
        ),
        sa.Column("input_context", JSONB()),
        sa.Column("input_fingerprint", sa.Text()),
        sa.Column("initialized_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("parent_job_id", name="uq_enrichment_workflow_parent_job"),
        sa.CheckConstraint(
            "visibility IN ('public','tenant')", name="ck_enrichment_workflow_visibility"
        ),
        sa.CheckConstraint(
            "(visibility='public' AND tenant_id IS NULL) OR "
            "(visibility='tenant' AND tenant_id IS NOT NULL)",
            name="ck_enrichment_workflow_tenant",
        ),
        sa.CheckConstraint(
            "actor_session_hash ~ '^[0-9a-f]{64}$' AND request_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_enrichment_workflow_digests",
        ),
        sa.CheckConstraint(
            "actor_role IN ('system_admin','tenant_admin','analyst','viewer')",
            name="ck_enrichment_workflow_actor_role",
        ),
        sa.CheckConstraint(
            "actor_permission_version>0 AND execution_policy_sha256 ~ '^[0-9a-f]{64}$' AND "
            "jsonb_typeof(execution_policy)='object' "
            "AND octet_length(execution_policy::text)<=16384",
            name="ck_enrichment_workflow_execution_policy",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(request_payload)='object' AND octet_length(request_payload::text)<=8192",
            name="ck_enrichment_workflow_request",
        ),
        sa.CheckConstraint(
            "(input_context IS NULL AND input_fingerprint IS NULL AND initialized_at IS NULL) OR "
            "(input_context IS NOT NULL AND jsonb_typeof(input_context)='object' AND "
            "input_fingerprint IS NOT NULL AND input_fingerprint ~ '^[0-9a-f]{64}$' "
            "AND initialized_at IS NOT NULL)",
            name="ck_enrichment_workflow_initialized",
        ),
    )
    op.create_index(
        "ix_enrichment_workflow_event", "enrichment_workflows", ["event_id", "created_at"]
    )
    op.create_index(
        "ix_enrichment_workflow_actor", "enrichment_workflows", ["actor_user_id", "created_at"]
    )
    op.create_table(
        "enrichment_job_steps",
        sa.Column("job_id", sa.Text(), sa.ForeignKey("job_runs.job_id"), primary_key=True),
        sa.Column(
            "workflow_id",
            sa.Text(),
            sa.ForeignKey("enrichment_workflows.workflow_id"),
            nullable=False,
        ),
        sa.Column("step_key", sa.Text(), nullable=False),
        sa.Column("dimension", sa.Text()),
        sa.Column("provider", sa.Text()),
        sa.Column("output_token_budget", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model_call_reserved_at", sa.DateTime(timezone=True)),
        sa.Column("model_call_completed_at", sa.DateTime(timezone=True)),
        sa.Column("model_trace", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("result_payload", JSONB()),
        sa.Column("result_sha256", sa.Text()),
        sa.Column("result_recorded_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workflow_id", "step_key", name="uq_enrichment_workflow_step"),
        sa.CheckConstraint(
            "dimension IS NULL OR dimension IN "
            "('cvss','epss','kev','cwe','atlas','versions','literature','poc','exposure')",
            name="ck_enrichment_step_dimension",
        ),
        sa.CheckConstraint(
            "(step_key='publication' AND dimension IS NULL AND provider IS NULL) OR "
            "(dimension IS NOT NULL AND step_key=dimension AND provider IS NULL) OR "
            "(dimension IS NOT NULL AND dimension='exposure' AND provider IS NOT NULL "
            "AND provider IN ('hunter','quake') AND "
            "step_key='exposure:' || provider)",
            name="ck_enrichment_step_identity",
        ),
        sa.CheckConstraint(
            "(dimension IN ('atlas','versions','literature','poc') "
            "AND output_token_budget=1024) OR "
            "((dimension IS NULL OR dimension NOT IN ('atlas','versions','literature','poc')) "
            "AND output_token_budget=0)",
            name="ck_enrichment_step_token_budget",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(model_trace)='array' AND octet_length(model_trace::text)<=65536",
            name="ck_enrichment_step_model_trace",
        ),
        sa.CheckConstraint(
            "(dimension IS NOT NULL AND dimension IN ('atlas','versions','literature','poc')) OR "
            "(model_call_reserved_at IS NULL AND model_call_completed_at IS NULL "
            "AND model_trace='[]'::jsonb)",
            name="ck_enrichment_step_model_call_scope",
        ),
        sa.CheckConstraint(
            "model_call_completed_at IS NULL OR (model_call_reserved_at IS NOT NULL AND "
            "model_call_completed_at>=model_call_reserved_at)",
            name="ck_enrichment_step_call_times",
        ),
        sa.CheckConstraint(
            "(result_payload IS NULL AND result_sha256 IS NULL AND result_recorded_at IS NULL) OR "
            "(result_payload IS NOT NULL AND jsonb_typeof(result_payload)='object' AND "
            "octet_length(result_payload::text)<=2097152 AND "
            "result_sha256 IS NOT NULL AND result_sha256 ~ '^[0-9a-f]{64}$' "
            "AND result_recorded_at IS NOT NULL)",
            name="ck_enrichment_step_result",
        ),
    )
    op.create_index("ix_enrichment_steps_workflow", "enrichment_job_steps", ["workflow_id"])


def downgrade() -> None:
    """Paid-call reservations and historical inputs require forward repair or backup recovery."""
    raise RuntimeError("enrichment workflow history requires forward-only recovery")
