"""Fault only owned projection markers on real isolated PG and Neo4j resources."""

from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import delete, select, update
from sqlalchemy.engine import make_url
from test_r10_neo4j_projection import apply, candidates
from test_r10_neo4j_projection import neo4j_store as neo4j_store
from test_r10_projection_batches import batch as synthetic_batch
from test_r10_projection_pg import (
    PUBLIC,
    capture,
    header,
    manifest_for,
    published_fixture,
)
from test_r10_projection_pg import projection_engine as projection_engine

from ai_intel.infrastructure.neo4j_projection import projection_key
from ai_intel.knowledge.evidence_graph import RELATION_TYPES
from ai_intel.knowledge.graph_projection import (
    GRAPH_APPLY_JOB_TYPE,
    ProjectionDigestConflict,
    ProjectionNotReady,
    build_graph_apply_handler,
    encode_projection_batch,
)
from ai_intel.knowledge.graph_projection_models import graph_projection_state
from ai_intel.knowledge.models import job_runs, scope_epochs
from ai_intel.workers.executor import execute_job


@pytest.fixture(autouse=True)
def register_owned_pg_failure_credentials(
    register_sensitive_failure_value, isolated_test_database_url
):
    register_sensitive_failure_value(SecretStr(isolated_test_database_url))
    password = make_url(isolated_test_database_url).password
    if password:
        register_sensitive_failure_value(SecretStr(password))


@pytest.mark.real_services
@pytest.mark.parametrize(
    "field,bad",
    [
        ("sequence", True),
        ("sequence", 1.0),
        ("payload_sha256", "c" * 64),
        ("namespace", "other"),
        ("partition_key", "tenant:other"),
        ("generation_id", "00000000-0000-0000-0000-000000000000"),
        ("event_id", "00000000-0000-0000-0000-000000000000"),
    ],
)
def test_bad_marker_identity_type_or_digest_is_filtered_and_restore_is_safe(
    neo4j_store, field, bad
):
    value = synthetic_batch().model_copy(update={"namespace": "r10_fix1_" + uuid4().hex})
    digest = encode_projection_batch(value)[1]
    neo4j_store.apply_batch(value, digest)
    key = projection_key(
        value.namespace, value.partition_key, str(value.generation_id), str(value.event_id)
    )
    original = {
        "sequence": value.sequence,
        "payload_sha256": digest,
        "namespace": value.namespace,
        "partition_key": value.partition_key,
        "generation_id": str(value.generation_id),
        "event_id": str(value.event_id),
    }
    query = "MATCH(slot:ProjectionSlot {projection_key:$key}) SET slot += $changes"
    with neo4j_store._transaction() as transaction:
        transaction.run(query, {"key": key, "changes": {field: bad}}).consume()
    assert not neo4j_store.find_candidates(
        PUBLIC, value.namespace, value.generation_id, (value.event_id,), RELATION_TYPES, 2
    ).candidates
    with neo4j_store._transaction() as transaction:
        transaction.run(query, {"key": key, "changes": {field: original[field]}}).consume()
    assert len(
        neo4j_store.find_candidates(
            PUBLIC, value.namespace, value.generation_id, (value.event_id,), RELATION_TYPES, 2
        ).candidates
    ) == len(value.edges)


@pytest.mark.real_pg
@pytest.mark.real_services
@pytest.mark.parametrize(
    "field,bad",
    [
        ("acknowledged_sha256", "c" * 64),
        ("acknowledged_sequence", 1.0),
        ("captured_sequence", True),
        ("batch_id", "00000000-0000-0000-0000-000000000000"),
    ],
)
def test_pg_ack_is_required_and_restore_preserves_legitimate_read(
    projection_engine, neo4j_store, tmp_path, field, bad
):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    namespace, generation = "r10_fix1_" + uuid4().hex, uuid4()
    manifest_for(projection_engine, generation, namespace=namespace)
    value = capture(projection_engine, generation, event_id, namespace=namespace)
    apply(projection_engine, neo4j_store, value)
    assert candidates(projection_engine, neo4j_store, value).candidates
    predicate = (graph_projection_state.c.namespace == namespace) & (
        graph_projection_state.c.state_key == "event:" + str(event_id)
    )
    with projection_engine.begin() as connection:
        original = connection.scalar(select(graph_projection_state.c.body).where(predicate))
        connection.execute(
            update(graph_projection_state).where(predicate).values(body={**original, field: bad})
        )
    with pytest.raises((ProjectionDigestConflict, ProjectionNotReady)):
        candidates(projection_engine, neo4j_store, value)
    with projection_engine.begin() as connection:
        connection.execute(update(graph_projection_state).where(predicate).values(body=original))
    assert candidates(projection_engine, neo4j_store, value).candidates
    assert header(projection_engine, generation, namespace=namespace).acknowledged_count == 1


@pytest.mark.real_pg
def test_missing_epoch_job_uses_fixed_state_code_without_side_effect(projection_engine, tmp_path):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    namespace, generation = "r10_fix1_" + uuid4().hex, uuid4()
    manifest_for(projection_engine, generation, namespace=namespace)
    capture(projection_engine, generation, event_id, namespace=namespace)
    with projection_engine.begin() as connection:
        job_id = connection.scalar(
            select(job_runs.c.job_id).where(job_runs.c.job_type == GRAPH_APPLY_JOB_TYPE)
        )
        connection.execute(delete(scope_epochs).where(scope_epochs.c.scope_key == "public"))

    class NeverCalled:
        def apply_batch(self, _batch, _digest):
            pytest.fail("Missing authoritative epoch reached Neo4j")

    handler = build_graph_apply_handler(NeverCalled(), lambda _session, _context: PUBLIC)
    assert (
        execute_job(
            projection_engine, job_id, "fix-fixture-worker", {GRAPH_APPLY_JOB_TYPE: handler}
        )
        == "blocked"
    )
    with projection_engine.connect() as connection:
        result = connection.execute(
            select(job_runs.c.error_code, job_runs.c.attempt_count).where(
                job_runs.c.job_id == job_id
            )
        ).one()
    assert result == ("graph_projection_state_unavailable", 1)
    assert header(projection_engine, generation, namespace=namespace).acknowledged_count == 0
