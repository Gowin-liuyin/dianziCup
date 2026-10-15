"""0012游标回执完整输入、终态拒绝和有界窗口恢复引用真实PG回归。"""

import json
from datetime import timedelta
from uuid import uuid4

import pytest
import test_r03_cursor_persistence as cursor_tests
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from test_r03_cursor_persistence import (
    ADMIN,
    NOW,
    Clock,
    claim,
    commit,
    row,
    seed_source,
)

from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.ingestion.cursor_repository import (
    PersistedPageEntry,
    SourceCursorRepository,
    SourceLeaseLostError,
)
from ai_intel.ingestion.scheduler import CursorCommitError
from ai_intel.knowledge.models import (
    job_payloads,
    job_runs,
    outbox_events,
    source_cursors,
    source_page_receipts,
)
from ai_intel.workers.executor import JobExecutionError, execute_job
from ai_intel.workers.jobs import claim_job, schedule_retry_or_fail

pytestmark = pytest.mark.real_pg
cursor_engine = cursor_tests.cursor_engine


def create_recovery_job(session, source_id, entry_id, *, max_attempts=5):
    return enqueue_job(
        session,
        None,
        "fixture-source-recovery",
        json.dumps({"source_id": source_id, "entry_id": entry_id}).encode(),
        NOW,
        max_attempts=max_attempts,
    )


def persist_recovery(source_id, callbacks):
    def persist(session, entry):
        callbacks.append(entry["entry_id"])
        return PersistedPageEntry(
            failed_job_id=create_recovery_job(session, source_id, entry["entry_id"])
        )

    return persist


@pytest.mark.parametrize(
    "change", ["entry_id", "unknown_field", "entry_order", "watermark", "completion", "output"]
)
def test_changed_replay_conflicts_without_callback_or_state_change(cursor_engine, change):
    source_id, callbacks = seed_source(cursor_engine), []
    entries = ({"entry_id": "a", "unknown": {"field": 1}}, {"entry_id": "b"})
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=Clock())
        lease = claim(repository)
        commit(
            repository,
            lease,
            entries,
            output_cursor={},
            persist_entry=persist_recovery(source_id, callbacks),
            watermark=NOW - timedelta(days=1),
        )
    before = row(cursor_engine, source_id)
    replay_entries, output, watermark, final = entries, {}, NOW - timedelta(days=1), False
    if change == "entry_id":
        replay_entries = ({"entry_id": "replacement", "unknown": {"field": 1}}, {"entry_id": "b"})
    elif change == "unknown_field":
        replay_entries = ({"entry_id": "a", "unknown": {"field": 2}}, {"entry_id": "b"})
    elif change == "entry_order":
        replay_entries = entries[::-1]
    elif change == "watermark":
        watermark = NOW
    elif change == "completion":
        final = True
    else:
        output = {"different": 1}
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=Clock())
        with pytest.raises(CursorCommitError, match="conflicts with replay"):
            commit(
                repository,
                lease,
                replay_entries,
                output_cursor=output,
                persist_entry=persist_recovery(source_id, callbacks),
                watermark=watermark,
                is_last_page=final,
            )
    assert callbacks == ["a", "b"] and row(cursor_engine, source_id) == before


def test_equivalent_key_order_and_utc_replay_is_callback_free_across_sessions(cursor_engine):
    from datetime import timezone

    source_id, callbacks = seed_source(cursor_engine), []
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=Clock())
        lease = claim(repository)
        original = commit(
            repository,
            lease,
            ({"entry_id": "entry", "b": 2, "a": 1},),
            persist_entry=persist_recovery(source_id, callbacks),
            is_last_page=True,
            watermark=NOW,
        )
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=Clock())
        repeated = commit(
            repository,
            lease,
            ({"a": 1, "b": 2, "entry_id": "entry"},),
            persist_entry=lambda *args: pytest.fail("matching replay invoked callback"),
            is_last_page=True,
            watermark=NOW.astimezone(timezone(timedelta(hours=8))),
        )
    assert repeated.reused and repeated.failed_job_ids == original.failed_job_ids
    assert callbacks == ["entry"]


def test_null_legacy_receipt_fails_closed_without_callback_and_checks_lease_first(cursor_engine):
    source_id = seed_source(cursor_engine)
    clock = Clock()
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=clock)
        lease = claim(repository)
        commit(repository, lease, output_cursor={})
        session.execute(
            update(source_page_receipts)
            .where(source_page_receipts.c.source_id == source_id)
            .values(request_sha256=None)
        )
    before = row(cursor_engine, source_id)
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=clock)
        with pytest.raises(CursorCommitError, match="legacy_page_receipt_unverifiable"):
            commit(
                repository,
                lease,
                output_cursor={},
                persist_entry=lambda *args: pytest.fail("legacy callback"),
            )
        clock.now += timedelta(seconds=60)
        with pytest.raises(SourceLeaseLostError):
            commit(repository, lease, output_cursor={})
    assert row(cursor_engine, source_id) == before


@pytest.mark.parametrize(
    "legacy",
    [{}, {"position": {}, "window_complete": False, "pending_watermark_published_at": None}],
)
def test_unfinished_legacy_window_without_tracking_does_not_guess_empty_recovery(
    cursor_engine, legacy
):
    source_id = seed_source(cursor_engine)
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=Clock())
        lease = claim(repository)
        session.execute(
            update(source_cursors)
            .where(source_cursors.c.source_id == source_id)
            .values(cursor_json=legacy)
        )
    before = row(cursor_engine, source_id)
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=Clock())
        with pytest.raises(CursorCommitError, match="legacy_window_recovery_unverifiable"):
            commit(
                repository,
                lease,
                ({"entry_id": "never-persisted"},),
                is_last_page=True,
                persist_entry=lambda *args: pytest.fail("legacy window callback"),
                watermark=NOW,
            )
    assert row(cursor_engine, source_id) == before


@pytest.mark.parametrize("status", ["queued", "retry_wait", "running"])
def test_only_scheduled_recoverable_states_with_remaining_attempts_can_advance(
    cursor_engine, status
):
    source_id = seed_source(cursor_engine)
    with Session(cursor_engine) as session, session.begin():
        job_id = create_recovery_job(session, source_id, "recoverable")
        if status in {"retry_wait", "running"}:
            claim_job(session, job_id, "recovery-worker", NOW)
        if status == "retry_wait":
            schedule_retry_or_fail(
                session, job_id, "recovery-worker", False, NOW, expected_attempt=1
            )
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=Clock())
        receipt = commit(
            repository,
            claim(repository),
            ({"entry_id": "recoverable"},),
            is_last_page=True,
            watermark=NOW,
            persist_entry=lambda *args: PersistedPageEntry(failed_job_id=job_id),
        )
    assert (
        receipt.failed_job_ids == (job_id,)
        and row(cursor_engine, source_id)["watermark_published_at"] == NOW
    )
    assert row(cursor_engine, source_id)["cursor_json"]["pending_recovery_job_ids"] == []


@pytest.mark.parametrize(
    "invalid",
    [
        "exhausted_queued",
        "exhausted_running",
        "missing_schedule",
        "missing_lease",
        "missing_delivery",
    ],
)
def test_unrecoverable_or_exhausted_nonterminal_references_roll_back_page(cursor_engine, invalid):
    source_id = seed_source(cursor_engine)
    with Session(cursor_engine) as session, session.begin():
        job_id = create_recovery_job(session, source_id, "unrecoverable", max_attempts=1)
        if invalid == "missing_delivery":
            session.execute(outbox_events.delete().where(outbox_events.c.job_id == job_id))
        else:
            values = {"status": "queued", "attempt_count": 1}
            if invalid == "exhausted_running":
                values.update(
                    status="running",
                    lease_owner="worker",
                    lease_expires_at=NOW + timedelta(seconds=60),
                )
            elif invalid == "missing_schedule":
                values.update(status="retry_wait", attempt_count=0)
            elif invalid == "missing_lease":
                values.update(status="running", attempt_count=0)
            session.execute(update(job_runs).where(job_runs.c.job_id == job_id).values(**values))
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=Clock())
        lease = claim(repository)
    before = row(cursor_engine, source_id)
    with Session(cursor_engine) as session, session.begin(), pytest.raises(CursorCommitError):
        commit(
            SourceCursorRepository(session, ADMIN, source_id, clock=Clock()),
            lease,
            ({"entry_id": "unrecoverable"},),
            is_last_page=True,
            watermark=NOW,
            persist_entry=lambda *args: PersistedPageEntry(failed_job_id=job_id),
        )
    assert row(cursor_engine, source_id) == before


def test_final_page_rechecks_prior_job_after_actual_permanent_failure_and_takeover(cursor_engine):
    source_id, clock, callbacks = seed_source(cursor_engine), Clock(), []
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=clock)
        lease = claim(repository)
        receipt = commit(
            repository,
            lease,
            ({"entry_id": "prior"},),
            persist_entry=persist_recovery(source_id, callbacks),
            watermark=NOW,
        )
    job_id = receipt.failed_job_ids[0]

    def permanent(session, context, payload):
        raise JobExecutionError("actual_permanent_failure", permanent=True)

    assert (
        execute_job(
            cursor_engine, job_id, "job-worker", {"fixture-source-recovery": permanent}, clock=clock
        )
        == "failed"
    )
    clock.now += timedelta(seconds=60)
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=clock)
        resumed = claim(repository)
    before = row(cursor_engine, source_id)
    assert before["cursor_json"]["pending_recovery_job_ids"] == [
        {"job_id": job_id, "entry_id": "prior"}
    ]
    with Session(cursor_engine) as session, session.begin(), pytest.raises(CursorCommitError):
        commit(
            SourceCursorRepository(session, ADMIN, source_id, clock=clock),
            resumed,
            input_cursor={"page": 1},
            output_cursor={},
            is_last_page=True,
        )
    assert row(cursor_engine, source_id) == before and before["watermark_published_at"] is None
    with cursor_engine.connect() as connection:
        assert (
            connection.execute(
                select(job_payloads.c.job_id).where(job_payloads.c.job_id == job_id)
            ).scalar_one()
            == job_id
        )
        assert (
            connection.execute(
                select(func.count())
                .select_from(source_page_receipts)
                .where(source_page_receipts.c.source_id == source_id)
            ).scalar_one()
            == 1
        )


def test_same_transaction_later_callback_cannot_make_earlier_reference_terminal(cursor_engine):
    source_id, created = seed_source(cursor_engine), []

    def callback(session, entry):
        job_id = create_recovery_job(session, source_id, entry["entry_id"])
        created.append(job_id)
        if entry["entry_id"] == "second":
            session.execute(
                update(job_runs).where(job_runs.c.job_id == created[0]).values(status="blocked")
            )
        return PersistedPageEntry(failed_job_id=job_id)

    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=Clock())
        lease = claim(repository)
        with pytest.raises(CursorCommitError):
            commit(
                repository,
                lease,
                ({"entry_id": "first"}, {"entry_id": "second"}),
                persist_entry=callback,
                is_last_page=True,
                watermark=NOW,
            )
    assert row(cursor_engine, source_id)["last_successful_page"] == 0
    with cursor_engine.connect() as connection:
        assert (
            connection.execute(
                select(job_runs.c.job_id).where(job_runs.c.job_id.in_(created))
            ).all()
            == []
        )


def test_reference_limit_rejects_entire_page_and_keeps_prior_tracking(cursor_engine):
    source_id = seed_source(cursor_engine)
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=Clock())
        lease = claim(repository)
        state = (
            session.execute(
                select(source_cursors).where(
                    source_cursors.c.source_id == source_id,
                )
            )
            .mappings()
            .one()["cursor_json"]
        )
        state["pending_recovery_job_ids"] = [
            {"job_id": str(uuid4()), "entry_id": str(index)} for index in range(1000)
        ]
        session.execute(
            update(source_cursors)
            .where(source_cursors.c.source_id == source_id)
            .values(cursor_json=state)
        )
    before = row(cursor_engine, source_id)
    callbacks = []
    with (
        Session(cursor_engine) as session,
        session.begin(),
        pytest.raises(CursorCommitError, match="exceed bounded limit"),
    ):
        commit(
            SourceCursorRepository(session, ADMIN, source_id, clock=Clock()),
            lease,
            ({"entry_id": "over-limit"},),
            persist_entry=persist_recovery(source_id, callbacks),
        )
    assert row(cursor_engine, source_id) == before


def test_completed_window_tracking_does_not_recheck_terminal_jobs_from_old_history(cursor_engine):
    source_id, clock, callbacks = seed_source(cursor_engine), Clock(), []
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=clock)
        lease = claim(repository)
        receipt = commit(
            repository,
            lease,
            ({"entry_id": "old-window"},),
            persist_entry=persist_recovery(source_id, callbacks),
            is_last_page=True,
            watermark=NOW,
        )
        repository.release(lease)
        session.execute(
            update(job_runs)
            .where(job_runs.c.job_id == receipt.failed_job_ids[0])
            .values(status="failed")
        )
    clock.now += timedelta(days=1)
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=clock)
        next_window = repository.claim(
            stream_kind="live", lease_owner="worker", window_start=NOW, window_end=clock.now
        )
        commit(
            repository,
            next_window,
            input_cursor=next_window.cursor_json,
            output_cursor={},
            is_last_page=True,
            watermark=clock.now,
        )
    state = row(cursor_engine, source_id)
    assert state["watermark_published_at"] == clock.now
    assert state["cursor_json"]["pending_recovery_job_ids"] == []
    with cursor_engine.connect() as connection:
        assert connection.execute(
            select(source_page_receipts.c.failed_job_ids).where(
                source_page_receipts.c.source_id == source_id,
                source_page_receipts.c.page_key == receipt.page_key,
            )
        ).scalar_one() == list(receipt.failed_job_ids)
