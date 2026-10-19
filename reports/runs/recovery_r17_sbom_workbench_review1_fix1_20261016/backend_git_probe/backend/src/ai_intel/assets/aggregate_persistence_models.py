"""R08 immutable safe observations share the authoritative knowledge PostgreSQL metadata."""

from sqlalchemy import DDL, CheckConstraint, Column, DateTime, Index, Table, Text, event
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ai_intel.knowledge.models import metadata

aggregate_observations = Table(
    "r08_aggregate_observations",
    metadata,
    Column("observation_id", UUID(as_uuid=True), primary_key=True),
    Column("schema_version", Text(), nullable=False),
    Column("canonical_json", JSONB(), nullable=False),
    Column("payload_sha256", Text(), nullable=False),
    Column("call_key", Text(), nullable=False),
    Column("provider", Text(), nullable=False),
    Column("query_id", Text(), nullable=False),
    Column("query_version", Text(), nullable=False),
    Column("retrieved_at", DateTime(timezone=True), nullable=False),
    Column("observed_at", DateTime(timezone=True)),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    Column("outcome", Text(), nullable=False),
    Column("error_code", Text()),
    Column("data_mode", Text(), nullable=False),
    Column("fee_status", Text(), nullable=False),
    Column("visibility", Text(), nullable=False),
    Column("tenant_id", Text()),
    Column("scope_key", Text(), nullable=False),
    CheckConstraint("schema_version = 'r08-aggregate-observation-1'", name="ck_r08_schema"),
    CheckConstraint("provider IN ('hunter','quake')", name="ck_r08_provider"),
    CheckConstraint("query_id IN ('ollama','vllm')", name="ck_r08_query"),
    CheckConstraint("query_version = 'r08-product-name-1'", name="ck_r08_query_version"),
    CheckConstraint("data_mode IN ('live','fixture')", name="ck_r08_mode"),
    CheckConstraint("fee_status = 'unknown'", name="ck_r08_fee"),
    CheckConstraint(
        "outcome = 'available' OR error_code IS NOT NULL", name="ck_r08_required_error"
    ),
    CheckConstraint(
        "payload_sha256 ~ '^[0-9a-f]{64}$' AND call_key ~ '^[0-9a-f]{64}$'", name="ck_r08_hashes"
    ),
    CheckConstraint(
        "(visibility='public' AND tenant_id IS NULL AND scope_key='public') OR "
        "(visibility='tenant' AND tenant_id IS NOT NULL AND scope_key='tenant:' || tenant_id)",
        name="ck_r08_scope",
    ),
    CheckConstraint(
        "(outcome='available' AND error_code IS NULL) OR "
        "(outcome='unknown' AND error_code='missing_total') OR "
        "(outcome='unauthorized' AND error_code='provider_unauthorized') OR "
        "(outcome='rate_limited' AND error_code='provider_rate_limited') OR "
        "(outcome='not_configured' AND error_code='credential_missing') OR "
        "(outcome='failed' AND error_code IN "
        "('invalid_total','invalid_response','provider_http_error','provider_error',"
        "'network_error','network_dns_error','network_tls_error','network_timeout',"
        "'network_policy_violation','response_too_large','unsupported_content_type'))",
        name="ck_r08_outcome",
    ),
)

Index(
    "ix_r08_current",
    aggregate_observations.c.call_key,
    aggregate_observations.c.scope_key,
    aggregate_observations.c.retrieved_at.desc(),
    aggregate_observations.c.recorded_at.desc(),
    (aggregate_observations.c.outcome == "available").self_group().asc(),
    aggregate_observations.c.observation_id.desc(),
)

IMMUTABILITY_FUNCTION_DDL = """
CREATE FUNCTION r08_reject_aggregate_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'aggregate observation history is immutable' USING ERRCODE = '55000';
END;
$$
"""
IMMUTABILITY_TRIGGER_DDL = """
CREATE TRIGGER r08_aggregate_observations_immutable
BEFORE UPDATE OR DELETE ON r08_aggregate_observations
FOR EACH ROW EXECUTE FUNCTION r08_reject_aggregate_mutation()
"""
event.listen(aggregate_observations, "after_create", DDL(IMMUTABILITY_FUNCTION_DDL))
event.listen(aggregate_observations, "after_create", DDL(IMMUTABILITY_TRIGGER_DDL))
