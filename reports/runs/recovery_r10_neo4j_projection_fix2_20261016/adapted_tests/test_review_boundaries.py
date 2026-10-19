"""Independent observed boundaries on owned synthetic PG/Neo4j resources."""

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session
from test_r10_neo4j_projection import apply, candidates, neo4j_store
from test_r10_projection_batches import batch as synthetic_batch
from test_r10_projection_pg import PUBLIC, capture, header, manifest_for, projection_engine, published_fixture

from ai_intel.domain.access import AccessScope, Role
from ai_intel.infrastructure.neo4j_projection import Neo4jProjectionStore, projection_key
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.knowledge.evidence_graph import RELATION_TYPES
from ai_intel.knowledge.graph_projection import (
    GRAPH_APPLY_JOB_TYPE, ProjectionCapacityError, ProjectionDigestConflict, ProjectionNotReady,
    apply_projection_batch, build_graph_apply_handler, encode_projection_batch,
    read_projection_candidates,
)
from ai_intel.knowledge.graph_projection_models import graph_projection_batches, graph_projection_state
from ai_intel.knowledge.models import job_runs, scope_epochs
from ai_intel.knowledge.revisions import bump_scope_epoch
from ai_intel.workers.executor import JobExecutionContext, execute_job


def review_namespace():
    return "r10_fix2_" + uuid4().hex


@pytest.mark.real_services
@pytest.mark.parametrize("invalid_marker", ["digest", "float_sequence"])
def test_candidate_read_rejects_inconsistent_current_slot_marker(neo4j_store, invalid_marker):
    value = synthetic_batch().model_copy(update={"namespace": review_namespace()})
    digest = encode_projection_batch(value)[1]
    neo4j_store.apply_batch(value, digest)
    assert neo4j_store.find_candidates(PUBLIC, value.namespace, value.generation_id,
                                      (value.event_id,), RELATION_TYPES, 2).candidates
    key = projection_key(value.namespace, value.partition_key, str(value.generation_id), str(value.event_id))
    clause = "SET slot.payload_sha256=$bad" if invalid_marker == "digest" else "SET slot.sequence=$bad"
    invalid = "c" * 64 if invalid_marker == "digest" else 1.0
    with neo4j_store._transaction() as transaction:
        transaction.run("MATCH (slot:ProjectionSlot {projection_key:$key}) " + clause,
                        {"key": key, "bad": invalid}).consume()
    found = neo4j_store.find_candidates(PUBLIC, value.namespace, value.generation_id,
                                       (value.event_id,), RELATION_TYPES, 2)
    assert not found.candidates, "Inconsistent slot marker must not release current candidate IDs"


@pytest.mark.real_services
def test_namespaces_and_generations_are_isolated_before_traversal(neo4j_store):
    value = synthetic_batch().model_copy(update={"namespace": review_namespace()})
    neo4j_store.apply_batch(value, encode_projection_batch(value)[1])
    for namespace, generation in ((review_namespace(), value.generation_id), (value.namespace, uuid4())):
        assert not neo4j_store.find_candidates(PUBLIC, namespace, generation,
                                               (value.event_id,), RELATION_TYPES, 2).candidates


@pytest.mark.real_pg
@pytest.mark.real_services
def test_session_and_adapter_recreation_replays_unacknowledged_commit(projection_engine, neo4j_store, tmp_path):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    namespace, generation = review_namespace(), uuid4()
    manifest_for(projection_engine, generation, namespace=namespace)
    value = capture(projection_engine, generation, event_id, namespace=namespace)
    with pytest.raises(RuntimeError), Session(projection_engine) as session, session.begin():
        apply_projection_batch(session, PUBLIC, value.batch_id, neo4j_store, datetime.now(UTC))
        raise RuntimeError("review crash boundary after external commit before PG commit")
    assert header(projection_engine, generation, namespace=namespace).acknowledged_count == 0
    recreated = Neo4jProjectionStore(neo4j_store.driver)
    assert apply(projection_engine, recreated, value).outcome == "already_applied"
    assert candidates(projection_engine, recreated, value).candidates
    assert header(projection_engine, generation, namespace=namespace).acknowledged_count == 1


def test_valid_per_field_support_lists_still_cannot_exceed_eight_mib_batch():
    value = synthetic_batch()
    supports = tuple(UUID(int=index) for index in range(1, 2001))
    edges = tuple(value.edges[0].model_copy(update={
        "id": UUID(int=index + 10000), "source_revision_ids": supports,
        "evidence_span_ids": supports, "supporting_claim_ids": supports,
    }) for index in range(36))
    with pytest.raises(ProjectionCapacityError, match="graph_projection_capacity_exceeded"):
        encode_projection_batch(value.model_copy(update={"edges": edges}))


@pytest.mark.real_pg
def test_partial_manifest_is_blocked_before_external_side_effect(projection_engine, tmp_path):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    namespace, generation = review_namespace(), uuid4()
    manifest_for(projection_engine, generation, namespace=namespace)
    value = capture(projection_engine, generation, event_id, namespace=namespace)
    with projection_engine.begin() as connection:
        connection.execute(delete(graph_projection_state).where(
            graph_projection_state.c.namespace == namespace,
            graph_projection_state.c.state_kind == "page"))
    class NeverCalled:
        def apply_batch(self, _batch, _digest):
            pytest.fail("Incomplete manifest reached external side effect")
    with pytest.raises(ProjectionNotReady), Session(projection_engine) as session, session.begin():
        apply_projection_batch(session, PUBLIC, value.batch_id, NeverCalled(), datetime.now(UTC))
    assert header(projection_engine, generation, namespace=namespace).acknowledged_count == 0


@pytest.mark.real_pg
def test_worker_authorizer_receives_real_session_and_trusted_context(projection_engine, tmp_path):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    namespace, generation = review_namespace(), uuid4()
    manifest_for(projection_engine, generation, namespace=namespace)
    value = capture(projection_engine, generation, event_id, namespace=namespace)
    with projection_engine.connect() as connection:
        job_id = connection.scalar(select(job_runs.c.job_id).where(job_runs.c.job_type == GRAPH_APPLY_JOB_TYPE))
    seen = []
    def authorize(session, context):
        assert isinstance(session, Session) and isinstance(context, JobExecutionContext)
        assert context.job_id == job_id and context.tenant_id is None
        assert session.scalar(select(func.count()).select_from(graph_projection_batches)) == 1
        seen.append(context)
        return AccessScope.for_authenticated_user("review-user", "other", Role.ANALYST)
    class NeverCalled:
        def apply_batch(self, _batch, _digest):
            pytest.fail("Wrong trusted scope reached external store")
    handler = build_graph_apply_handler(NeverCalled(), authorize)
    assert execute_job(projection_engine, job_id, "review-worker", {GRAPH_APPLY_JOB_TYPE: handler}) == "blocked"
    assert len(seen) == 1
    assert header(projection_engine, generation, namespace=namespace).acknowledged_count == 0


@pytest.mark.real_pg
def test_payload_cannot_self_assign_worker_scope(projection_engine):
    now = datetime.now(UTC)
    with Session(projection_engine) as session, session.begin():
        job = enqueue_job(session, None, GRAPH_APPLY_JOB_TYPE,
                          json.dumps({"batch_id": str(uuid4()), "tenant_id": "victim"}).encode(), now,
                          idempotency_key="review-forged-scope")
    seen = []
    handler = build_graph_apply_handler(object(), lambda session, context: seen.append(context))
    assert execute_job(projection_engine, job, "review-worker", {GRAPH_APPLY_JOB_TYPE: handler}) == "blocked"
    assert not seen
    with projection_engine.connect() as connection:
        assert connection.scalar(select(job_runs.c.error_code).where(job_runs.c.job_id == job)) == "invalid_job_payload"


@pytest.mark.real_pg
def test_unknown_io_retries_are_bounded_and_do_not_ack(projection_engine, tmp_path):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    namespace, generation = review_namespace(), uuid4()
    manifest_for(projection_engine, generation, namespace=namespace)
    capture(projection_engine, generation, event_id, namespace=namespace)
    with projection_engine.connect() as connection:
        job_id = connection.scalar(select(job_runs.c.job_id).where(job_runs.c.job_type == GRAPH_APPLY_JOB_TYPE))
    class Unavailable:
        def apply_batch(self, _batch, _digest):
            raise ConnectionError("review synthetic unavailable external IO")
    handler = build_graph_apply_handler(Unavailable(), lambda session, context: PUBLIC)
    at = datetime.now(UTC)
    outcomes = []
    for attempt in range(5):
        current = at + timedelta(seconds=400 * attempt)
        outcomes.append(execute_job(projection_engine, job_id, "review-worker", {GRAPH_APPLY_JOB_TYPE: handler}, clock=lambda: current))
    assert outcomes == ["retry_wait"] * 4 + ["failed"]
    with projection_engine.connect() as connection:
        row = connection.execute(select(job_runs.c.attempt_count, job_runs.c.error_code).where(job_runs.c.job_id == job_id)).one()
    assert row == (5, "handler_failed")
    assert header(projection_engine, generation, namespace=namespace).acknowledged_count == 0


@pytest.mark.real_pg
def test_missing_authoritative_epoch_is_deterministic_blocked(projection_engine, tmp_path):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    namespace, generation = review_namespace(), uuid4()
    manifest_for(projection_engine, generation, namespace=namespace)
    capture(projection_engine, generation, event_id, namespace=namespace)
    with projection_engine.begin() as connection:
        job_id = connection.scalar(select(job_runs.c.job_id).where(job_runs.c.job_type == GRAPH_APPLY_JOB_TYPE))
        connection.execute(delete(scope_epochs).where(scope_epochs.c.scope_key == "public"))
    class NeverCalled:
        def apply_batch(self, _batch, _digest):
            pytest.fail("Missing epoch reached external side effect")
    handler = build_graph_apply_handler(NeverCalled(), lambda session, context: PUBLIC)
    outcome = execute_job(projection_engine, job_id, "review-worker", {GRAPH_APPLY_JOB_TYPE: handler})
    assert header(projection_engine, generation, namespace=namespace).acknowledged_count == 0
    assert outcome == "blocked", "Missing authoritative epoch is a deterministic state error, not unknown IO"


@pytest.mark.real_pg
@pytest.mark.real_services
def test_candidate_hash_must_match_pg_ack_not_only_neo4j_marker(projection_engine, neo4j_store, tmp_path):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    namespace, generation = review_namespace(), uuid4()
    manifest_for(projection_engine, generation, namespace=namespace)
    value = capture(projection_engine, generation, event_id, namespace=namespace)
    apply(projection_engine, neo4j_store, value)
    expected_digest = encode_projection_batch(value)[1]
    assert header(projection_engine, generation, namespace=namespace).status == "ready"
    key = projection_key(namespace, "public", str(generation), str(event_id))
    with neo4j_store._transaction() as transaction:
        transaction.run("MATCH(slot:ProjectionSlot {projection_key:$key}) SET slot.payload_sha256=$bad",
                        {"key": key, "bad": "c" * 64}).consume()
        transaction.run("MATCH()-[edge:INTEL_RELATION]->() WHERE edge.namespace=$namespace "
                        "SET edge.payload_sha256=$bad",
                        {"namespace": namespace, "bad": "c" * 64}).consume()
    with Session(projection_engine) as session:
        try:
            found = read_projection_candidates(session, PUBLIC, namespace, generation,
                                               (event_id,), neo4j_store)
        except (ProjectionDigestConflict, ProjectionNotReady):
            return
    assert not found.candidates, (
        "Candidates with a derived hash disagreeing with PG ACK must be rejected; "
        f"expected={expected_digest}, actual={[item.payload_sha256 for item in found.candidates]}"
    )
