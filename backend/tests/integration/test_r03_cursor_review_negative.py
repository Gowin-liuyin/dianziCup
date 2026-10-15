"""Independent real-PG counterexamples for durable recovery and replay contracts."""

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from ai_intel.domain.access import AccessScope, Role
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.ingestion.cursor_repository import (
    PersistedPageEntry,
    SourceCursorRepository,
    make_page_key,
)
from ai_intel.ingestion.scheduler import CursorCommitError
from ai_intel.knowledge.models import job_runs, source_cursors, source_page_receipts
from ai_intel.workers.executor import JobExecutionError, execute_job

ADMIN = AccessScope.for_authenticated_user("independent-reviewer", None, Role.SYSTEM_ADMIN)
RUN = Path(__file__).resolve().parents[3] / "reports/runs/recovery_r03_cursor_fixes_20261015"


@pytest.fixture
def review_engine():
    engine = create_engine(
        os.environ["TEST_DATABASE_URL"],
        connect_args={
            "connect_timeout": 5,
            "options": "-c statement_timeout=20000 -c lock_timeout=5000",
        },
    )
    with engine.connect() as connection:
        assert (
            connection.execute(text("select current_database()")).scalar_one()
            == "test_dianzi_r03_cursor_fix_20261015"
        )
        assert (
            connection.execute(text("select version_num from alembic_version")).scalar_one()
            == "0012_source_page_fingerprint"
        )
    yield engine
    engine.dispose()


def seed_source(engine, now):
    source_id = str(uuid4())
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into sources(source_id,name,category,base_origin,"
                "visibility,tenant_id,created_at) values(:id,:name,'vendor_advisory',"
                "'https://example.invalid','public',NULL,:now)"
            ),
            {"id": source_id, "name": "independent-r03-review-" + source_id, "now": now},
        )
    return source_id


def observe(name, observation):
    observation["observed_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    (RUN / (name + ".observation.json")).write_text(
        json.dumps(observation, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(observation, default=str))


@pytest.mark.parametrize("terminal", ["permanent_failed", "blocked", "attempts_exhausted"])
def test_terminal_failure_is_not_a_recoverable_entry(review_engine, terminal):
    now = datetime.now(UTC)
    source_id = seed_source(review_engine, now)
    job_type = "independent-recovery-" + uuid4().hex
    payload = json.dumps({"source_id": source_id, "entry_id": "missing-raw-entry"}).encode()
    with Session(review_engine) as session, session.begin():
        job_id = enqueue_job(
            session,
            None,
            job_type,
            payload,
            now,
            max_attempts=1 if terminal == "attempts_exhausted" else 5,
        )

    def failed_handler(session, context, payload):
        raise JobExecutionError(
            "independent_upstream_failure",
            permanent=terminal == "permanent_failed",
            blocked=terminal == "blocked",
        )

    outcome = execute_job(
        review_engine, job_id, "independent-worker", {job_type: failed_handler}, clock=lambda: now
    )
    assert outcome == ("blocked" if terminal == "blocked" else "failed")
    accepted = False
    try:
        with Session(review_engine) as session, session.begin():
            repository = SourceCursorRepository(session, ADMIN, source_id, clock=lambda: now)
            lease = repository.claim(
                stream_kind="live",
                lease_owner="independent-source-worker",
                window_start=now - timedelta(days=1),
                window_end=now,
            )
            _receipt = repository.commit_page(
                lease,
                page_key=make_page_key(lease, {}),
                input_cursor={},
                output_cursor={"page": 1},
                entries=({"entry_id": "missing-raw-entry"},),
                persist_entry=lambda session, entry: PersistedPageEntry(failed_job_id=job_id),
                is_last_page=True,
                watermark_published_at=now,
            )
            accepted = True
    except CursorCommitError:
        pass
    with review_engine.connect() as connection:
        cursor = (
            connection.execute(
                select(source_cursors).where(source_cursors.c.source_id == source_id)
            )
            .mappings()
            .first()
        )
        job = (
            connection.execute(select(job_runs).where(job_runs.c.job_id == job_id)).mappings().one()
        )
    observe(
        "terminal_" + terminal,
        {
            "source_id": source_id,
            "job_id": job_id,
            "job_status": job["status"],
            "attempt_count": job["attempt_count"],
            "max_attempts": job["max_attempts"],
            "page_accepted": accepted,
            "cursor": dict(cursor) if cursor else None,
        },
    )
    assert not accepted, (
        "terminal failure has no automatic replay path but page/watermark committed"
    )


def test_same_page_key_different_entries_must_not_silently_reuse_receipt(review_engine):
    now = datetime.now(UTC)
    source_id = seed_source(review_engine, now)
    callbacks = []
    with Session(review_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=lambda: now)
        lease = repository.claim(
            stream_kind="live",
            lease_owner="review-replay",
            window_start=now - timedelta(days=1),
            window_end=now,
        )

        def durable_recovery(session, entry):
            callbacks.append(entry["entry_id"])
            job_id = enqueue_job(
                session,
                None,
                "source_recovery",
                json.dumps({"source_id": source_id, "entry_id": entry["entry_id"]}).encode(),
                now,
            )
            return PersistedPageEntry(failed_job_id=job_id)

        original = repository.commit_page(
            lease,
            page_key=make_page_key(lease, {}),
            input_cursor={},
            output_cursor={"page": 1},
            entries=({"entry_id": "original-entry"},),
            persist_entry=durable_recovery,
            is_last_page=True,
        )
    rejected = False
    with Session(review_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=lambda: now)
        try:
            repeated = repository.commit_page(
                lease,
                page_key=make_page_key(lease, {}),
                input_cursor={},
                output_cursor={"page": 1},
                entries=({"entry_id": "new-entry-not-saved"},),
                persist_entry=durable_recovery,
                is_last_page=True,
            )
        except CursorCommitError:
            rejected = True
    observe(
        "changed_replay_entries",
        {
            "source_id": source_id,
            "original_failed_job_ids": original.failed_job_ids,
            "changed_entry_rejected": rejected,
            "callbacks": callbacks,
            "receipt_reused": not rejected and repeated.reused,
        },
    )
    assert rejected, "same cursor/count with different entry identities reused an unrelated receipt"


def test_same_page_key_changed_completion_must_not_silently_reuse_receipt(review_engine):
    now = datetime.now(UTC)
    source_id = seed_source(review_engine, now)
    with Session(review_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=lambda: now)
        lease = repository.claim(
            stream_kind="live",
            lease_owner="review-finality",
            window_start=now - timedelta(days=1),
            window_end=now,
        )
        _original = repository.commit_page(
            lease,
            page_key=make_page_key(lease, {}),
            input_cursor={},
            output_cursor={},
            entries=(),
            persist_entry=lambda session, entry: False,
            is_last_page=False,
            watermark_published_at=now,
        )
    rejected = False
    with Session(review_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=lambda: now)
        try:
            repeated = repository.commit_page(
                lease,
                page_key=make_page_key(lease, {}),
                input_cursor={},
                output_cursor={},
                entries=(),
                persist_entry=lambda session, entry: False,
                is_last_page=True,
                watermark_published_at=now,
            )
        except CursorCommitError:
            rejected = True
    with review_engine.connect() as connection:
        cursor = (
            connection.execute(
                select(source_cursors).where(source_cursors.c.source_id == source_id)
            )
            .mappings()
            .one()
        )
        receipt_count = len(
            connection.execute(
                select(source_page_receipts.c.page_key).where(
                    source_page_receipts.c.source_id == source_id
                )
            ).all()
        )
    observe(
        "changed_replay_completion",
        {
            "source_id": source_id,
            "changed_completion_rejected": rejected,
            "receipt_reused": not rejected and repeated.reused,
            "receipt_count": receipt_count,
            "cursor": dict(cursor),
        },
    )
    assert rejected, (
        "completion changed but replay was reported successful while window stayed unfinished"
    )
