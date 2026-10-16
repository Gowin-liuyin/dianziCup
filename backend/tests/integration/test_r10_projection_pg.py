"""Real owned PG with explicitly synthetic graph-store fixtures; not Neo4j/live evidence."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, func, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema
from test_r02_knowledge_revisions import NOW
from test_r10_evidence_graph_pg import VERSION, publish_event, publish_fact

from ai_intel.domain.access import AccessScope, CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.domain.values import VisibilityScope
from ai_intel.infrastructure.database import run_migrations
from ai_intel.knowledge.graph_projection import (
    GRAPH_APPLY_JOB_TYPE,
    GraphCandidateSet,
    ProjectionCapacityError,
    ProjectionNotReady,
    ProjectionReceipt,
    ReconciliationManifest,
    apply_projection_batch,
    begin_reconciliation,
    build_graph_apply_handler,
    capture_event_projection,
    list_projection_history,
    projection_apply_decision,
    read_manifest_page,
    read_projection_batch,
    read_projection_candidates,
)
from ai_intel.knowledge.graph_projection_models import (
    graph_projection_batches,
    graph_projection_state,
)
from ai_intel.knowledge.models import evidence, job_runs, metadata, outbox_events
from ai_intel.knowledge.persistence_models import claim_evidence, claims, events
from ai_intel.knowledge.revisions import bump_scope_epoch
from ai_intel.workers.executor import execute_job

pytestmark = pytest.mark.real_pg
PUBLIC = AccessScope.for_authenticated_user("fixture-viewer", None, Role.VIEWER)


@pytest.fixture
def projection_engine(isolated_test_database_url):
    url = make_url(isolated_test_database_url)
    assert url.database == "test_dianzi_r10_projection_20261016"
    assert url.host == "127.0.0.1" and url.port == 25432
    if not url.username or not url.username.startswith("test_"):
        raise RuntimeError("owned PostgreSQL role mismatch")
    schema = "test_r10_projection_" + uuid4().hex
    base = create_engine(url, connect_args={"connect_timeout": 5})
    with base.begin() as connection:
        database, user = connection.execute(text("SELECT current_database(),current_user")).one()
        if database != url.database or user != url.username:
            raise RuntimeError("owned PostgreSQL identity mismatch")
        owner = connection.execute(
            text(
                "SELECT pg_get_userbyid(datdba), shobj_description(oid,'pg_database') "
                "FROM pg_database WHERE datname=:name"
            ),
            {"name": url.database},
        ).one()
        if owner != (url.username, "dianzi:r10_projection_20261016:owned-test-only"):
            raise RuntimeError("owned PostgreSQL marker mismatch")
        connection.execute(CreateSchema(schema))
    isolated = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=5000"}
    )
    run_migrations(isolated.render_as_string(hide_password=False))
    engine = create_engine(isolated, connect_args={"connect_timeout": 5})
    with engine.begin() as connection:
        metadata.create_all(connection, tables=[graph_projection_batches, graph_projection_state])
    try:
        yield engine
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


class SyntheticGraphStore:
    """Explicit non-Neo4j fixture used only to isolate PG acknowledgment behavior."""

    def __init__(self):
        self.markers = {}
        self.failure = None

    def apply_batch(self, batch, digest):
        if self.failure == "before":
            raise ConnectionError("synthetic store unavailable")
        key = (batch.namespace, batch.partition_key, batch.generation_id, batch.event_id)
        sequence, stored = self.markers.get(key, (0, ""))
        outcome = projection_apply_decision(sequence, batch.sequence, stored, digest)
        if outcome == "applied":
            self.markers[key] = (batch.sequence, digest)
        if self.failure == "after":
            raise ConnectionError("synthetic acknowledgment lost")
        return ProjectionReceipt(
            batch_id=batch.batch_id, sequence=batch.sequence, payload_sha256=digest, outcome=outcome
        )

    def find_candidates(self, *_args):
        return GraphCandidateSet(candidates=(), truncated=False)


def published_fixture(engine, path, visibility=None):
    event_id = uuid4()
    source = publish_fact(engine, path, event_id, VERSION, scope=visibility)
    publish_event(engine, event_id, [source], scope=visibility)
    return event_id, source


def manifest_for(engine, generation, scope=PUBLIC, namespace="r10-test"):
    with Session(engine) as session, session.begin():
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        return begin_reconciliation(session, scope, namespace, generation, NOW)


def capture(engine, generation, event_id, scope=PUBLIC, namespace="r10-test"):
    return capture_event_projection(
        engine,
        scope,
        namespace,
        generation,
        event_id,
        authorize=lambda _session: scope,
        captured_at=NOW,
    )


def header(engine, generation, scope=PUBLIC, namespace="r10-test"):
    with Session(engine) as session:
        row = session.execute(
            select(graph_projection_state.c.body).where(
                graph_projection_state.c.namespace == namespace,
                graph_projection_state.c.generation_id == str(generation),
                graph_projection_state.c.partition_key
                == ("public" if scope == PUBLIC else "tenant:" + scope.tenant_id),
                graph_projection_state.c.state_key == "partition",
            )
        ).scalar_one()
        import json

        return ReconciliationManifest.model_validate_json(json.dumps(row))


def test_real_pg_capture_queues_only_reference_and_is_idempotent(projection_engine, tmp_path):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    generation = uuid4()
    manifest_for(projection_engine, generation)
    first = capture(projection_engine, generation, event_id)
    second = capture(projection_engine, generation, event_id)
    assert first == second and len(first.edges) == 5
    with projection_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(graph_projection_batches)) == 1
        assert (
            connection.scalar(
                select(func.count())
                .select_from(outbox_events)
                .where(outbox_events.c.topic == "job.graph_apply")
            )
            == 1
        )
    assert header(projection_engine, generation).captured_count == 1
    assert header(projection_engine, generation).status == "pending"


@pytest.mark.parametrize("failure", ["before", "after"])
def test_failed_side_effect_does_not_ack_and_replay_is_safe(projection_engine, tmp_path, failure):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    generation = uuid4()
    manifest_for(projection_engine, generation)
    batch = capture(projection_engine, generation, event_id)
    store = SyntheticGraphStore()
    store.failure = failure
    with pytest.raises(ConnectionError), Session(projection_engine) as session, session.begin():
        apply_projection_batch(session, PUBLIC, batch.batch_id, store, NOW)
    assert header(projection_engine, generation).acknowledged_count == 0
    store.failure = None
    with Session(projection_engine) as session, session.begin():
        receipt = apply_projection_batch(session, PUBLIC, batch.batch_id, store, NOW)
    assert receipt.outcome == ("already_applied" if failure == "after" else "applied")
    assert header(projection_engine, generation).status == "ready"
    with Session(projection_engine) as session, session.begin():
        apply_projection_batch(session, PUBLIC, batch.batch_id, store, NOW)
    assert header(projection_engine, generation).acknowledged_count == 1


def test_two_capture_workers_create_one_batch(projection_engine, tmp_path):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    generation = uuid4()
    manifest_for(projection_engine, generation)
    barrier = Barrier(2)

    def worker():
        barrier.wait(timeout=10)
        return capture(projection_engine, generation, event_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker) for _ in range(2)]
        batches = [future.result(timeout=20) for future in futures]
    assert batches[0].batch_id == batches[1].batch_id
    assert header(projection_engine, generation).captured_count == 1


def test_manifest_pages_preserve_empty_events_and_do_not_infer_max_epoch(projection_engine):
    ids = sorted(uuid4() for _ in range(101))
    with projection_engine.begin() as connection:
        connection.execute(
            insert(events),
            [
                dict(
                    event_id=str(value),
                    event_type="vulnerability",
                    title="Synthetic empty graph",
                    scope_key="public",
                    visibility="public",
                    tenant_id=None,
                    status="active",
                    first_seen_at=NOW,
                )
                for value in ids
            ],
        )
        bump_scope_epoch(connection, "public", NOW)
    generation = uuid4()
    manifest = manifest_for(projection_engine, generation)
    with Session(projection_engine) as session:
        pages = [
            read_manifest_page(session, PUBLIC, "r10-test", generation, index) for index in range(2)
        ]
    assert manifest.page_count == 2 and manifest.event_count == 101
    assert [entry.event_id for page in pages for entry in page.entries] == ids
    batch = capture(projection_engine, generation, ids[0])
    assert not batch.edges and len(batch.nodes) == 1
    with Session(projection_engine) as session, session.begin():
        apply_projection_batch(session, PUBLIC, batch.batch_id, SyntheticGraphStore(), NOW)
    assert header(projection_engine, generation).status == "pending"
    assert header(projection_engine, generation).acknowledged_count == 1


def test_claim_withdrawal_and_empty_scope_create_new_snapshot_and_tombstone(
    projection_engine, tmp_path
):
    event_id, source = published_fixture(projection_engine, tmp_path)
    generation = uuid4()
    manifest_for(projection_engine, generation)
    first = capture(projection_engine, generation, event_id)
    with projection_engine.begin() as connection:
        connection.execute(
            update(claims)
            .where(claims.c.claim_id == source.record.claim_id.value)
            .values(claim_status="withdrawn")
        )
        bump_scope_epoch(connection, "public", NOW)
    empty_generation = uuid4()
    manifest_for(projection_engine, empty_generation)
    empty = capture(projection_engine, empty_generation, event_id)
    assert first.edges and not empty.edges and empty.kind == "snapshot"
    with projection_engine.begin() as connection:
        connection.execute(
            update(events).where(events.c.event_id == str(event_id)).values(status="merged")
        )
        bump_scope_epoch(connection, "public", NOW)
    tombstone_generation = uuid4()
    manifest_for(projection_engine, tombstone_generation)
    tombstone = capture(projection_engine, tombstone_generation, event_id)
    assert tombstone.kind == "tombstone" and not tombstone.nodes and not tombstone.edges


def test_epoch_change_prevents_ready_or_candidate_success(projection_engine, tmp_path):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    generation = uuid4()
    manifest_for(projection_engine, generation)
    batch = capture(projection_engine, generation, event_id)
    with projection_engine.begin() as connection:
        bump_scope_epoch(connection, "public", NOW)
    with Session(projection_engine) as session, session.begin():
        apply_projection_batch(session, PUBLIC, batch.batch_id, SyntheticGraphStore(), NOW)
    assert header(projection_engine, generation).status == "stale"
    with pytest.raises(ProjectionNotReady), Session(projection_engine) as session:
        read_projection_candidates(
            session, PUBLIC, "r10-test", generation, (event_id,), SyntheticGraphStore()
        )


def test_private_batch_is_invisible_to_viewer_and_other_tenant(projection_engine, tmp_path):
    visibility = VisibilityScope(visibility="tenant", tenant_id="owner")
    event_id, _source = published_fixture(projection_engine, tmp_path, visibility)
    owner = AccessScope.for_authenticated_user("owner-user", "owner", Role.ANALYST)
    with projection_engine.begin() as connection:
        bump_scope_epoch(connection, "public", NOW)
    generation = uuid4()
    manifest_for(projection_engine, generation, owner)
    batch = capture(projection_engine, generation, event_id, owner)
    for rejected in (PUBLIC, AccessScope.for_authenticated_user("other", "other", Role.ANALYST)):
        with pytest.raises(CrossTenantAccessError), Session(projection_engine) as session:
            read_projection_batch(session, rejected, batch.batch_id)
    assert all(edge.scope == visibility for edge in batch.edges)


def test_fresh_authorization_change_cannot_save_batch(projection_engine, tmp_path):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    generation = uuid4()
    manifest_for(projection_engine, generation)
    changed = AccessScope.for_authenticated_user("changed-user", None, Role.VIEWER)
    with pytest.raises(PermissionDeniedError):
        capture_event_projection(
            projection_engine,
            PUBLIC,
            "r10-test",
            generation,
            event_id,
            authorize=lambda _session: changed,
            captured_at=NOW,
        )
    with projection_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(graph_projection_batches)) == 0


def test_real_2001_support_capacity_does_not_capture_or_advance(projection_engine, tmp_path):
    event_id, source = published_fixture(projection_engine, tmp_path)
    with projection_engine.begin() as connection:
        original = dict(
            connection.execute(
                select(evidence).where(
                    evidence.c.evidence_id == source.evidence_links[0].evidence_id.value,
                )
            )
            .mappings()
            .one()
        )
        identifiers = [str(uuid4()) for _ in range(2001)]
        connection.execute(
            insert(evidence),
            [{**original, "evidence_id": identifier} for identifier in identifiers],
        )
        connection.execute(
            insert(claim_evidence),
            [
                dict(
                    claim_id=source.record.claim_id.value,
                    evidence_id=identifier,
                    support_kind="supports",
                    validation_status="validated",
                )
                for identifier in identifiers
            ],
        )
        bump_scope_epoch(connection, "public", NOW)
    generation = uuid4()
    manifest_for(projection_engine, generation)
    with pytest.raises(ProjectionCapacityError):
        capture(projection_engine, generation, event_id)
    assert header(projection_engine, generation).captured_count == 0
    assert header(projection_engine, generation).status == "pending"
    with projection_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(graph_projection_batches)) == 0


def test_genuinely_empty_manifest_is_versioned_and_becomes_stale_after_new_event(projection_engine):
    with projection_engine.begin() as connection:
        bump_scope_epoch(connection, "public", NOW)
    generation = uuid4()
    manifest = manifest_for(projection_engine, generation)
    assert manifest.event_count == 0 and manifest.page_count == 0 and manifest.status == "ready"
    with projection_engine.begin() as connection:
        connection.execute(
            insert(events).values(
                event_id=str(uuid4()),
                event_type="vulnerability",
                title="Synthetic formerly empty hit",
                scope_key="public",
                visibility="public",
                tenant_id=None,
                status="active",
                first_seen_at=NOW,
            )
        )
        bump_scope_epoch(connection, "public", NOW)
    with pytest.raises(ProjectionNotReady), Session(projection_engine) as session:
        read_projection_candidates(
            session, PUBLIC, "r10-test", generation, (uuid4(),), SyntheticGraphStore()
        )


def test_missing_manifest_page_is_not_a_complete_watermark(projection_engine, tmp_path):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    generation = uuid4()
    manifest_for(projection_engine, generation)
    batch = capture(projection_engine, generation, event_id)
    with Session(projection_engine) as session, session.begin():
        apply_projection_batch(session, PUBLIC, batch.batch_id, SyntheticGraphStore(), NOW)
    with projection_engine.begin() as connection:
        connection.execute(
            delete(graph_projection_state).where(
                graph_projection_state.c.generation_id == str(generation),
                graph_projection_state.c.state_kind == "page",
            )
        )
    with pytest.raises(ProjectionNotReady), Session(projection_engine) as session:
        read_projection_candidates(
            session, PUBLIC, "r10-test", generation, (event_id,), SyntheticGraphStore()
        )


def test_history_is_bounded_and_cannot_return_other_partition_content(projection_engine, tmp_path):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    captured = []
    for _ in range(3):
        generation = uuid4()
        manifest_for(projection_engine, generation)
        captured.append(capture(projection_engine, generation, event_id))
    with Session(projection_engine) as session:
        first = list_projection_history(session, PUBLIC, "r10-test", event_id, limit=1)
        second = list_projection_history(
            session,
            PUBLIC,
            "r10-test",
            event_id,
            limit=1,
            after=(first[0].captured_at, first[0].batch_id),
        )
        other = AccessScope.for_authenticated_user("other", "other", Role.ANALYST)
        assert not list_projection_history(session, other, "r10-test", event_id)
        with pytest.raises(ValueError):
            list_projection_history(session, PUBLIC, "r10-test", event_id, limit=101)
    assert len(first) == len(second) == 1 and first[0].batch_id != second[0].batch_id
    assert not hasattr(first[0], "payload") and not hasattr(first[0], "nodes")


@pytest.mark.parametrize("failure", ["scope", "missing_page"])
def test_graph_job_boundary_failure_blocks_without_ack(projection_engine, tmp_path, failure):
    scope = PUBLIC
    visibility = VisibilityScope(visibility="public")
    if failure == "scope":
        scope = AccessScope.for_authenticated_user("owner", "owner", Role.ANALYST)
        visibility = VisibilityScope(visibility="tenant", tenant_id="owner")
    event_id, _source = published_fixture(projection_engine, tmp_path, visibility)
    with projection_engine.begin() as connection:
        bump_scope_epoch(connection, "public", NOW)
    generation = uuid4()
    manifest_for(projection_engine, generation, scope)
    capture(projection_engine, generation, event_id, scope)
    with projection_engine.begin() as connection:
        job_id = connection.scalar(
            select(job_runs.c.job_id).where(job_runs.c.job_type == GRAPH_APPLY_JOB_TYPE)
        )
        if failure == "missing_page":
            connection.execute(
                delete(graph_projection_state).where(
                    graph_projection_state.c.generation_id == str(generation),
                    graph_projection_state.c.state_kind == "page",
                )
            )
    handler = build_graph_apply_handler(SyntheticGraphStore(), lambda _session, _context: PUBLIC)
    assert (
        execute_job(
            projection_engine, job_id, "owned-fixture-worker", {GRAPH_APPLY_JOB_TYPE: handler}
        )
        == "blocked"
    )
    with projection_engine.connect() as connection:
        error_code = connection.scalar(
            select(job_runs.c.error_code).where(job_runs.c.job_id == job_id)
        )
    assert error_code == (
        "graph_projection_scope_denied"
        if failure == "scope"
        else "graph_projection_state_unavailable"
    )
    assert header(projection_engine, generation, scope).acknowledged_count == 0
