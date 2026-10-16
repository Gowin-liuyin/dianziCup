"""Isolated PG fences and real source effects; synthetic IO never counts as live."""

import asyncio
import json
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema
from test_r03_jobs_pg import NOW, seed_source

from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.knowledge.models import fetch_attempts, job_runs, outbox_events
from ai_intel.workers.executor import (
    DetachedJobHandler,
    JobExecutionContext,
    JobExecutionError,
    JobExecutionResult,
    execute_job,
    record_source_fetch_failure,
)
from ai_intel.workers.jobs import require_job_lease

pytestmark = pytest.mark.real_pg
JOB_TYPE = "fixture_detached_source_effect"


@pytest.fixture()
def detached_engine(
    isolated_test_database_url: str,
    register_sensitive_failure_value: Callable[[SecretStr], None],
) -> Iterator[Engine]:
    register_sensitive_failure_value(SecretStr(isolated_test_database_url))
    url = make_url(isolated_test_database_url)
    if url.password:
        register_sensitive_failure_value(SecretStr(url.password))
    assert url.database == "test_dianzi_detached_worker_20261016"
    schema = "test_detached_worker_" + uuid4().hex
    base = create_engine(
        url, poolclass=NullPool, hide_parameters=True, connect_args={"connect_timeout": 5}
    )
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=1000"}
    )
    engine = create_engine(
        isolated, poolclass=NullPool, hide_parameters=True, connect_args={"connect_timeout": 5}
    )
    try:
        run_migrations(isolated.render_as_string(hide_password=False))
        yield engine
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


def source_job(engine: Engine) -> tuple[str, str, bytes]:
    with Session(engine) as session, session.begin():
        source_id = seed_source(session)
        payload = json.dumps(
            {"source_id": source_id, "observed_at": NOW.isoformat(), "http_status": 401}
        ).encode()
        job_id = enqueue_job(session, None, JOB_TYPE, payload, NOW)
    return job_id, source_id, payload


def effect_count(engine: Engine, source_id: str) -> int:
    with Session(engine) as session:
        return session.execute(
            select(func.count())
            .select_from(fetch_attempts)
            .where(fetch_attempts.c.source_id == source_id)
        ).scalar_one()


def job_row(engine: Engine, job_id: str):
    with Session(engine) as session:
        return session.execute(select(job_runs).where(job_runs.c.job_id == job_id)).mappings().one()


def commit_source_effect(
    engine: Engine, context: JobExecutionContext, payload: bytes, *, at=NOW
) -> JobExecutionResult:
    """Fixture service owns its short fence/PG-idempotence transaction."""
    attempt_id = str(uuid5(NAMESPACE_URL, "ai-intel:fetch-failure:" + context.job_id))
    with Session(engine) as session, session.begin():
        require_job_lease(
            session, context.job_id, context.worker_id, at, expected_attempt=context.attempt_count
        )
        existing = session.execute(
            select(fetch_attempts.c.attempt_id).where(fetch_attempts.c.attempt_id == attempt_id)
        ).scalar_one_or_none()
        if existing is not None:
            return JobExecutionResult(result_ref="pg:fetch_attempt:" + existing)
        return record_source_fetch_failure(session, context, payload)


def test_job_lock_is_released_during_io_and_real_service_owns_short_effect_txn(detached_engine):
    job_id, source_id, expected_payload = source_job(detached_engine)
    entered_io, release_io = Event(), Event()

    def handler(context, payload):
        assert (
            payload == expected_payload and context.tenant_id is None and context.attempt_count == 1
        )
        entered_io.set()
        assert release_io.wait(timeout=5)
        return commit_source_effect(detached_engine, context, payload)

    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(
            execute_job,
            detached_engine,
            job_id,
            "worker",
            {JOB_TYPE: DetachedJobHandler(handler)},
            clock=lambda: NOW,
        )
        try:
            assert entered_io.wait(timeout=5)
            with Session(detached_engine) as session, session.begin():
                row = (
                    session.execute(
                        select(job_runs)
                        .where(job_runs.c.job_id == job_id)
                        .with_for_update(nowait=True)
                    )
                    .mappings()
                    .one()
                )
                assert row["status"] == "running" and row["attempt_count"] == 1
            assert effect_count(detached_engine, source_id) == 0
        finally:
            release_io.set()
        assert running.result(timeout=10) == "succeeded"
    assert effect_count(detached_engine, source_id) == 1
    assert job_row(detached_engine, job_id)["result_ref"].startswith("pg:fetch_attempt:")


def test_lease_lost_before_payload_read_never_calls_service(detached_engine):
    job_id, source_id, _payload = source_job(detached_engine)
    times = iter([NOW, NOW + timedelta(seconds=60)])
    handler = DetachedJobHandler(lambda *arguments: pytest.fail("expired payload dispatched"))
    assert (
        execute_job(
            detached_engine, job_id, "worker", {JOB_TYPE: handler}, clock=lambda: next(times)
        )
        == "lease_lost"
    )
    assert effect_count(detached_engine, source_id) == 0
    assert job_row(detached_engine, job_id)["status"] == "running"


def test_service_refences_after_valid_payload_before_committing_effect(detached_engine):
    job_id, source_id, _payload = source_job(detached_engine)
    expired = NOW + timedelta(seconds=60)
    handler = DetachedJobHandler(
        lambda context, payload: commit_source_effect(detached_engine, context, payload, at=expired)
    )
    assert (
        execute_job(detached_engine, job_id, "worker", {JOB_TYPE: handler}, clock=lambda: NOW)
        == "lease_lost"
    )
    assert effect_count(detached_engine, source_id) == 0
    assert job_row(detached_engine, job_id)["status"] == "running"


def test_committed_effect_survives_lost_completion_and_service_pg_replay_is_idempotent(
    detached_engine,
):
    job_id, source_id, _payload = source_job(detached_engine)
    times = iter([NOW, NOW, NOW + timedelta(seconds=60)])
    first = DetachedJobHandler(
        lambda context, payload: commit_source_effect(detached_engine, context, payload)
    )
    assert (
        execute_job(detached_engine, job_id, "worker", {JOB_TYPE: first}, clock=lambda: next(times))
        == "lease_lost"
    )
    assert effect_count(detached_engine, source_id) == 1
    assert job_row(detached_engine, job_id)["status"] == "running"
    later = NOW + timedelta(seconds=61)
    replay = DetachedJobHandler(
        lambda context, payload: commit_source_effect(detached_engine, context, payload, at=later)
    )
    assert (
        execute_job(detached_engine, job_id, "recovered", {JOB_TYPE: replay}, clock=lambda: later)
        == "succeeded"
    )
    assert effect_count(detached_engine, source_id) == 1
    assert job_row(detached_engine, job_id)["attempt_count"] == 2


@pytest.mark.parametrize("error", [KeyboardInterrupt(), SystemExit(), asyncio.CancelledError()])
def test_cancel_after_service_commit_propagates_and_does_not_complete_or_retry(
    detached_engine, error
):
    job_id, source_id, _payload = source_job(detached_engine)

    def handler(context, payload):
        commit_source_effect(detached_engine, context, payload)
        raise error

    with pytest.raises(type(error)) as captured:
        execute_job(
            detached_engine,
            job_id,
            "worker",
            {JOB_TYPE: DetachedJobHandler(handler)},
            clock=lambda: NOW,
        )
    assert captured.value is error
    assert effect_count(detached_engine, source_id) == 1
    row = job_row(detached_engine, job_id)
    assert row["status"] == "running" and row["error_code"] is None
    with Session(detached_engine) as session:
        assert (
            session.execute(
                select(func.count())
                .select_from(outbox_events)
                .where(outbox_events.c.job_id == job_id)
            ).scalar_one()
            == 1
        )


def test_service_unknown_result_classification_is_preserved_without_worker_loop(detached_engine):
    job_id, source_id, _payload = source_job(detached_engine)

    def handler(context, payload):
        commit_source_effect(detached_engine, context, payload)
        raise JobExecutionError("model_outcome_unknown", blocked=True)

    assert (
        execute_job(
            detached_engine,
            job_id,
            "worker",
            {JOB_TYPE: DetachedJobHandler(handler)},
            clock=lambda: NOW,
        )
        == "blocked"
    )
    assert effect_count(detached_engine, source_id) == 1
    row = job_row(detached_engine, job_id)
    assert row["error_code"] == "model_outcome_unknown" and row["next_retry_at"] is None
    assert (
        execute_job(
            detached_engine,
            job_id,
            "duplicate",
            {JOB_TYPE: DetachedJobHandler(handler)},
            clock=lambda: NOW,
        )
        == "not_claimed"
    )


def test_concurrent_duplicate_and_completed_replay_do_not_execute_twice(detached_engine):
    job_id, source_id, _payload = source_job(detached_engine)
    entered, release = Event(), Event()
    calls = []

    def handler(context, payload):
        calls.append(context.attempt_count)
        entered.set()
        assert release.wait(timeout=5)
        return commit_source_effect(detached_engine, context, payload)

    handlers = {JOB_TYPE: DetachedJobHandler(handler)}
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(
            execute_job, detached_engine, job_id, "first", handlers, clock=lambda: NOW
        )
        try:
            assert entered.wait(timeout=5)
            assert (
                execute_job(detached_engine, job_id, "concurrent", handlers, clock=lambda: NOW)
                == "not_claimed"
            )
        finally:
            release.set()
        assert first.result(timeout=10) == "succeeded"
    assert (
        execute_job(detached_engine, job_id, "replay", handlers, clock=lambda: NOW) == "not_claimed"
    )
    assert calls == [1] and effect_count(detached_engine, source_id) == 1


def test_legacy_effect_is_invisible_until_atomic_completion_and_duplicate_skips_lock(
    detached_engine,
):
    job_id, source_id, _payload = source_job(detached_engine)
    written, release = Event(), Event()

    def handler(session, context, payload):
        result = record_source_fetch_failure(session, context, payload)
        written.set()
        assert release.wait(timeout=5)
        return result

    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(
            execute_job, detached_engine, job_id, "first", {JOB_TYPE: handler}, clock=lambda: NOW
        )
        try:
            assert written.wait(timeout=5)
            assert effect_count(detached_engine, source_id) == 0
            assert job_row(detached_engine, job_id)["status"] == "running"
            assert (
                execute_job(
                    detached_engine, job_id, "second", {JOB_TYPE: handler}, clock=lambda: NOW
                )
                == "not_claimed"
            )
        finally:
            release.set()
        assert first.result(timeout=10) == "succeeded"
    assert effect_count(detached_engine, source_id) == 1
    assert job_row(detached_engine, job_id)["status"] == "succeeded"


@pytest.mark.parametrize("expired", [False, True])
def test_legacy_effect_rolls_back_on_failure_or_expired_completion(detached_engine, expired):
    job_id, source_id, _payload = source_job(detached_engine)
    times = iter([NOW, NOW, NOW + timedelta(seconds=60) if expired else NOW])

    def handler(session, context, payload):
        result = record_source_fetch_failure(session, context, payload)
        if not expired:
            raise JobExecutionError("fixture_service_failure")
        return result

    assert execute_job(
        detached_engine, job_id, "first", {JOB_TYPE: handler}, clock=lambda: next(times)
    ) == ("lease_lost" if expired else "retry_wait")
    assert effect_count(detached_engine, source_id) == 0
    assert job_row(detached_engine, job_id)["status"] == ("running" if expired else "retry_wait")
