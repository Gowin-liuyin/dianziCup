"""PG delivery recovery boundaries use marked schemas and explicit clock injection."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session
from test_r14_langgraph_workflow_pg import workflow_resources as workflow_resources

from ai_intel.infrastructure.outbox import enqueue_job, relay_pending_events
from ai_intel.knowledge.models import job_runs, job_transitions, outbox_events
from ai_intel.workers.jobs import (
    DELIVERY_STOPPED_AT,
    claim_job,
    complete_job,
    recover_expired_job_deliveries,
)

pytestmark = pytest.mark.real_pg


def enqueue(engine, at, *, max_attempts=5):
    with Session(engine) as session, session.begin():
        return enqueue_job(
            session,
            None,
            "synthetic-preclaim",
            b"{}",
            at,
            idempotency_key="synthetic-" + uuid4().hex,
            max_attempts=max_attempts,
        )


def published(engine, job, at, *, attempts=1):
    with engine.begin() as connection:
        connection.execute(
            update(outbox_events)
            .where(outbox_events.c.job_id == job)
            .values(published_at=at, delivery_attempts=attempts)
        )


def recover(engine, at):
    with Session(engine) as session, session.begin():
        return recover_expired_job_deliveries(session, at)


@pytest.mark.parametrize("elapsed,expected", [(59.999, 0), (60, 1), (61, 1)])
def test_queued_published_recovery_uses_original_exact_grace(workflow_resources, elapsed, expected):
    engine, _, _ = workflow_resources
    at = datetime.now(UTC)
    job = enqueue(engine, at)
    published(engine, job, at)
    assert recover(engine, at + timedelta(seconds=elapsed)) == expected
    assert recover(engine, at + timedelta(seconds=elapsed)) == 0
    with engine.connect() as connection:
        assert connection.execute(
            select(job_runs.c.status, job_runs.c.attempt_count, job_runs.c.lease_expires_at).where(
                job_runs.c.job_id == job
            )
        ).one() == ("queued", 0, None)
        assert connection.scalar(select(func.count()).select_from(job_runs)) == 1
        assert (
            connection.scalar(
                select(func.count())
                .select_from(outbox_events)
                .where(outbox_events.c.job_id == job, outbox_events.c.published_at.is_(None))
            )
            == expected
        )


@pytest.mark.parametrize("outbox_kind,expected", [("missing", 1), ("pending", 0), ("backoff", 0)])
def test_missing_outbox_is_rebuilt_but_effective_pending_is_never_duplicated(
    workflow_resources, outbox_kind, expected
):
    engine, _, _ = workflow_resources
    at = datetime.now(UTC)
    job = enqueue(engine, at)
    with engine.begin() as connection:
        if outbox_kind == "missing":
            connection.execute(delete(outbox_events).where(outbox_events.c.job_id == job))
        elif outbox_kind == "backoff":
            connection.execute(
                update(outbox_events)
                .where(outbox_events.c.job_id == job)
                .values(next_delivery_at=at + timedelta(hours=1), delivery_attempts=1)
            )
    assert recover(engine, at + timedelta(seconds=61)) == expected
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(outbox_events)) == 1
        assert connection.scalar(select(outbox_events.c.published_at)) is None


@pytest.mark.parametrize(
    "status", ["succeeded", "partial", "failed", "cancelled", "blocked", "waiting_approval"]
)
def test_terminal_pending_is_stopped_without_forging_publication(workflow_resources, status):
    engine, _, _ = workflow_resources
    at = datetime.now(UTC)
    job = enqueue(engine, at)
    with engine.begin() as connection:
        connection.execute(update(job_runs).where(job_runs.c.job_id == job).values(status=status))
    assert recover(engine, at + timedelta(seconds=61)) == 0
    sent = []
    with Session(engine) as session, session.begin():
        assert relay_pending_events(session, at + timedelta(hours=1), publisher=sent.append) == []
    assert sent == []
    with engine.connect() as connection:
        assert connection.execute(
            select(
                outbox_events.c.published_at,
                outbox_events.c.next_delivery_at,
                outbox_events.c.last_error_code,
            )
        ).one() == (None, DELIVERY_STOPPED_AT, "job_delivery_stopped")


@pytest.mark.parametrize("max_attempts", [1, 3, 5])
def test_total_delivery_cap_sums_all_receipts_without_resetting_business_attempts(
    workflow_resources, max_attempts
):
    engine, _, _ = workflow_resources
    at = datetime.now(UTC)
    job = enqueue(engine, at, max_attempts=max_attempts)
    published(engine, job, at, attempts=max_attempts * 3 - 1)
    assert recover(engine, at + timedelta(seconds=61)) == 1
    with Session(engine) as session, session.begin():
        sent = []
        assert (
            len(relay_pending_events(session, at + timedelta(seconds=61), publisher=sent.append))
            == 1
        )
    assert recover(engine, at + timedelta(seconds=122)) == 0
    with engine.connect() as connection:
        assert connection.execute(
            select(
                job_runs.c.status,
                job_runs.c.attempt_count,
                job_runs.c.max_attempts,
                job_runs.c.error_code,
            ).where(job_runs.c.job_id == job)
        ).one() == ("failed", 0, max_attempts, "delivery_attempts_exhausted")
        assert (
            connection.scalar(select(func.sum(outbox_events.c.delivery_attempts)))
            == max_attempts * 3
        )
        assert connection.scalar(select(job_transitions.c.reason)) == "delivery_attempts_exhausted"
        assert connection.scalar(select(func.count()).select_from(job_runs)) == 1


def test_pending_broker_failure_at_cap_stops_without_more_wire(workflow_resources):
    engine, _, _ = workflow_resources
    at = datetime.now(UTC)
    job = enqueue(engine, at, max_attempts=1)
    with engine.begin() as connection:
        connection.execute(
            update(outbox_events)
            .where(outbox_events.c.job_id == job)
            .values(delivery_attempts=3, last_error_code="broker_publish_failed")
        )
    assert recover(engine, at + timedelta(seconds=1)) == 0
    sent = []
    with Session(engine) as session, session.begin():
        assert relay_pending_events(session, at + timedelta(hours=1), publisher=sent.append) == []
    with engine.connect() as connection:
        assert connection.execute(
            select(
                outbox_events.c.published_at,
                outbox_events.c.delivery_attempts,
                outbox_events.c.last_error_code,
            )
        ).one() == (None, 3, "delivery_attempts_exhausted")


@pytest.mark.parametrize("retry_due,expected", [(False, 0), (True, 1)])
def test_retry_wait_recovery_obeys_persisted_retry_time(workflow_resources, retry_due, expected):
    engine, _, _ = workflow_resources
    at = datetime.now(UTC)
    job = enqueue(engine, at)
    published(engine, job, at)
    with engine.begin() as connection:
        connection.execute(
            update(job_runs)
            .where(job_runs.c.job_id == job)
            .values(
                status="retry_wait", next_retry_at=at + timedelta(seconds=60 if retry_due else 120)
            )
        )
    assert recover(engine, at + timedelta(seconds=61)) == expected


def test_active_lease_then_expired_lease_are_not_conflated(workflow_resources):
    engine, _, _ = workflow_resources
    at = datetime.now(UTC)
    job = enqueue(engine, at)
    published(engine, job, at)
    with Session(engine) as session, session.begin():
        assert claim_job(session, job, "synthetic-lease", at) is not None
    assert recover(engine, at + timedelta(seconds=59)) == 0
    assert recover(engine, at + timedelta(seconds=60)) == 1
    with Session(engine) as session, session.begin():
        claimed = claim_job(session, job, "synthetic-new", at + timedelta(seconds=61))
        assert claimed["attempt_count"] == 2
        complete_job(
            session, job, "synthetic-new", "partial", at + timedelta(seconds=62), expected_attempt=2
        )
    assert recover(engine, at + timedelta(seconds=122)) == 0


def test_concurrent_scans_create_one_pending_message(workflow_resources):
    engine, _, _ = workflow_resources
    at = datetime.now(UTC)
    job = enqueue(engine, at)
    published(engine, job, at)
    barrier = Barrier(2)

    def scan():
        barrier.wait(timeout=10)
        return recover(engine, at + timedelta(seconds=61))

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(scan) for _ in range(2)]
        assert sum(future.result(timeout=15) for future in futures) == 1
    with engine.connect() as connection:
        assert (
            connection.scalar(
                select(func.count())
                .select_from(outbox_events)
                .where(outbox_events.c.published_at.is_(None))
            )
            == 1
        )


def test_recovery_publication_failure_and_rollback_preserve_original_history(workflow_resources):
    engine, _, _ = workflow_resources
    at = datetime.now(UTC)
    job = enqueue(engine, at)
    published(engine, job, at)
    with (
        Session(engine) as session,
        pytest.raises(RuntimeError, match="synthetic rollback"),
        session.begin(),
    ):
        assert recover_expired_job_deliveries(session, at + timedelta(seconds=61)) == 1
        raise RuntimeError("synthetic rollback")
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(outbox_events)) == 1

    def broken(event):
        raise ConnectionError("synthetic broker unavailable")

    with Session(engine) as session, session.begin():
        assert recover_expired_job_deliveries(session, at + timedelta(seconds=61)) == 1
        assert relay_pending_events(session, at + timedelta(seconds=61), publisher=broken) == []
    assert recover(engine, at + timedelta(seconds=122)) == 0
    with engine.connect() as connection:
        assert connection.scalar(select(func.sum(outbox_events.c.delivery_attempts))) == 2
        assert connection.scalar(select(func.count()).select_from(outbox_events)) == 2
