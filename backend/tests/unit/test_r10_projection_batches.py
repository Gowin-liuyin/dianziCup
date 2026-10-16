"""Explicit synthetic batch tests; no database or Neo4j connection."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from ai_intel.domain.values import VisibilityScope
from ai_intel.knowledge.evidence_graph import GraphEdge, GraphNode, GraphSnapshot
from ai_intel.knowledge.graph_projection import (
    ProjectionCapacityError,
    ProjectionDigestConflict,
    decode_projection_batch,
    encode_projection_batch,
    make_projection_batch,
    projection_apply_decision,
)

NOW = datetime(2026, 10, 16, tzinfo=UTC)


def snapshot(*, truncated: bool = False) -> GraphSnapshot:
    event_id, target_id = UUID(int=1), UUID(int=2)
    scope = VisibilityScope(visibility="public")
    return GraphSnapshot(
        event_id=event_id,
        business_version=1,
        nodes=(
            GraphNode(id=event_id, kind="event", label="Synthetic event", scope=scope),
            GraphNode(id=target_id, kind="source_revision", label="Synthetic source", scope=scope),
        ),
        edges=(
            GraphEdge(
                id=UUID(int=3),
                relation_type="same_event",
                subject_id=event_id,
                object_id=target_id,
                scope=scope,
                source_revision_ids=(UUID(int=4),),
                evidence_span_ids=(UUID(int=5),),
                supporting_claim_ids=(UUID(int=6),),
                reason="Synthetic source support",
            ),
        ),
        truncated=truncated,
        gaps=(),
        content_sha256="a" * 64,
    )


def batch():
    return make_projection_batch(
        snapshot(),
        namespace="r10-test",
        partition_key="public",
        generation_id=uuid4(),
        sequence=1,
        scope_epochs=(("public", 1),),
        input_sha256="b" * 64,
        captured_at=NOW,
    )


def test_batch_keeps_support_identity_but_does_not_copy_sensitive_text():
    value = batch()
    encoded, digest = encode_projection_batch(value)
    assert decode_projection_batch(encoded, digest) == value
    assert value.edges[0].evidence_span_ids == (UUID(int=5),)
    assert value.edges[0].supporting_claim_ids == (UUID(int=6),)
    assert b"Synthetic" not in encoded and b"reason" not in encoded and b"label" not in encoded


def test_truncated_graph_cannot_become_complete_projection_batch():
    with pytest.raises(ProjectionCapacityError):
        make_projection_batch(
            snapshot(truncated=True),
            namespace="r10-test",
            partition_key="public",
            generation_id=uuid4(),
            sequence=1,
            scope_epochs=(("public", 1),),
            input_sha256="b" * 64,
            captured_at=NOW,
        )


def test_hash_tampering_is_not_an_empty_success():
    encoded, digest = encode_projection_batch(batch())
    with pytest.raises(ProjectionDigestConflict):
        decode_projection_batch(encoded.replace(b'"sequence":1', b'"sequence":2'), digest)


@pytest.mark.parametrize(
    "current,incoming,stored,proposed,expected",
    [
        (1, 2, "a" * 64, "b" * 64, "applied"),
        (2, 1, "b" * 64, "a" * 64, "superseded"),
        (2, 2, "b" * 64, "b" * 64, "already_applied"),
    ],
)
def test_duplicate_and_out_of_order_receipts(current, incoming, stored, proposed, expected):
    assert projection_apply_decision(current, incoming, stored, proposed) == expected


def test_equal_sequence_with_different_digest_is_corruption():
    with pytest.raises(ProjectionDigestConflict):
        projection_apply_decision(2, 2, "a" * 64, "b" * 64)
