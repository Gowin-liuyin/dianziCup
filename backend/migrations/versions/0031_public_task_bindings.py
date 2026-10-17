"""Add public typed locators while JobRun remains the unique task status authority."""

from alembic import op

revision = "0031_public_task_bindings"
down_revision = "0030_revalidation_actor_bindings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Install request/owner bindings and write-once typed locators without rewriting history."""
    op.execute("""
CREATE TABLE public_task_bindings (
 task_id TEXT PRIMARY KEY REFERENCES job_runs(job_id),
 schema_version TEXT NOT NULL,
 task_type TEXT NOT NULL,
 owner_user_id TEXT NOT NULL REFERENCES users(user_id),
 tenant_id TEXT,
 authorized_role TEXT NOT NULL,
 actor_reference JSONB NOT NULL,
 public_request_json JSONB NOT NULL,
 request_sha256 TEXT NOT NULL,
 trace_id TEXT NOT NULL,
 admitted_at TIMESTAMPTZ NOT NULL,
 deadline_at TIMESTAMPTZ NOT NULL,
 result_kind TEXT,
 result_id TEXT,
 result_published_at TIMESTAMPTZ,
 CONSTRAINT ck_public_task_schema CHECK(schema_version = 'r18-public-task-binding-1'),
 CONSTRAINT ck_public_task_type CHECK(task_type IN ('ask','stack_check')),
 CONSTRAINT ck_public_task_role CHECK(
  authorized_role IN ('tenant_admin','system_admin','analyst','viewer')),
 CONSTRAINT ck_public_task_actor CHECK(jsonb_typeof(actor_reference) = 'object'),
 CONSTRAINT ck_public_task_request CHECK(jsonb_typeof(public_request_json) = 'object'),
 CONSTRAINT ck_public_task_digest CHECK(request_sha256 ~ '^[0-9a-f]{64}$'),
 CONSTRAINT ck_public_task_trace CHECK(trace_id ~ '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$'),
 CONSTRAINT ck_public_task_deadline CHECK(deadline_at > admitted_at),
 CONSTRAINT ck_public_task_result CHECK(
  (result_kind IS NULL AND result_id IS NULL AND result_published_at IS NULL) OR
  (result_kind IS NOT NULL AND result_id IS NOT NULL AND result_published_at IS NOT NULL
   AND ((task_type = 'ask' AND result_kind = 'qa_answer') OR
        (task_type = 'stack_check' AND result_kind = 'stack_check'))
   AND result_published_at >= admitted_at AND result_published_at < deadline_at)),
 CONSTRAINT ck_public_task_result_id CHECK(
  result_id IS NULL OR result_id ~ '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$')
)
""")
    op.execute("""
CREATE FUNCTION protect_public_task_binding() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'DELETE'
 OR (to_jsonb(NEW) - ARRAY['result_kind','result_id','result_published_at']) <>
    (to_jsonb(OLD) - ARRAY['result_kind','result_id','result_published_at'])
 OR OLD.result_kind IS NOT NULL
 OR NEW.result_kind IS NULL THEN
  RAISE EXCEPTION 'public task binding is immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER public_task_bindings_immutable BEFORE UPDATE OR DELETE ON public_task_bindings
FOR EACH ROW EXECUTE FUNCTION protect_public_task_binding();
""")


def downgrade() -> None:
    """History remains intact; disable the producer and use reviewed forward recovery."""
    raise RuntimeError("0031_public_task_bindings requires forward-only recovery")
