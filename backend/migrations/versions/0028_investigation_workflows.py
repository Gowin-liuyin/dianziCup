"""Install approved persistent records without changing historical tables."""

from alembic import op

revision = "0028_investigation_workflows"
down_revision = "0027_recommendation_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create immutable bindings and their explicitly permitted completion transitions."""
    op.execute(
        """
CREATE TABLE investigation_workflows (
	job_id TEXT NOT NULL,
	owner_user_id TEXT NOT NULL,
	tenant_id TEXT,
	authorized_role TEXT NOT NULL,
	actor_reference JSONB NOT NULL,
	graph_version TEXT NOT NULL,
	input_sha256 TEXT NOT NULL,
	input_json JSONB NOT NULL,
	budget_json JSONB NOT NULL,
	scope_epochs JSONB NOT NULL,
	asset_snapshot_id TEXT,
	deadline_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (job_id),
	CONSTRAINT uq_investigation_owner_binding UNIQUE (job_id, owner_user_id, tenant_id),
	CONSTRAINT ck_investigation_graph_version CHECK (graph_version = 'r14-langgraph-1'),
	CONSTRAINT ck_investigation_input_hash CHECK (length(input_sha256) = 64),
	CONSTRAINT ck_investigation_deadline CHECK (deadline_at > created_at),
	FOREIGN KEY(job_id) REFERENCES job_runs (job_id),
	FOREIGN KEY(owner_user_id) REFERENCES users (user_id)
)
        """
    )
    op.execute(
        """
CREATE TABLE investigation_operations (
	job_id TEXT NOT NULL,
	operation_key TEXT NOT NULL,
	call_key TEXT NOT NULL,
	kind TEXT NOT NULL,
	role TEXT NOT NULL,
	status TEXT NOT NULL,
	request_sha256 TEXT NOT NULL,
	tool_name TEXT,
	model_version TEXT,
	prompt_version TEXT,
	policy_version TEXT NOT NULL,
	pricing_version TEXT DEFAULT 'unavailable' NOT NULL,
	cost_status TEXT DEFAULT 'unknown' NOT NULL,
	input_bytes INTEGER NOT NULL,
	output_bytes INTEGER NOT NULL,
	tool_calls INTEGER NOT NULL,
	model_calls INTEGER NOT NULL,
	output_json JSONB,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	completed_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (job_id, operation_key),
	CONSTRAINT uq_investigation_operation_call UNIQUE (job_id, call_key),
	CONSTRAINT ck_investigation_operation_kind CHECK (kind IN ('tool','model','node')),
	CONSTRAINT ck_investigation_operation_status
        CHECK (status IN ('reserved','succeeded','partial','failed')),
	CONSTRAINT ck_investigation_operation_counters
        CHECK (input_bytes >= 0 AND output_bytes >= 0 AND tool_calls >= 0 AND model_calls >= 0),
	CONSTRAINT ck_investigation_operation_cost CHECK (cost_status = 'unknown'),
	CONSTRAINT ck_investigation_operation_receipt
        CHECK ((status = 'reserved' AND completed_at IS NULL AND output_json IS NULL)
        OR (status <> 'reserved' AND completed_at IS NOT NULL AND output_json IS NOT NULL)),
	FOREIGN KEY(job_id) REFERENCES investigation_workflows (job_id)
)
        """
    )
    op.execute(
        """
CREATE FUNCTION prevent_investigation_workflow_changes() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'investigation binding is immutable'; END; $$;
CREATE TRIGGER investigation_workflows_immutable BEFORE UPDATE OR DELETE ON investigation_workflows
FOR EACH ROW EXECUTE FUNCTION prevent_investigation_workflow_changes();
CREATE FUNCTION prevent_investigation_receipt_changes() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'DELETE' OR OLD.status <> 'reserved' OR NEW.status = 'reserved'
 OR (to_jsonb(NEW) - ARRAY['status','output_json','completed_at']) <>
    (to_jsonb(OLD) - ARRAY['status','output_json','completed_at']) THEN
   RAISE EXCEPTION 'investigation receipt is immutable';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER investigation_operations_immutable
BEFORE UPDATE OR DELETE ON investigation_operations
FOR EACH ROW EXECUTE FUNCTION prevent_investigation_receipt_changes();
        """
    )


def downgrade() -> None:
    """Retain audit/history; recovery uses separately reviewed forward repairs."""
    raise RuntimeError("0028_investigation_workflows requires forward-only recovery")
