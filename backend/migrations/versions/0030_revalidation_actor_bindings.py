"""Install append-only actor bindings; existing PG jobs remain authoritative."""

from alembic import op

revision = "0030_revalidation_actor_bindings"
down_revision = "0029_recommendation_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add immutable server authentication bindings without changing historical rows."""
    op.execute(
        """
CREATE TABLE revalidation_job_bindings (
	job_id TEXT NOT NULL,
	actor_user_id TEXT NOT NULL,
	tenant_id TEXT,
	authorized_role TEXT NOT NULL,
	actor_reference JSONB NOT NULL,
	payload_sha256 TEXT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (job_id),
	CONSTRAINT ck_revalidation_actor_role
        CHECK (authorized_role IN ('tenant_admin','system_admin','analyst','viewer')),
	CONSTRAINT ck_revalidation_actor_object CHECK (jsonb_typeof(actor_reference)='object'),
	CONSTRAINT ck_revalidation_payload_digest CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
	FOREIGN KEY(job_id) REFERENCES job_runs (job_id),
	FOREIGN KEY(actor_user_id) REFERENCES users (user_id)
)
        """
    )
    op.execute(
        """
CREATE FUNCTION protect_revalidation_actor_binding() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
RAISE EXCEPTION 'revalidation actor binding is immutable' USING ERRCODE='23514';
END $$
        """
    )
    op.execute(
        """
CREATE TRIGGER revalidation_job_bindings_immutable
BEFORE UPDATE OR DELETE ON revalidation_job_bindings
FOR EACH ROW EXECUTE FUNCTION protect_revalidation_actor_binding()
        """
    )


def downgrade() -> None:
    """Retain identities and history; recovery requires a reviewed forward migration."""
    raise RuntimeError("0030_revalidation_actor_bindings requires forward-only recovery")
