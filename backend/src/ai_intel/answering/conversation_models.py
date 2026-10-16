"""Two PG conversation tables proposed for root migration0024; no runtime creation."""

from sqlalchemy import (
    DDL,
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Table,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ai_intel.knowledge.models import metadata
from ai_intel.retrieval.persistence_models import grounded_answers as grounded_answers

qa_conversations = Table(
    "qa_conversations",
    metadata,
    Column("conversation_id", UUID(as_uuid=True), primary_key=True),
    Column("schema_version", Integer, nullable=False),
    Column("user_id", Text, ForeignKey("users.user_id"), nullable=False),
    Column("tenant_id", Text),
    Column("status", Text, nullable=False),
    Column("version", BigInteger, nullable=False),
    Column("active_turn_id", UUID(as_uuid=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
    CheckConstraint("schema_version=1 AND version>=0", name="ck_qa_conversation_version"),
    CheckConstraint(
        "(status='active' AND revoked_at IS NULL) OR (status='revoked' AND revoked_at IS NOT NULL)",
        name="ck_qa_conversation_status",
    ),
    ForeignKeyConstraint(
        ["conversation_id", "active_turn_id"],
        ["qa_conversation_turns.conversation_id", "qa_conversation_turns.turn_id"],
        name="fk_qa_active_turn",
        deferrable=True,
        initially="DEFERRED",
        use_alter=True,
    ),
)
Index(
    "ix_qa_conversation_owner",
    qa_conversations.c.user_id,
    qa_conversations.c.tenant_id,
    qa_conversations.c.updated_at,
    qa_conversations.c.conversation_id,
)

qa_conversation_turns = Table(
    "qa_conversation_turns",
    metadata,
    Column("turn_id", UUID(as_uuid=True), primary_key=True),
    Column("schema_version", Integer, nullable=False),
    Column(
        "conversation_id",
        UUID(as_uuid=True),
        ForeignKey("qa_conversations.conversation_id"),
        nullable=False,
    ),
    Column("user_id", Text, ForeignKey("users.user_id"), nullable=False),
    Column("tenant_id", Text),
    Column("turn_number", BigInteger, nullable=False),
    Column("base_conversation_version", BigInteger, nullable=False),
    Column(
        "answer_id", Text, ForeignKey("grounded_answers.answer_id"), nullable=False, unique=True
    ),
    Column("context_sha256", Text, nullable=False),
    Column("resolved_context", JSONB, nullable=False),
    Column("admitted_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "schema_version=1 AND turn_number>=1 AND base_conversation_version>=0",
        name="ck_qa_turn_version",
    ),
    CheckConstraint(
        "context_sha256 ~ '^[0-9a-f]{64}$' AND jsonb_typeof(resolved_context)='object'",
        name="ck_qa_turn_context",
    ),
    UniqueConstraint("conversation_id", "turn_number", name="uq_qa_turn_number"),
    UniqueConstraint("conversation_id", "turn_id", name="uq_qa_turn_conversation_identity"),
)

OWNERSHIP_FUNCTION_DDL = """
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

OWNERSHIP_TRIGGER_DDLS = tuple(
    f"CREATE CONSTRAINT TRIGGER qa_owner_{table} AFTER INSERT OR UPDATE ON {table} "
    "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION qa_validate_turn_ownership()"
    for table in ("qa_conversation_turns", "qa_conversations", "grounded_answers")
)

IMMUTABILITY_FUNCTION_DDL = """
CREATE FUNCTION prevent_qa_turn_changes() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'conversation turns are immutable' USING ERRCODE='23514'; END $$
"""
IMMUTABILITY_TRIGGER_DDL = """
CREATE TRIGGER qa_conversation_turns_immutable BEFORE UPDATE OR DELETE
ON qa_conversation_turns FOR EACH ROW EXECUTE FUNCTION prevent_qa_turn_changes()
"""

event.listen(qa_conversation_turns, "after_create", DDL(OWNERSHIP_FUNCTION_DDL))
for ownership_ddl in OWNERSHIP_TRIGGER_DDLS:
    event.listen(qa_conversation_turns, "after_create", DDL(ownership_ddl))
event.listen(qa_conversation_turns, "after_create", DDL(IMMUTABILITY_FUNCTION_DDL))
event.listen(qa_conversation_turns, "after_create", DDL(IMMUTABILITY_TRIGGER_DDL))
