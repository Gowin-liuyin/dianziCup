"""Add frozen immutable R11 history through the production forward chain.

Revision ID: 0021_condition_assessments
Revises: 0020_hybrid_retrieval
"""

from alembic import op

revision = "0021_condition_assessments"
down_revision = "0020_hybrid_retrieval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create only new tables; existing facts, bytes and hashes are unchanged."""
    op.execute(
        """
CREATE TABLE condition_rule_versions (
rule_id TEXT NOT NULL,
version INTEGER NOT NULL,
event_id TEXT NOT NULL,
visibility TEXT NOT NULL,
tenant_id TEXT,
rule_kind TEXT NOT NULL,
condition_sha256 TEXT NOT NULL,
rule_payload JSONB NOT NULL,
status TEXT NOT NULL,
author_user_id TEXT NOT NULL,
published_by TEXT,
published_at TIMESTAMP WITH TIME ZONE,
retired_at TIMESTAMP WITH TIME ZONE,
created_at TIMESTAMP WITH TIME ZONE NOT NULL,
PRIMARY KEY (rule_id, version),
CONSTRAINT ck_condition_rule_version CHECK (version > 0),
CONSTRAINT ck_condition_rule_visibility CHECK (visibility IN ('public', 'tenant')),
CONSTRAINT ck_condition_rule_tenant CHECK ((visibility = 'public' AND tenant_id IS NULL) OR
(visibility = 'tenant' AND tenant_id IS NOT NULL)),
CONSTRAINT ck_condition_rule_kind CHECK (rule_kind IN
('software_applicability','observed_path','research_prerequisites')),
CONSTRAINT ck_condition_rule_status CHECK (status IN
('candidate','validated','published','retired')),
CONSTRAINT ck_rule_condition_digest CHECK (condition_sha256 ~ '^[0-9a-f]{64}$'),
CONSTRAINT ck_rule_payload CHECK (jsonb_typeof(rule_payload)='object'),
CONSTRAINT ck_rule_published_time CHECK ((status IN ('published','retired'))=(published_at
IS NOT NULL)),
CONSTRAINT ck_rule_retired_time CHECK ((status='retired')=(retired_at IS NOT NULL)),
CONSTRAINT ck_rule_reviewer CHECK (published_by IS NULL OR published_by<>author_user_id),
FOREIGN KEY(event_id) REFERENCES events (event_id),
FOREIGN KEY(author_user_id) REFERENCES users (user_id),
FOREIGN KEY(published_by) REFERENCES users (user_id)
)
        """
    )
    op.execute(
        """
CREATE UNIQUE INDEX uq_current_published_rule_family ON condition_rule_versions (rule_id)
WHERE status = 'published'
        """
    )
    op.execute(
        """
CREATE TABLE rule_support_bindings (
rule_id TEXT NOT NULL,
rule_version INTEGER NOT NULL,
node_id TEXT NOT NULL,
claim_id TEXT NOT NULL,
evidence_id TEXT NOT NULL,
condition_sha256 TEXT NOT NULL,
PRIMARY KEY (rule_id, rule_version, node_id, claim_id, evidence_id),
CONSTRAINT fk_rule_support_version FOREIGN KEY(rule_id, rule_version) REFERENCES
condition_rule_versions (rule_id, version),
CONSTRAINT ck_binding_condition_digest CHECK (condition_sha256 ~ '^[0-9a-f]{64}$'),
FOREIGN KEY(claim_id) REFERENCES claims (claim_id),
FOREIGN KEY(evidence_id) REFERENCES evidence (evidence_id)
)
        """
    )
    op.execute(
        """
CREATE TABLE rule_leaf_reviews (
review_id TEXT NOT NULL,
rule_id TEXT NOT NULL,
rule_version INTEGER NOT NULL,
node_id TEXT NOT NULL,
claim_id TEXT NOT NULL,
evidence_id TEXT NOT NULL,
input_digest TEXT NOT NULL,
decision TEXT NOT NULL,
range_complete BOOLEAN NOT NULL,
reason TEXT NOT NULL,
actor_user_id TEXT NOT NULL,
actor_role TEXT NOT NULL,
created_at TIMESTAMP WITH TIME ZONE NOT NULL,
PRIMARY KEY (review_id),
CONSTRAINT fk_rule_review_binding FOREIGN KEY(rule_id, rule_version, node_id, claim_id,
evidence_id) REFERENCES rule_support_bindings (rule_id, rule_version, node_id, claim_id,
evidence_id),
CONSTRAINT ck_rule_review_decision CHECK (decision IN ('supports','refutes')),
CONSTRAINT ck_rule_review_reason CHECK (length(reason) BETWEEN 1 AND 2000),
CONSTRAINT ck_rule_review_digest CHECK (input_digest ~ '^[0-9a-f]{64}$'),
CONSTRAINT uq_rule_review_replay UNIQUE (rule_id, rule_version, node_id, claim_id,
evidence_id, input_digest, actor_user_id, decision, range_complete, reason),
FOREIGN KEY(actor_user_id) REFERENCES users (user_id)
)
        """
    )
    op.execute(
        """
CREATE TABLE rule_validation_receipts (
receipt_id TEXT NOT NULL,
rule_id TEXT NOT NULL,
rule_version INTEGER NOT NULL,
actor_user_id TEXT NOT NULL,
input_digest TEXT NOT NULL,
policy_version TEXT NOT NULL,
validator_version TEXT NOT NULL,
input_snapshot JSONB NOT NULL,
prepared_assessment JSONB,
created_at TIMESTAMP WITH TIME ZONE NOT NULL,
PRIMARY KEY (receipt_id),
CONSTRAINT fk_rule_validation_version FOREIGN KEY(rule_id, rule_version) REFERENCES
condition_rule_versions (rule_id, version),
CONSTRAINT ck_rule_validation_digest CHECK (input_digest ~ '^[0-9a-f]{64}$'),
CONSTRAINT ck_rule_validation_snapshot CHECK (jsonb_typeof(input_snapshot)='object'),
FOREIGN KEY(actor_user_id) REFERENCES users (user_id)
)
        """
    )
    op.execute(
        """
CREATE TABLE assessment_results (
assessment_id TEXT NOT NULL,
tenant_id TEXT NOT NULL,
asset_id TEXT NOT NULL,
asset_snapshot_id TEXT NOT NULL,
event_id TEXT NOT NULL,
rule_id TEXT NOT NULL,
rule_version INTEGER NOT NULL,
knowledge_epoch BIGINT,
scope_epoch_map JSONB NOT NULL,
policy_version TEXT NOT NULL,
input_digest TEXT NOT NULL,
status TEXT NOT NULL,
freshness TEXT NOT NULL,
result_payload JSONB NOT NULL,
created_at TIMESTAMP WITH TIME ZONE NOT NULL,
PRIMARY KEY (assessment_id),
CONSTRAINT fk_assessment_asset_snapshot_tenant FOREIGN KEY(asset_id, tenant_id,
asset_snapshot_id) REFERENCES asset_snapshots (asset_id, tenant_id, snapshot_id),
CONSTRAINT fk_assessment_rule_version FOREIGN KEY(rule_id, rule_version) REFERENCES
condition_rule_versions (rule_id, version),
CONSTRAINT uq_assessment_execution UNIQUE (tenant_id, asset_snapshot_id, rule_id,
rule_version, input_digest, policy_version),
CONSTRAINT ck_assessment_input_digest CHECK (input_digest ~ '^[0-9a-f]{64}$'),
CONSTRAINT ck_assessment_freshness CHECK (freshness IN ('current','stale','unknown')),
CONSTRAINT ck_assessment_status CHECK (status IN
('supported_applicability','excluded_with_evidence','insufficient_evidence','conflicting_evidence')),
CONSTRAINT ck_assessment_payload CHECK (jsonb_typeof(result_payload)='object'),
FOREIGN KEY(event_id) REFERENCES events (event_id)
)
        """
    )
    op.execute(
        """
CREATE INDEX ix_assessment_tenant_asset ON assessment_results (tenant_id, asset_id,
created_at)
        """
    )
    op.execute(
        """
CREATE TABLE assessment_scope_watches (
assessment_id TEXT NOT NULL,
tenant_id TEXT NOT NULL,
event_ids JSONB NOT NULL,
package_keys JSONB NOT NULL,
rule_id TEXT NOT NULL,
rule_version INTEGER NOT NULL,
rule_kind TEXT NOT NULL,
scope_epoch_map JSONB NOT NULL,
selected_rule_ids JSONB NOT NULL,
no_published_rule BOOLEAN NOT NULL,
PRIMARY KEY (assessment_id),
CONSTRAINT ck_assessment_watch_event CHECK (jsonb_array_length(event_ids)>0),
FOREIGN KEY(assessment_id) REFERENCES assessment_results (assessment_id)
)
        """
    )
    op.execute(
        """
CREATE OR REPLACE FUNCTION r11_require_immutable_rule() RETURNS trigger LANGUAGE plpgsql AS
$$
BEGIN
IF TG_OP='DELETE' THEN RAISE EXCEPTION 'rule versions are immutable' USING ERRCODE='23514';
END IF;
IF (to_jsonb(OLD)-'status'-'published_at'-'retired_at'-'published_by') <>
(to_jsonb(NEW)-'status'-'published_at'-'retired_at'-'published_by') THEN
RAISE EXCEPTION 'rule content is immutable' USING ERRCODE='23514'; END IF;
IF (OLD.status<>NEW.status AND NOT
((OLD.status='candidate' AND NEW.status='validated') OR
(OLD.status='validated' AND NEW.status='published') OR
(OLD.status='published' AND NEW.status='retired'))) OR
(OLD.published_at IS NOT NULL AND OLD.published_at IS DISTINCT FROM NEW.published_at) OR
(OLD.published_by IS NOT NULL AND OLD.published_by IS DISTINCT FROM NEW.published_by) OR
(OLD.retired_at IS NOT NULL AND OLD.retired_at IS DISTINCT FROM NEW.retired_at) THEN
RAISE EXCEPTION 'rule lifecycle is forward only' USING ERRCODE='23514'; END IF;
RETURN NEW; END $$;
CREATE TRIGGER condition_rule_versions_immutable BEFORE UPDATE OR DELETE
ON condition_rule_versions FOR EACH ROW EXECUTE FUNCTION r11_require_immutable_rule();
        """
    )
    op.execute(
        """
CREATE OR REPLACE FUNCTION r11_require_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'rule and assessment receipts are append only' USING ERRCODE='23514';
END $$;
        """
    )
    op.execute(
        """
CREATE TRIGGER rule_support_bindings_immutable BEFORE UPDATE OR DELETE ON
rule_support_bindings FOR EACH ROW EXECUTE FUNCTION r11_require_append_only();
        """
    )
    op.execute(
        """
CREATE TRIGGER rule_leaf_reviews_immutable BEFORE UPDATE OR DELETE ON rule_leaf_reviews FOR
EACH ROW EXECUTE FUNCTION r11_require_append_only();
        """
    )
    op.execute(
        """
CREATE TRIGGER rule_validation_receipts_immutable BEFORE UPDATE OR DELETE ON
rule_validation_receipts FOR EACH ROW EXECUTE FUNCTION r11_require_append_only();
        """
    )
    op.execute(
        """
CREATE TRIGGER assessment_results_immutable BEFORE UPDATE OR DELETE ON assessment_results
FOR EACH ROW EXECUTE FUNCTION r11_require_append_only();
        """
    )
    op.execute(
        """
CREATE TRIGGER assessment_scope_watches_immutable BEFORE UPDATE OR DELETE ON
assessment_scope_watches FOR EACH ROW EXECUTE FUNCTION r11_require_append_only();
        """
    )


def downgrade() -> None:
    """Preserve evidence history; disable writers and use an approved forward repair."""
    raise RuntimeError("R11 immutable history cannot be downgraded; use forward repair")
