"""Real PG execution chain with a marked synthetic graph store; requires owned resources."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from test_r10_projection_pg import PUBLIC, SyntheticGraphStore, published_fixture
from test_r10_projection_pg import projection_engine as projection_engine

from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.knowledge.graph_projection import (
    ProjectionCapacityError,
    ProjectionNotReady,
    begin_reconciliation,
    read_projection_scope_epochs,
    read_reconciliation_manifest,
)
from ai_intel.knowledge.graph_projection_models import graph_projection_batches
from ai_intel.knowledge.graph_runtime_policy import (
    DEFAULT_GRAPH_NAMESPACE,
    GraphReconciliationRequest,
    build_graph_runtime_policy,
    graph_generation_id,
)
from ai_intel.knowledge.models import job_runs
from ai_intel.knowledge.persistence_models import events
from ai_intel.knowledge.revisions import bump_scope_epoch
from ai_intel.workers.executor import execute_job

pytestmark = pytest.mark.real_pg


def runtime_for(engine, **budget):
    return build_graph_runtime_policy(
        engine, SyntheticGraphStore(), lambda _s, _c: PUBLIC, **budget
    )


def change_job(engine):
    with Session(engine) as session:
        return session.scalar(
            select(job_runs.c.job_id)
            .where(
                job_runs.c.job_type == "knowledge_change",
                job_runs.c.status == "queued",
                job_runs.c.tenant_id.is_(None),
            )
            .order_by(job_runs.c.created_at.desc())
            .limit(1)
        )


def run_graph_jobs(engine, runtime):
    outcomes = []
    for _ in range(30):
        with Session(engine) as session:
            pending = session.execute(
                select(job_runs.c.job_id, job_runs.c.job_type)
                .where(
                    job_runs.c.job_type.in_(runtime.job_handlers),
                    job_runs.c.status == "queued",
                )
                .order_by(job_runs.c.created_at, job_runs.c.job_id)
                .limit(1)
            ).first()
        if pending is None:
            return outcomes
        result = execute_job(
            engine, pending.job_id, "pg-graph-fixture-" + uuid4().hex, runtime.job_handlers
        )
        outcomes.append((pending.job_type, result))
    raise AssertionError("graph fixture job bound exhausted")


def current_manifest(engine):
    with Session(engine) as session:
        epochs = read_projection_scope_epochs(session, PUBLIC)
        generation = graph_generation_id(DEFAULT_GRAPH_NAMESPACE, "public", epochs)
        return read_reconciliation_manifest(session, PUBLIC, DEFAULT_GRAPH_NAMESPACE, generation)


def test_real_publication_fans_out_captures_and_applies_while_shared_job_stays_partial(
    projection_engine,
    tmp_path,
):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    runtime = runtime_for(projection_engine)
    parent_id = change_job(projection_engine)
    assert parent_id is not None
    assert (
        execute_job(
            projection_engine,
            parent_id,
            "pg-parent-fixture",
            {
                "knowledge_change": runtime.knowledge_change_handler,
            },
        )
        == "partial"
    )
    outcomes = run_graph_jobs(projection_engine, runtime)
    assert outcomes == [
        ("graph_reconcile", "partial"),
        ("graph_capture", "partial"),
        ("graph_apply", "succeeded"),
    ]
    manifest = current_manifest(projection_engine)
    assert manifest.status == "ready" and manifest.event_count == manifest.acknowledged_count == 1
    with Session(projection_engine) as session:
        assert (
            session.scalar(select(job_runs.c.status).where(job_runs.c.job_id == parent_id))
            == "partial"
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(graph_projection_batches)
                .where(
                    graph_projection_batches.c.event_id == str(event_id),
                )
            )
            == 1
        )


def test_multiple_publications_at_same_epoch_reuse_one_graph_job(projection_engine, tmp_path):
    published_fixture(projection_engine, tmp_path)
    runtime = runtime_for(projection_engine)
    with Session(projection_engine) as session:
        parents = session.scalars(
            select(job_runs.c.job_id).where(
                job_runs.c.job_type == "knowledge_change",
                job_runs.c.tenant_id.is_(None),
            )
        ).all()
    assert len(parents) >= 2
    for parent in parents:
        assert (
            execute_job(
                projection_engine,
                parent,
                "pg-replay-fixture-" + uuid4().hex,
                {
                    "knowledge_change": runtime.knowledge_change_handler,
                },
            )
            == "partial"
        )
    with Session(projection_engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(job_runs)
                .where(
                    job_runs.c.job_type == "graph_reconcile",
                )
            )
            == 1
        )


def test_next_epoch_includes_old_slot_tombstone_without_reviving_old_generation(
    projection_engine,
    tmp_path,
):
    event_id, _source = published_fixture(projection_engine, tmp_path)
    runtime = runtime_for(projection_engine)
    execute_job(
        projection_engine,
        change_job(projection_engine),
        "pg-first-fixture",
        {
            "knowledge_change": runtime.knowledge_change_handler,
        },
    )
    run_graph_jobs(projection_engine, runtime)
    first = current_manifest(projection_engine)
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    with Session(projection_engine) as session, session.begin():
        session.execute(
            update(events).where(events.c.event_id == str(event_id)).values(status="merged")
        )
        bump_scope_epoch(session, "public", now)
        epochs = read_projection_scope_epochs(session, PUBLIC)
        generation = graph_generation_id(DEFAULT_GRAPH_NAMESPACE, "public", epochs)
        request = GraphReconciliationRequest(generation_id=generation, scope_epochs=epochs)
        enqueue_job(session, None, "graph_reconcile", request.model_dump_json().encode(), now)
    run_graph_jobs(projection_engine, runtime)
    second = current_manifest(projection_engine)
    assert second.generation_id != first.generation_id and second.status == "ready"
    with Session(projection_engine) as session:
        latest_kind = session.scalar(
            select(graph_projection_batches.c.kind).where(
                graph_projection_batches.c.generation_id == str(second.generation_id),
                graph_projection_batches.c.event_id == str(event_id),
            )
        )
        assert latest_kind == "tombstone"
        with pytest.raises(ProjectionNotReady):
            read_reconciliation_manifest(
                session, PUBLIC, DEFAULT_GRAPH_NAMESPACE, first.generation_id
            )


def test_manifest_event_budget_rejects_before_incomplete_manifest_is_published(
    projection_engine,
    tmp_path,
):
    published_fixture(projection_engine, tmp_path / "one")
    published_fixture(projection_engine, tmp_path / "two")
    from datetime import UTC, datetime

    with Session(projection_engine) as session, session.begin():
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        with pytest.raises(ProjectionCapacityError):
            begin_reconciliation(
                session, PUBLIC, "bounded-graph", uuid4(), datetime.now(UTC), max_events=1
            )
