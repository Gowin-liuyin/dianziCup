"""Real isolated PG covers terminal starvation, authority and cancellation row locking."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from time import monotonic, sleep

import pytest
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_r14_langgraph_workflow_pg import workflow_resources as workflow_resources

from ai_intel.infrastructure.outbox import enqueue_job, relay_pending_events
from ai_intel.knowledge.models import job_runs, outbox_events
from ai_intel.workers.jobs import recover_expired_job_deliveries

pytestmark = pytest.mark.real_pg


def enqueue(engine, at, status="queued", count=1):
    with Session(engine) as session, session.begin():
        jobs = [
            enqueue_job(session, None, "synthetic-terminal-relay", b"{}", at) for _ in range(count)
        ]
        session.execute(update(job_runs).where(job_runs.c.job_id.in_(jobs)).values(status=status))
    return jobs


def relay(engine, at, limit=100):
    sent = []
    with Session(engine) as session, session.begin():
        released = relay_pending_events(session, at, publisher=sent.append, limit=limit)
    assert sent == released
    return sent


@pytest.mark.parametrize(
    "status", ["succeeded", "partial", "failed", "cancelled", "blocked", "waiting_approval"]
)
def test_terminal_more_than_cleanup_limit_never_publishes(workflow_resources, status):
    engine, _, _ = workflow_resources
    at = datetime.now(UTC)
    enqueue(engine, at - timedelta(minutes=5), status, count=105)
    with Session(engine) as session, session.begin():
        assert recover_expired_job_deliveries(session, at, limit=100) == 0
    assert relay(engine, at) == []
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(outbox_events)) == 105
        assert (
            connection.scalar(
                select(func.count())
                .select_from(outbox_events)
                .where(outbox_events.c.published_at.is_not(None))
            )
            == 0
        )
        assert connection.scalar(select(func.sum(outbox_events.c.delivery_attempts))) == 0


def test_terminal_backlog_does_not_starve_later_ready_jobs_even_without_cleanup(workflow_resources):
    engine, _, _ = workflow_resources
    at = datetime.now(UTC)
    enqueue(engine, at - timedelta(minutes=5), "cancelled", count=205)
    ready = enqueue(engine, at)[0]
    sent = relay(engine, at, limit=1)
    assert [item["job_id"] for item in sent] == [ready]
    with engine.connect() as connection:
        assert (
            connection.scalar(
                select(func.count())
                .select_from(outbox_events)
                .where(outbox_events.c.published_at.is_not(None))
            )
            == 1
        )


@pytest.mark.parametrize("status", ["queued", "retry_wait", "running"])
def test_active_authoritative_states_keep_original_due_delivery_semantics(
    workflow_resources, status
):
    engine, _, _ = workflow_resources
    at = datetime.now(UTC)
    ready = enqueue(engine, at, status)[0]
    assert [item["job_id"] for item in relay(engine, at)] == [ready]
    assert relay(engine, at) == []


def test_payload_reference_mismatch_cannot_publish_or_starve_valid_event(workflow_resources):
    engine, _, _ = workflow_resources
    at = datetime.now(UTC)
    malformed = enqueue(engine, at - timedelta(minutes=5))[0]
    valid = enqueue(engine, at)[0]
    with engine.begin() as connection:
        connection.execute(
            update(outbox_events)
            .where(outbox_events.c.job_id == malformed)
            .values(payload_ref="pg:job:other-owner")
        )
    assert [item["job_id"] for item in relay(engine, at, limit=1)] == [valid]
    with engine.connect() as connection:
        assert (
            connection.scalar(
                select(outbox_events.c.published_at).where(outbox_events.c.job_id == malformed)
            )
            is None
        )
        assert (
            connection.scalar(
                select(outbox_events.c.delivery_attempts).where(outbox_events.c.job_id == malformed)
            )
            == 0
        )


def test_missing_authoritative_job_is_rejected_by_real_fk(workflow_resources):
    engine, _, _ = workflow_resources
    at = datetime.now(UTC)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            insert(outbox_events).values(
                event_id="synthetic-orphan",
                job_id="synthetic-no-authority",
                topic="job.synthetic",
                payload_ref="pg:job:synthetic-no-authority",
                created_at=at,
            )
        )
    assert relay(engine, at) == []


def test_original_future_delivery_backoff_is_still_obeyed(workflow_resources):
    engine, _, _ = workflow_resources
    at = datetime.now(UTC)
    job = enqueue(engine, at, "retry_wait")[0]
    with engine.begin() as connection:
        connection.execute(
            update(outbox_events)
            .where(outbox_events.c.job_id == job)
            .values(next_delivery_at=at + timedelta(seconds=5))
        )
    assert relay(engine, at) == []
    assert [item["job_id"] for item in relay(engine, at + timedelta(seconds=5))] == [job]


def test_job_lock_skips_cancellation_race_but_keeps_later_job_available(workflow_resources):
    engine, _, _ = workflow_resources
    at = datetime.now(UTC)
    cancelled = enqueue(engine, at - timedelta(minutes=5))[0]
    valid = enqueue(engine, at)[0]
    with Session(engine) as cancel_session, cancel_session.begin():
        cancel_session.execute(
            select(job_runs).where(job_runs.c.job_id == cancelled).with_for_update()
        )
        cancel_session.execute(
            update(job_runs).where(job_runs.c.job_id == cancelled).values(status="cancelled")
        )
        assert [item["job_id"] for item in relay(engine, at, limit=1)] == [valid]
    assert relay(engine, at) == []


def test_relay_job_row_lock_serializes_cancellation_until_publication_commit(workflow_resources):
    engine, _, _ = workflow_resources
    at = datetime.now(UTC)
    job = enqueue(engine, at)[0]
    cancellation_started = Event()
    cancellation_committed = Event()
    cancellation_pid = []

    def cancel():
        with engine.begin() as connection:
            cancellation_pid.append(connection.scalar(select(func.pg_backend_pid())))
            cancellation_started.set()
            connection.execute(
                update(job_runs).where(job_runs.c.job_id == job).values(status="cancelled")
            )
        cancellation_committed.set()

    with ThreadPoolExecutor(max_workers=1) as executor:
        with Session(engine) as session, session.begin():
            future = None

            def publisher(event):
                nonlocal future
                assert event["job_id"] == job
                future = executor.submit(cancel)
                assert cancellation_started.wait(timeout=5)
                deadline = monotonic() + 2
                wait_event = None
                while monotonic() < deadline:
                    wait_event = session.scalar(
                        text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"),
                        {"pid": cancellation_pid[0]},
                    )
                    if wait_event == "Lock":
                        break
                    sleep(0.01)
                assert wait_event == "Lock"
                assert not cancellation_committed.is_set()

            assert len(relay_pending_events(session, at, publisher=publisher)) == 1
        future.result(timeout=10)
    assert cancellation_committed.is_set()
    assert relay(engine, at + timedelta(seconds=1)) == []
    with engine.connect() as connection:
        assert (
            connection.scalar(select(job_runs.c.status).where(job_runs.c.job_id == job))
            == "cancelled"
        )
        assert (
            connection.scalar(
                select(outbox_events.c.published_at).where(outbox_events.c.job_id == job)
            )
            == at
        )
