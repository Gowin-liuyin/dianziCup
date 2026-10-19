"""Two disposable PG projection sidecars; production DDL is owned by migration 0025."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    LargeBinary,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

from ai_intel.knowledge.models import metadata

graph_projection_batches = Table(
    "graph_projection_batches",
    metadata,
    Column("batch_id", Text, primary_key=True),
    Column("namespace", Text, nullable=False),
    Column("partition_key", Text, nullable=False),
    Column("generation_id", Text, nullable=False),
    Column("event_id", Text, nullable=False),
    Column("sequence", BigInteger, nullable=False),
    Column("kind", Text, nullable=False),
    Column("payload_sha256", Text, nullable=False),
    Column("payload", LargeBinary, nullable=False),
    Column("captured_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "namespace",
        "partition_key",
        "generation_id",
        "event_id",
        "sequence",
        name="uq_graph_projection_sequence",
    ),
    CheckConstraint("sequence > 0", name="ck_graph_projection_sequence"),
    CheckConstraint("kind IN ('snapshot','tombstone')", name="ck_graph_projection_kind"),
    CheckConstraint("octet_length(payload) <= 8388608", name="ck_graph_projection_payload"),
    CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_graph_projection_digest"),
)

graph_projection_state = Table(
    "graph_projection_state",
    metadata,
    Column("namespace", Text, primary_key=True),
    Column("partition_key", Text, primary_key=True),
    Column("generation_id", Text, primary_key=True),
    Column("state_key", Text, primary_key=True),
    Column("state_kind", Text, nullable=False),
    Column("event_id", Text),
    Column("body", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("state_kind IN ('partition','page','slot')", name="ck_graph_state_kind"),
    CheckConstraint("(state_kind = 'slot') = (event_id IS NOT NULL)", name="ck_graph_state_event"),
)
