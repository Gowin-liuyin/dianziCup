"""Forward frozen recovery DDL; historical rows retain authority.

Revision ID: 0024_conversation_context
Revises: 0023_enrichment_input_audit
"""

from alembic import op

revision = "0024_conversation_context"
down_revision = "0023_enrichment_input_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add only the approved fields, sidecars and integrity guards."""
    op.execute(
        """
CREATE TABLE qa_conversations (
    conversation_id UUID NOT NULL,
    schema_version INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    tenant_id TEXT,
    status TEXT NOT NULL,
    version BIGINT NOT NULL,
    active_turn_id UUID,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (conversation_id),
    CONSTRAINT ck_qa_conversation_version CHECK (schema_version=1 AND version>=0),
    CONSTRAINT ck_qa_conversation_status CHECK ((status='active' AND revoked_at IS NULL) OR
(status='revoked' AND revoked_at IS NOT NULL)),
    FOREIGN KEY(user_id) REFERENCES users (user_id)
)
        """
    )
    op.execute(
        """
CREATE TABLE qa_conversation_turns (
    turn_id UUID NOT NULL,
    schema_version INTEGER NOT NULL,
    conversation_id UUID NOT NULL,
    user_id TEXT NOT NULL,
    tenant_id TEXT,
    turn_number BIGINT NOT NULL,
    base_conversation_version BIGINT NOT NULL,
    answer_id TEXT NOT NULL,
    context_sha256 TEXT NOT NULL,
    resolved_context JSONB NOT NULL,
    admitted_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (turn_id),
    CONSTRAINT ck_qa_turn_version CHECK (schema_version=1 AND turn_number>=1 AND
base_conversation_version>=0),
    CONSTRAINT ck_qa_turn_context CHECK (context_sha256 ~ '^[0-9a-f]{64}$' AND
jsonb_typeof(resolved_context)='object'),
    CONSTRAINT uq_qa_turn_number UNIQUE (conversation_id, turn_number),
    CONSTRAINT uq_qa_turn_conversation_identity UNIQUE (conversation_id, turn_id),
    FOREIGN KEY(conversation_id) REFERENCES qa_conversations (conversation_id),
    FOREIGN KEY(user_id) REFERENCES users (user_id),
    UNIQUE (answer_id),
    FOREIGN KEY(answer_id) REFERENCES grounded_answers (answer_id)
)
        """
    )
    op.execute(
        """
ALTER TABLE qa_conversations ADD CONSTRAINT fk_qa_active_turn FOREIGN KEY(conversation_id,
active_turn_id) REFERENCES qa_conversation_turns (conversation_id, turn_id) DEFERRABLE INITIALLY
DEFERRED
        """
    )
    op.execute(
        """
CREATE INDEX ix_qa_conversation_owner ON qa_conversations (user_id, tenant_id, updated_at,
conversation_id)
        """
    )
    op.execute(
        """
CREATE FUNCTION qa_validate_turn_ownership() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  target_turn uuid;
  target_conversation uuid;
  target_answer text;
BEGIN
  IF TG_TABLE_NAME='qa_conversation_turns' THEN target_turn := NEW.turn_id;
  ELSIF TG_TABLE_NAME='qa_conversations' THEN target_conversation := NEW.conversation_id;
  ELSE target_answer := NEW.answer_id;
  END IF;
  IF EXISTS (
    SELECT 1 FROM qa_conversation_turns t
    JOIN qa_conversations c USING (conversation_id)
    JOIN grounded_answers a USING (answer_id)
    WHERE (t.turn_id=target_turn OR t.conversation_id=target_conversation
           OR t.answer_id=target_answer)
      AND (t.user_id IS DISTINCT FROM c.user_id OR t.user_id IS DISTINCT FROM a.user_id
       OR t.tenant_id IS DISTINCT FROM c.tenant_id OR t.tenant_id IS DISTINCT FROM a.tenant_id)
  ) THEN
    RAISE EXCEPTION 'conversation owner mismatch' USING ERRCODE='23514';
  END IF;
  RETURN NULL;
END;
$$
        """
    )
    op.execute(
        """
ALTER FUNCTION qa_validate_turn_ownership() SET search_path FROM CURRENT
        """
    )
    op.execute(
        """
CREATE CONSTRAINT TRIGGER qa_owner_qa_conversation_turns AFTER INSERT OR UPDATE ON
qa_conversation_turns DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION
qa_validate_turn_ownership()
        """
    )
    op.execute(
        """
CREATE CONSTRAINT TRIGGER qa_owner_qa_conversations AFTER INSERT OR UPDATE ON qa_conversations
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION qa_validate_turn_ownership()
        """
    )
    op.execute(
        """
CREATE CONSTRAINT TRIGGER qa_owner_grounded_answers AFTER INSERT OR UPDATE ON grounded_answers
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION qa_validate_turn_ownership()
        """
    )
    op.execute(
        """
CREATE FUNCTION prevent_qa_turn_changes() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'conversation turns are immutable' USING ERRCODE='23514'; END $$
        """
    )
    op.execute(
        """
CREATE TRIGGER qa_conversation_turns_immutable BEFORE UPDATE OR DELETE
ON qa_conversation_turns FOR EACH ROW EXECUTE FUNCTION prevent_qa_turn_changes()
        """
    )


def downgrade() -> None:
    """Preserve receipts and revocation history; use approved forward repair."""
    raise RuntimeError("recovery history requires forward-only recovery")
