"""Owned PG/Neo4j default-factory cases with an explicitly synthetic hybrid consumer."""

import os
from contextlib import contextmanager
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from test_r10_projection_pg import PUBLIC, published_fixture
from test_r10_projection_pg import projection_engine as projection_engine

from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.knowledge import default_graph_runtime as runtime
from ai_intel.knowledge.graph_projection import (
    ProjectionNotReady,
    read_projection_scope_epochs,
    read_reconciliation_manifest,
)
from ai_intel.knowledge.graph_runtime_policy import DEFAULT_GRAPH_NAMESPACE, graph_generation_id
from ai_intel.knowledge.models import job_runs, outbox_events
from ai_intel.knowledge.persistence_models import events
from ai_intel.knowledge.revisions import bump_scope_epoch
from ai_intel.workers.executor import JobExecutionError, JobExecutionResult, execute_job

pytestmark = [pytest.mark.real_pg, pytest.mark.real_services]


@pytest.fixture
def owned_graph_settings(register_sensitive_failure_value):
    required = (
        "NEO4J_TEST_BOLT_URL",
        "NEO4J_TEST_USERNAME",
        "NEO4J_TEST_PASSWORD",
        "DIANZI_TEST_NEO4J_RESOURCE_ID",
        "DIANZI_TEST_NEO4J_DEADLINE",
    )
    if any(not os.environ.get(name) for name in required):
        raise pytest.UsageError("blocked: explicit owned Neo4j resource environment required")
    uri = os.environ["NEO4J_TEST_BOLT_URL"]
    resource_id = os.environ["DIANZI_TEST_NEO4J_RESOURCE_ID"]
    deadline = datetime.fromisoformat(os.environ["DIANZI_TEST_NEO4J_DEADLINE"])
    if (
        not resource_id.startswith("dianzi-r10_default_graph_")
        or urlsplit(uri).hostname != "127.0.0.1"
        or deadline.tzinfo is None
        or deadline <= datetime.now(UTC)
    ):
        raise pytest.UsageError("blocked: owned Neo4j resource identity or deadline mismatch")
    password = SecretStr(os.environ["NEO4J_TEST_PASSWORD"])
    register_sensitive_failure_value(password)
    return ApplicationSettings(
        app_env="test",
        data_mode="fixture",
        neo4j_uri=uri,
        neo4j_username=os.environ["NEO4J_TEST_USERNAME"],
        neo4j_password=password,
        opensearch_url=None,
        semantic_model_cache_directory=None,
    )


@pytest.fixture
def synthetic_hybrid(monkeypatch):
    state = {"fail": False, "calls": 0}

    def hybrid(session, context, payload):
        state["calls"] += 1
        if state["fail"]:
            raise JobExecutionError("corpus_projection_not_configured", blocked=True)
        return JobExecutionResult("partial", "pg:hybrid_receipt:fixture", "other_consumers_pending")

    @contextmanager
    def handlers(engine, settings):
        yield {"knowledge_change": hybrid}

    monkeypatch.setattr(runtime, "build_projection_job_handlers", handlers)
    return state


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


def drain_graph_jobs(engine, handlers):
    outcomes = []
    for _ in range(30):
        with Session(engine) as session:
            job = session.execute(
                select(job_runs.c.job_id, job_runs.c.job_type)
                .where(
                    job_runs.c.job_type.in_(("graph_reconcile", "graph_capture", "graph_apply")),
                    job_runs.c.status == "queued",
                )
                .order_by(job_runs.c.created_at, job_runs.c.job_id)
                .limit(1)
            ).first()
        if job is None:
            return outcomes
        outcomes.append(
            (job.job_type, execute_job(engine, job.job_id, "fixture-" + uuid4().hex, handlers))
        )
    raise AssertionError("owned graph fixture job budget exhausted")


def current_manifest(engine):
    with Session(engine) as session:
        epochs = read_projection_scope_epochs(session, PUBLIC)
        generation = graph_generation_id(DEFAULT_GRAPH_NAMESPACE, "public", epochs)
        return read_reconciliation_manifest(session, PUBLIC, DEFAULT_GRAPH_NAMESPACE, generation)


def test_default_factory_publication_reaches_real_manifest_ready_while_parent_remains_partial(
    projection_engine, owned_graph_settings, synthetic_hybrid, tmp_path
):
    published_fixture(projection_engine, tmp_path)
    with runtime.build_default_graph_job_handlers(
        projection_engine, owned_graph_settings
    ) as handlers:
        assert (
            execute_job(
                projection_engine, change_job(projection_engine), "fixture-worker", handlers
            )
            == "partial"
        )
        outcomes = drain_graph_jobs(projection_engine, handlers)
    assert outcomes == [
        ("graph_reconcile", "partial"),
        ("graph_capture", "partial"),
        ("graph_apply", "succeeded"),
    ]
    manifest = current_manifest(projection_engine)
    assert manifest.status == "ready" and manifest.acknowledged_count == manifest.event_count == 1
    assert synthetic_hybrid["calls"] == 1


def test_real_graph_dispatch_survives_hybrid_unavailability_and_replay_does_not_grow_queue(
    projection_engine, owned_graph_settings, synthetic_hybrid, tmp_path
):
    published_fixture(projection_engine, tmp_path)
    parent_job = change_job(projection_engine)
    synthetic_hybrid["fail"] = True
    with runtime.build_default_graph_job_handlers(
        projection_engine, owned_graph_settings
    ) as handlers:
        for _ in range(2):
            assert (
                execute_job(projection_engine, parent_job, "fixture-worker", handlers) == "blocked"
            )
            with Session(projection_engine) as session, session.begin():
                assert (
                    session.scalar(
                        select(func.count())
                        .select_from(job_runs)
                        .where(job_runs.c.job_type == "graph_reconcile")
                    )
                    == 1
                )
                assert (
                    session.scalar(
                        select(func.count())
                        .select_from(outbox_events)
                        .where(outbox_events.c.topic == "job.graph_reconcile")
                    )
                    == 1
                )
                session.execute(
                    update(job_runs).where(job_runs.c.job_id == parent_job).values(status="queued")
                )
        assert drain_graph_jobs(projection_engine, handlers)[-1] == ("graph_apply", "succeeded")
    assert current_manifest(projection_engine).status == "ready"


def test_real_epoch_change_invalidates_previous_manifest_and_captures_withdrawn_history(
    projection_engine, owned_graph_settings, synthetic_hybrid, tmp_path
):
    event_id, _ = published_fixture(projection_engine, tmp_path)
    with runtime.build_default_graph_job_handlers(
        projection_engine, owned_graph_settings
    ) as handlers:
        execute_job(projection_engine, change_job(projection_engine), "fixture-worker", handlers)
        drain_graph_jobs(projection_engine, handlers)
        old = current_manifest(projection_engine)
        with Session(projection_engine) as session, session.begin():
            session.execute(
                update(events).where(events.c.event_id == str(event_id)).values(status="withdrawn")
            )
            bump_scope_epoch(session, "public", datetime.now(UTC))
        with Session(projection_engine) as session, pytest.raises(ProjectionNotReady):
            read_reconciliation_manifest(
                session, PUBLIC, DEFAULT_GRAPH_NAMESPACE, old.generation_id
            )
        published_fixture(projection_engine, tmp_path)
        execute_job(projection_engine, change_job(projection_engine), "fixture-worker", handlers)
        drain_graph_jobs(projection_engine, handlers)
    new = current_manifest(projection_engine)
    assert new.generation_id != old.generation_id
    assert new.status == "ready" and new.event_count == 2
