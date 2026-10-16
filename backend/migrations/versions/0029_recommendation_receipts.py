"""Install approved persistent records without changing historical tables."""

from alembic import op

revision = "0029_recommendation_receipts"
down_revision = "0028_investigation_workflows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create immutable bindings and their explicitly permitted completion transitions."""
    op.execute(
        """
CREATE TABLE recommendation_mutation_receipts (
	id TEXT NOT NULL,
	tenant_id TEXT NOT NULL,
	user_id TEXT NOT NULL,
	operation TEXT NOT NULL,
	target_locator TEXT NOT NULL,
	idempotency_sha256 TEXT NOT NULL,
	input_sha256 TEXT NOT NULL,
	response_payload JSONB NOT NULL,
	response_sha256 TEXT NOT NULL,
	status_code INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_recommendation_mutation_request
        UNIQUE (tenant_id, user_id, operation, target_locator, idempotency_sha256),
	CONSTRAINT ck_recommendation_mutation_operation
        CHECK (operation IN ('create_subscription','replace_subscription','set_enabled',
        'generate','mark_read','create_report')),
	CONSTRAINT ck_recommendation_mutation_target CHECK (length(target_locator) BETWEEN 1 AND 200),
	CONSTRAINT ck_recommendation_mutation_hashes
        CHECK (idempotency_sha256 ~ '^[0-9a-f]{64}$' AND input_sha256 ~ '^[0-9a-f]{64}$'
        AND response_sha256 ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_recommendation_mutation_response CHECK (jsonb_typeof(response_payload)='object'),
	CONSTRAINT ck_recommendation_mutation_status CHECK (status_code IN (200,201)),
	FOREIGN KEY(user_id) REFERENCES users (user_id)
)
        """
    )
    op.execute(
        """
CREATE FUNCTION protect_recommendation_mutation_receipt() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
RAISE EXCEPTION 'recommendation request receipt is immutable' USING ERRCODE='23514';
END $$
        """
    )
    op.execute(
        """
CREATE TRIGGER recommendation_mutation_receipts_immutable
BEFORE UPDATE OR DELETE ON recommendation_mutation_receipts
FOR EACH ROW EXECUTE FUNCTION protect_recommendation_mutation_receipt()
        """
    )


def downgrade() -> None:
    """Retain audit/history; recovery uses separately reviewed forward repairs."""
    raise RuntimeError("0029_recommendation_receipts requires forward-only recovery")
