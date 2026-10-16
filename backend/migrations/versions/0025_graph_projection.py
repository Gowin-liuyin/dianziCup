"""Forward frozen recovery DDL; historical rows retain authority.

Revision ID: 0025_graph_projection
Revises: 0024_conversation_context
"""

from alembic import op

revision = "0025_graph_projection"
down_revision = "0024_conversation_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add only the approved fields, sidecars and integrity guards."""
    op.execute(
        """
CREATE TABLE graph_projection_batches (
    batch_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    partition_key TEXT NOT NULL,
    generation_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    sequence BIGINT NOT NULL,
    kind TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    payload BYTEA NOT NULL,
    captured_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (batch_id),
    CONSTRAINT uq_graph_projection_sequence UNIQUE (namespace, partition_key, generation_id,
event_id, sequence),
    CONSTRAINT ck_graph_projection_sequence CHECK (sequence > 0),
    CONSTRAINT ck_graph_projection_kind CHECK (kind IN ('snapshot','tombstone')),
    CONSTRAINT ck_graph_projection_payload CHECK (octet_length(payload) <= 8388608),
    CONSTRAINT ck_graph_projection_digest CHECK (payload_sha256 ~ '^[0-9a-f]{64}$')
)
        """
    )
    op.execute(
        """
CREATE TABLE graph_projection_state (
    namespace TEXT NOT NULL,
    partition_key TEXT NOT NULL,
    generation_id TEXT NOT NULL,
    state_key TEXT NOT NULL,
    state_kind TEXT NOT NULL,
    event_id TEXT,
    body JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (namespace, partition_key, generation_id, state_key),
    CONSTRAINT ck_graph_state_kind CHECK (state_kind IN ('partition','page','slot')),
    CONSTRAINT ck_graph_state_event CHECK ((state_kind = 'slot') = (event_id IS NOT NULL))
)
        """
    )
    op.execute(
        """
ALTER TABLE graph_projection_batches ADD CONSTRAINT ck_graph_projection_payload_sha256
CHECK (payload_sha256 = encode(sha256(payload),'hex'))
        """
    )
    op.execute(
        """
CREATE FUNCTION prevent_graph_projection_batch_changes() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
RAISE EXCEPTION 'graph projection batches are immutable' USING ERRCODE='23514'; END $$
        """
    )
    op.execute(
        """
CREATE TRIGGER graph_projection_batches_immutable BEFORE UPDATE OR DELETE
ON graph_projection_batches FOR EACH ROW EXECUTE FUNCTION prevent_graph_projection_batch_changes()
        """
    )


def downgrade() -> None:
    """Preserve receipts and revocation history; use approved forward repair."""
    raise RuntimeError("recovery history requires forward-only recovery")
