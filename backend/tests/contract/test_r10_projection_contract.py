"""Synthetic strict DTO and size boundaries; no service/driver connection."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from ai_intel.knowledge.graph_projection import (
    MAX_BATCH_BYTES,
    GraphCandidateSet,
    GraphProjectionBatch,
    ProjectionCapacityError,
    ReconciliationManifest,
    decode_projection_batch,
    encode_projection_batch,
)


def tombstone():
    return GraphProjectionBatch(
        batch_id=uuid4(),
        namespace="r10-test",
        partition_key="public",
        generation_id=uuid4(),
        event_id=uuid4(),
        sequence=1,
        kind="tombstone",
        scope_epochs=(("public", 1),),
        input_sha256="a" * 64,
        full_graph_sha256="b" * 64,
        nodes=(),
        edges=(),
        captured_at=datetime(2026, 10, 16, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("sequence", True),
        ("sequence", "1"),
        ("schema_version", True),
        ("schema_version", 1.0),
        ("scope_epochs", (("public", 0),)),
        ("scope_epochs", ()),
        ("scope_epochs", (("tenant:other", 1),)),
        ("namespace", "../../escape"),
        ("kind", "empty_success"),
        ("event_business_version", 1),
        ("rule_version", "model-guessed"),
        ("captured_at", datetime(2026, 10, 16)),
    ],
)
def test_invalid_batch_boundary_is_rejected(field, value):
    payload = tombstone().model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        GraphProjectionBatch.model_validate(payload)


@pytest.mark.parametrize(
    "field,value",
    [("tenant_id", "other"), ("cypher", "MATCH(n) RETURN n"), ("url", "http://127.0.0.1")],
)
def test_payload_does_not_offer_tenant_query_or_url_input(field, value):
    payload = tombstone().model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        GraphProjectionBatch.model_validate(payload)


def test_oversized_bytes_are_capacity_error_without_parsing_or_success():
    with pytest.raises(ProjectionCapacityError):
        decode_projection_batch(b"x" * (MAX_BATCH_BYTES + 1), "a" * 64)


def test_model_copy_cannot_bypass_encoded_contract():
    value = tombstone().model_copy(update={"sequence": False})
    with pytest.raises(ValidationError):
        encode_projection_batch(value)


def test_manifest_ready_requires_every_captured_event_ack():
    with pytest.raises(ValidationError):
        ReconciliationManifest(
            namespace="r10-test",
            partition_key="public",
            generation_id=UUID(int=1),
            scope_epochs=(("public", 1),),
            manifest_sha256="a" * 64,
            page_count=2,
            event_count=101,
            captured_count=101,
            acknowledged_count=100,
            status="ready",
        )


def test_candidate_revalidation_flag_cannot_be_coerced_or_disabled():
    for value in (1, "true", False):
        with pytest.raises(ValidationError):
            GraphCandidateSet.model_validate(
                {"candidates": (), "truncated": False, "requires_pg_revalidation": value}
            )
