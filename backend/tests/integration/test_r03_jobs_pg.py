"""真实PG任务并发、fence、原子效果、输入重放与outbox恢复。"""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ai_intel.infrastructure.outbox import enqueue_job, relay_pending_events
from ai_intel.knowledge.models import (
    fetch_attempts,
    job_payloads,
    job_runs,
    job_transitions,
    outbox_events,
)
from ai_intel.knowledge.persistence_models import change_events
from ai_intel.workers.executor import (
    JobExecutionError,
    JobExecutionResult,
    execute_job,
    record_source_fetch_failure,
)
from ai_intel.workers.jobs import (
    JobLeaseLostError,
    JobPayloadUnavailableError,
    claim_job,
    claim_next_job,
    complete_job,
    read_job_payload,
    recover_expired_job_deliveries,
    renew_lease,
    schedule_retry_or_fail,
)

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 15, 4, 0, tzinfo=UTC)


def create_job(engine: Engine, *, job_type: str | None = None, max_attempts: int = 5) -> str:
    with Session(engine) as session, session.begin():
        return enqueue_job(
            session, None, job_type or "r03-" + uuid4().hex, b"{}", NOW, max_attempts=max_attempts
        )


def seed_source(session: Session, tenant_id: str | None = None) -> str:
    source_id = str(uuid4())
    session.execute(
        text(
            "INSERT INTO sources(source_id,name,category,base_origin,"
            "visibility,tenant_id,created_at) "
            "VALUES(:id,:name,'vendor_advisory','https://example.invalid',:visibility,:tenant,:at)"
        ),
        {
            "id": source_id,
            "name": "r03-fixture-" + source_id,
            "visibility": "public" if tenant_id is None else "tenant",
            "tenant": tenant_id,
            "at": NOW,
        },
    )
    return source_id


def test_same_scope_key_is_concurrent_but_cross_scope_and_type_are_independent(
    migrated_engine,
) -> None:
    key = "r03-" + uuid4().hex
    start = Barrier(2)

    def concurrent_enqueue() -> str:
        start.wait(timeout=5)
        with Session(migrated_engine) as session, session.begin():
            return enqueue_job(session, "tenant-a", "parse", b"same", NOW, idempotency_key=key)

    with ThreadPoolExecutor(max_workers=2) as pool:
        left = pool.submit(concurrent_enqueue)
        right = pool.submit(concurrent_enqueue)
        assert left.result(timeout=10) == right.result(timeout=10)
    with Session(migrated_engine) as session, session.begin():
        other_tenant = enqueue_job(session, "tenant-b", "parse", b"same", NOW, idempotency_key=key)
        other_type = enqueue_job(session, "tenant-a", "enrich", b"same", NOW, idempotency_key=key)
        assert other_tenant != other_type
        assert (
            session.execute(
                select(func.count()).select_from(job_runs).where(job_runs.c.idempotency_key == key)
            ).scalar_one()
            == 3
        )


def test_rollback_does_not_reserve_idempotency_key_or_payload(migrated_engine) -> None:
    key = "rollback-" + uuid4().hex
    with Session(migrated_engine) as session:
        first = enqueue_job(session, None, "parse", b"old", NOW, idempotency_key=key)
        session.rollback()
    with Session(migrated_engine) as session, session.begin():
        second = enqueue_job(session, None, "parse", b"new", NOW, idempotency_key=key)
        assert read_job_payload(session, second, None) == b"new"
        assert (
            session.execute(
                select(job_payloads.c.job_id).where(job_payloads.c.job_id == first)
            ).scalar_one_or_none()
            is None
        )


def test_two_workers_skip_locked_first_job_and_claim_distinct_rows(migrated_engine) -> None:
    job_type = "r03-competing-" + uuid4().hex
    ids = {create_job(migrated_engine, job_type=job_type) for _ in range(2)}
    first_locked = Event()
    second_done = Event()

    def first_worker() -> str:
        with Session(migrated_engine) as session, session.begin():
            row = claim_next_job(session, "worker-a", NOW, job_type)
            assert row is not None and row["attempt_count"] == 1
            first_locked.set()
            assert second_done.wait(timeout=8)
            return str(row["job_id"])

    def second_worker() -> str:
        assert first_locked.wait(timeout=5)
        try:
            with Session(migrated_engine) as session, session.begin():
                row = claim_next_job(session, "worker-b", NOW, job_type)
                assert row is not None and row["attempt_count"] == 1
                return str(row["job_id"])
        finally:
            second_done.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(first_worker), pool.submit(second_worker)
        assert {a.result(timeout=10), b.result(timeout=10)} == ids


def test_expired_owner_cannot_complete_renew_or_retry_before_reclaim(migrated_engine) -> None:
    job_id = create_job(migrated_engine)
    with Session(migrated_engine) as session, session.begin():
        assert claim_job(session, job_id, "same-owner", NOW)["attempt_count"] == 1
    expired = NOW + timedelta(seconds=60)
    with Session(migrated_engine) as session, session.begin():
        with pytest.raises(JobLeaseLostError):
            complete_job(session, job_id, "same-owner", "succeeded", expired, expected_attempt=1)
        with pytest.raises(JobLeaseLostError):
            renew_lease(session, job_id, "same-owner", expired, expected_attempt=1)
        with pytest.raises(JobLeaseLostError):
            schedule_retry_or_fail(
                session, job_id, "same-owner", False, expired, expected_attempt=1
            )


def test_same_owner_old_attempt_is_fenced_after_reclaim(migrated_engine) -> None:
    job_id = create_job(migrated_engine)
    later = NOW + timedelta(seconds=61)
    with Session(migrated_engine) as session, session.begin():
        claim_job(session, job_id, "same-owner", NOW)
    with Session(migrated_engine) as session, session.begin():
        assert claim_job(session, job_id, "same-owner", later)["attempt_count"] == 2
        with pytest.raises(JobLeaseLostError):
            complete_job(session, job_id, "same-owner", "succeeded", later, expected_attempt=1)
        complete_job(session, job_id, "same-owner", "succeeded", later, expected_attempt=2)
        transitions = session.execute(
            select(job_transitions.c.attempt_count, job_transitions.c.to_status)
            .where(job_transitions.c.job_id == job_id)
            .order_by(job_transitions.c.transition_sequence)
        ).all()
        assert transitions == [(1, "running"), (2, "running"), (2, "succeeded")]


def test_retry_wait_cannot_be_claimed_early_and_retry_event_is_due_once(migrated_engine) -> None:
    job_id = create_job(migrated_engine)
    with Session(migrated_engine) as session, session.begin():
        claim_job(session, job_id, "first", NOW)
        assert (
            schedule_retry_or_fail(
                session, job_id, "first", False, NOW, expected_attempt=1, retry_after_seconds=30
            )
            == "retry_wait"
        )
        assert claim_job(session, job_id, "early", NOW + timedelta(seconds=29)) is None
        assert claim_job(session, job_id, "due", NOW + timedelta(seconds=30))["attempt_count"] == 2


def test_expired_last_attempt_becomes_failed_without_new_owner(migrated_engine) -> None:
    job_id = create_job(migrated_engine, max_attempts=1)
    with Session(migrated_engine) as session, session.begin():
        claim_job(session, job_id, "dead", NOW)
    with Session(migrated_engine) as session, session.begin():
        assert claim_job(session, job_id, "new", NOW + timedelta(seconds=60)) is None
        row = session.execute(select(job_runs).where(job_runs.c.job_id == job_id)).mappings().one()
        assert (row["status"], row["error_code"], row["lease_owner"]) == (
            "failed",
            "attempts_exhausted",
            None,
        )


def test_payload_scope_digest_legacy_and_change_reference_are_checked(migrated_engine) -> None:
    job_id = create_job(migrated_engine)
    with Session(migrated_engine) as session, session.begin():
        assert read_job_payload(session, job_id, None) == b"{}"
        with pytest.raises(JobPayloadUnavailableError, match="scope_denied"):
            read_job_payload(session, job_id, "other")
        session.execute(
            update(job_payloads).where(job_payloads.c.job_id == job_id).values(payload=b"bad")
        )
        with pytest.raises(JobPayloadUnavailableError, match="digest_mismatch"):
            read_job_payload(session, job_id, None)
        session.execute(
            update(job_runs).where(job_runs.c.job_id == job_id).values(payload_ref="f" * 64)
        )
        with pytest.raises(JobPayloadUnavailableError, match="legacy_job_payload_unavailable"):
            read_job_payload(session, job_id, None)
        change_id = str(uuid4())
        encoded = b'{"change":"safe"}'
        session.execute(
            insert(change_events).values(
                change_id=change_id,
                scope_key="public",
                epoch=1,
                change_type="fixture",
                entity_ids=[],
                payload={"change": "safe"},
                created_at=NOW,
            )
        )
        session.execute(
            update(job_runs)
            .where(job_runs.c.job_id == job_id)
            .values(
                payload_ref="pg:change:" + change_id,
                payload_sha256=hashlib.sha256(encoded).hexdigest(),
            )
        )
        assert read_job_payload(session, job_id, None) == encoded
        session.execute(
            update(change_events)
            .where(change_events.c.change_id == change_id)
            .values(scope_key="tenant:" + job_id)
        )
        with pytest.raises(JobPayloadUnavailableError, match="scope_denied"):
            read_job_payload(session, job_id, None)


def test_executor_duplicate_delivery_only_commits_one_real_effect(migrated_engine) -> None:
    with Session(migrated_engine) as session, session.begin():
        source_id = seed_source(session)
        payload = json.dumps(
            {"source_id": source_id, "observed_at": NOW.isoformat(), "http_status": 401}
        ).encode()
        job_id = enqueue_job(session, None, "record_source_fetch_failure", payload, NOW)
    handlers = {"record_source_fetch_failure": record_source_fetch_failure}
    assert execute_job(migrated_engine, job_id, "a", handlers, clock=lambda: NOW) == "succeeded"
    assert execute_job(migrated_engine, job_id, "b", handlers, clock=lambda: NOW) == "not_claimed"
    with Session(migrated_engine) as session:
        rows = (
            session.execute(select(fetch_attempts).where(fetch_attempts.c.source_id == source_id))
            .mappings()
            .all()
        )
        assert len(rows) == 1 and rows[0]["outcome"] == "auth_stopped"
        assert session.execute(
            select(job_runs.c.result_ref).where(job_runs.c.job_id == job_id)
        ).scalar_one() == ("pg:fetch_attempt:" + rows[0]["attempt_id"])


@pytest.mark.parametrize(
    "error",
    [
        JobExecutionError("upstream_unavailable"),
        JobExecutionError("upstream_auth_denied", blocked=True),
    ],
)
def test_handler_effect_rolls_back_before_retry_or_blocked(migrated_engine, error) -> None:
    job_type = "r03-rollback-" + uuid4().hex
    job_id = create_job(migrated_engine, job_type=job_type)
    with Session(migrated_engine) as session, session.begin():
        source_id = seed_source(session)

    def handler(session, context, payload):
        session.execute(
            insert(fetch_attempts).values(
                attempt_id=str(uuid4()),
                source_id=source_id,
                attempted_at=NOW,
                outcome="failed",
                new_event_count=0,
            )
        )
        raise error

    expected = "blocked" if error.blocked else "retry_wait"
    assert (
        execute_job(migrated_engine, job_id, "owner", {job_type: handler}, clock=lambda: NOW)
        == expected
    )
    with Session(migrated_engine) as session:
        assert (
            session.execute(
                select(func.count())
                .select_from(fetch_attempts)
                .where(fetch_attempts.c.source_id == source_id)
            ).scalar_one()
            == 0
        )
        assert (
            session.execute(
                select(job_runs.c.error_code).where(job_runs.c.job_id == job_id)
            ).scalar_one()
            == error.error_code
        )


def test_handler_overrunning_lease_rolls_back_effect(migrated_engine) -> None:
    job_type = "r03-expire-" + uuid4().hex
    job_id = create_job(migrated_engine, job_type=job_type)
    with Session(migrated_engine) as session, session.begin():
        source_id = seed_source(session)
    clock_values = iter([NOW, NOW, NOW + timedelta(seconds=60)])

    def handler(session, context, payload):
        session.execute(
            insert(fetch_attempts).values(
                attempt_id=str(uuid4()),
                source_id=source_id,
                attempted_at=NOW,
                outcome="failed",
                new_event_count=0,
            )
        )
        return JobExecutionResult()

    assert (
        execute_job(
            migrated_engine, job_id, "owner", {job_type: handler}, clock=lambda: next(clock_values)
        )
        == "lease_lost"
    )
    with Session(migrated_engine) as session:
        assert (
            session.execute(
                select(func.count())
                .select_from(fetch_attempts)
                .where(fetch_attempts.c.source_id == source_id)
            ).scalar_one()
            == 0
        )
        assert (
            session.execute(
                select(job_runs.c.status).where(job_runs.c.job_id == job_id)
            ).scalar_one()
            == "running"
        )


def test_unknown_type_and_legacy_payload_are_explicitly_blocked(migrated_engine) -> None:
    job_type = "r03-unknown-" + uuid4().hex
    job_id = create_job(migrated_engine, job_type=job_type)
    assert execute_job(migrated_engine, job_id, "a", {}, clock=lambda: NOW) == "blocked"
    legacy_id = create_job(migrated_engine, job_type=job_type)
    with Session(migrated_engine) as session, session.begin():
        session.execute(
            update(job_runs).where(job_runs.c.job_id == legacy_id).values(payload_ref="f" * 64)
        )
    assert (
        execute_job(
            migrated_engine,
            legacy_id,
            "b",
            {job_type: lambda s, c, p: JobExecutionResult()},
            clock=lambda: NOW,
        )
        == "blocked"
    )
    with Session(migrated_engine) as session:
        assert (
            session.execute(
                select(job_runs.c.error_code).where(job_runs.c.job_id == legacy_id)
            ).scalar_one()
            == "legacy_job_payload_unavailable"
        )


def test_relay_failure_does_not_publish_and_replay_after_commit_gap_is_possible(
    migrated_engine,
) -> None:
    job_id = create_job(migrated_engine)

    def broken(event):
        raise ConnectionError("private broker details must not be saved")

    with Session(migrated_engine) as session, session.begin():
        relay_pending_events(session, NOW, publisher=broken, limit=1000)
        row = (
            session.execute(select(outbox_events).where(outbox_events.c.job_id == job_id))
            .mappings()
            .one()
        )
        assert row["published_at"] is None and row["last_error_code"] == "broker_publish_failed"
        assert row["next_delivery_at"] == NOW + timedelta(seconds=5)
    published = []
    with Session(migrated_engine) as session:
        relay_pending_events(
            session,
            NOW + timedelta(seconds=5),
            publisher=lambda e: published.append(e["job_id"]),
            limit=1000,
        )
        session.rollback()
    with Session(migrated_engine) as session, session.begin():
        relay_pending_events(
            session,
            NOW + timedelta(seconds=5),
            publisher=lambda e: published.append(e["job_id"]),
            limit=1000,
        )
    assert published.count(job_id) == 2


def test_recovery_recreates_only_one_pending_event_for_dead_worker(migrated_engine) -> None:
    job_id = create_job(migrated_engine)
    with Session(migrated_engine) as session, session.begin():
        session.execute(
            update(outbox_events).where(outbox_events.c.job_id == job_id).values(published_at=NOW)
        )
        claim_job(session, job_id, "dead", NOW)
    later = NOW + timedelta(seconds=61)
    with Session(migrated_engine) as session, session.begin():
        recover_expired_job_deliveries(session, later, limit=1000)
        recover_expired_job_deliveries(session, later, limit=1000)
        assert (
            session.execute(
                select(func.count())
                .select_from(outbox_events)
                .where(outbox_events.c.job_id == job_id, outbox_events.c.published_at.is_(None))
            ).scalar_one()
            == 1
        )
