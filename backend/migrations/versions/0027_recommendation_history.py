"""Persist approved subscription ownership and immutable recommendation/report history."""

from alembic import op

revision = "0027_recommendation_history"
down_revision = "0026_api_key_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Install frozen tables and narrowly mutable current/read overlays."""
    op.execute(
        """
CREATE TABLE r15_subscriptions (
	id TEXT NOT NULL,

	tenant_id TEXT NOT NULL,

	user_id TEXT NOT NULL,

	version INTEGER NOT NULL,

	enabled BOOLEAN NOT NULL,

	spec_payload JSONB NOT NULL,

	spec_sha256 TEXT NOT NULL,

	created_at TIMESTAMP WITH TIME ZONE NOT NULL,

	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,

	PRIMARY KEY (id),

	CONSTRAINT uq_r15_subscription_owner UNIQUE (id,
 tenant_id,
 user_id),

	CONSTRAINT ck_r15_subscription_version CHECK (version >= 1),

	CONSTRAINT ck_r15_subscription_spec CHECK (jsonb_typeof(spec_payload)='object'),

	CONSTRAINT ck_r15_subscription_sha CHECK (spec_sha256 ~ '^[0-9a-f]{64}$'),

	FOREIGN KEY(user_id)
REFERENCES users (user_id)
)
        """
    )
    op.execute(
        """
CREATE INDEX ix_r15_subscription_owner ON r15_subscriptions (tenant_id,
 user_id,
 created_at)
        """
    )
    op.execute(
        """
CREATE TABLE r15_generations (
	id TEXT NOT NULL,

	subscription_id TEXT NOT NULL,

	tenant_id TEXT NOT NULL,

	user_id TEXT NOT NULL,

	subscription_version INTEGER NOT NULL,

	cutoff_at TIMESTAMP WITH TIME ZONE NOT NULL,

	input_sha256 TEXT NOT NULL,

	policy_version TEXT NOT NULL,

	scope_epochs JSONB NOT NULL,

	result_payload JSONB NOT NULL,

	content_sha256 TEXT NOT NULL,

	created_at TIMESTAMP WITH TIME ZONE NOT NULL,

	PRIMARY KEY (id),

	CONSTRAINT fk_r15_generation_owner FOREIGN KEY(subscription_id,
 tenant_id,
 user_id)
REFERENCES r15_subscriptions (id,
 tenant_id,
 user_id),

	CONSTRAINT uq_r15_generation_owner UNIQUE (id,
 subscription_id,
 tenant_id,
 user_id),

	CONSTRAINT uq_r15_generation_execution UNIQUE (subscription_id,
 subscription_version,
 input_sha256,
 policy_version),

	CONSTRAINT ck_r15_generation_version CHECK (subscription_version >= 1),

	CONSTRAINT ck_r15_generation_sha CHECK (input_sha256 ~ '^[0-9a-f]{64}$'
AND content_sha256 ~ '^[0-9a-f]{64}$'),

	CONSTRAINT ck_r15_generation_payload CHECK (jsonb_typeof(scope_epochs)='object'
AND jsonb_typeof(result_payload)='object')
)
        """
    )
    op.execute(
        """
CREATE TABLE r15_recommendations (
	id TEXT NOT NULL,

	subscription_id TEXT NOT NULL,

	tenant_id TEXT NOT NULL,

	user_id TEXT NOT NULL,

	generation_id TEXT NOT NULL,

	event_id TEXT NOT NULL,

	material_version TEXT NOT NULL,

	payload JSONB NOT NULL,

	content_sha256 TEXT NOT NULL,

	created_at TIMESTAMP WITH TIME ZONE NOT NULL,

	read_at TIMESTAMP WITH TIME ZONE,

	current_status TEXT NOT NULL,

	current_reason TEXT NOT NULL,

	current_checked_at TIMESTAMP WITH TIME ZONE NOT NULL,

	PRIMARY KEY (id),

	CONSTRAINT fk_r15_recommendation_generation_owner FOREIGN KEY(generation_id,
 subscription_id,
 tenant_id,
 user_id)
REFERENCES r15_generations (id,
 subscription_id,
 tenant_id,
 user_id),

	CONSTRAINT uq_r15_recommendation_material UNIQUE (subscription_id,
 event_id,
 material_version),

	CONSTRAINT ck_r15_recommendation_sha CHECK (material_version ~ '^[0-9a-f]{64}$'
AND content_sha256 ~ '^[0-9a-f]{64}$'),

	CONSTRAINT ck_r15_recommendation_payload CHECK (jsonb_typeof(payload)='object'),

	CONSTRAINT ck_r15_recommendation_current CHECK (current_status IN ('current',
'stale',
'withdrawn',
'unknown')),

	FOREIGN KEY(event_id)
REFERENCES events (event_id)
)
        """
    )
    op.execute(
        """
CREATE INDEX ix_r15_recommendation_owner ON r15_recommendations (tenant_id,
 user_id,
 created_at)
        """
    )
    op.execute(
        """
CREATE TABLE r15_reports (
	id TEXT NOT NULL,

	subscription_id TEXT NOT NULL,

	tenant_id TEXT NOT NULL,

	user_id TEXT NOT NULL,

	generation_id TEXT NOT NULL,

	frequency TEXT NOT NULL,

	cutoff_at TIMESTAMP WITH TIME ZONE NOT NULL,

	generated_at TIMESTAMP WITH TIME ZONE NOT NULL,

	payload JSONB NOT NULL,

	content_sha256 TEXT NOT NULL,

	current_status TEXT NOT NULL,

	current_reason TEXT NOT NULL,

	current_checked_at TIMESTAMP WITH TIME ZONE NOT NULL,

	PRIMARY KEY (id),

	CONSTRAINT fk_r15_report_generation_owner FOREIGN KEY(generation_id,
 subscription_id,
 tenant_id,
 user_id)
REFERENCES r15_generations (id,
 subscription_id,
 tenant_id,
 user_id),

	CONSTRAINT uq_r15_report_execution UNIQUE (generation_id,
 frequency,
 cutoff_at),

	CONSTRAINT ck_r15_report_frequency CHECK (frequency IN ('day',
'week')),

	CONSTRAINT ck_r15_report_payload CHECK (content_sha256 ~ '^[0-9a-f]{64}$'
AND jsonb_typeof(payload)='object'),

	CONSTRAINT ck_r15_report_current CHECK (current_status IN ('current',
'stale',
'withdrawn',
'unknown'))
)
        """
    )
    op.execute(
        """
CREATE INDEX ix_r15_report_owner ON r15_reports (tenant_id,
 user_id,
 generated_at)
        """
    )
    op.execute(
        """
CREATE FUNCTION prevent_r15_history_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
RAISE EXCEPTION 'recommendation history is immutable' USING ERRCODE='23514'; END $$
        """
    )
    op.execute(
        """
CREATE TRIGGER r15_generations_immutable BEFORE UPDATE OR DELETE ON r15_generations
FOR EACH ROW EXECUTE FUNCTION prevent_r15_history_mutation()
        """
    )
    op.execute(
        """
CREATE TRIGGER r15_reports_immutable BEFORE UPDATE OR DELETE ON r15_reports
FOR EACH ROW EXECUTE FUNCTION prevent_r15_history_mutation()
        """
    )
    op.execute(
        """
CREATE FUNCTION protect_r15_subscription() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
IF TG_OP='DELETE'
THEN  RAISE EXCEPTION 'subscription history is immutable' USING ERRCODE='23514'; END IF;
IF ROW(NEW.id,
NEW.tenant_id,
NEW.user_id,
NEW.created_at)
IS DISTINCT FROM ROW(OLD.id,
OLD.tenant_id,
OLD.user_id,
OLD.created_at)
OR NEW.version<>OLD.version+1
OR NEW. updated_at<OLD.updated_at
THEN
RAISE EXCEPTION 'subscription owner or version is invalid' USING ERRCODE='23514'; END IF;
RETURN NEW; END $$
        """
    )
    op.execute(
        """
CREATE TRIGGER r15_subscriptions_owner_version BEFORE UPDATE OR DELETE ON r15_subscriptions
FOR EACH ROW EXECUTE FUNCTION protect_r15_subscription()
        """
    )
    op.execute(
        """
CREATE FUNCTION protect_r15_recommendation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
IF TG_OP='DELETE'
THEN  RAISE EXCEPTION 'recommendation history is immutable' USING ERRCODE='23514'; END IF;
IF (to_jsonb(NEW)-ARRAY['read_at',
'current_status',
'current_reason',
'current_checked_at'])
IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['read_at',
'current_status',
'current_reason',
'current_checked_at'])
OR (OLD.read_at IS NOT NULL
AND NEW. read_at
IS DISTINCT FROM OLD.read_at)
OR NEW.current_checked_at<OLD.current_checked_at
THEN
RAISE EXCEPTION 'recommendation history is immutable' USING ERRCODE='23514'; END IF;
RETURN NEW; END $$
        """
    )
    op.execute(
        """
CREATE TRIGGER r15_recommendations_history BEFORE UPDATE OR DELETE ON r15_recommendations
FOR EACH ROW EXECUTE FUNCTION protect_r15_recommendation()
        """
    )


def downgrade() -> None:
    """Retain immutable history; recovery uses reviewed forward repairs."""
    raise RuntimeError("recommendation history requires forward-only recovery")
