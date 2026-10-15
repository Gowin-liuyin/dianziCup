"""Real isolated PG scheduling with explicit fixture jobs; no source or broker live claims."""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from test_r06_catalog_documents_pg import ADMIN
from test_r06_catalog_documents_pg import catalog_engine as catalog_engine
from test_r06_source_worker_pg import handler_for

from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.ingestion.source_documents import ensure_source_registration
from ai_intel.ingestion.source_jobs import (
    SOURCE_JOB_TYPE,
    SourcePageRequest,
    enqueue_source_page,
)
from ai_intel.ingestion.source_polling import (
    MAX_ACTIVE_SOURCE_JOBS,
    SourcePollingError,
    enqueue_due_source_collections,
)
from ai_intel.knowledge.models import job_payloads, job_runs, outbox_events
from ai_intel.workers.executor import execute_job

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 15, 10, 17, tzinfo=UTC)


def tick(engine, at=NOW):
    with Session(engine) as session, session.begin():
        return enqueue_due_source_collections(session, ADMIN, at)


def mark_fixture_jobs_completed(engine):
    """Advance synthetic queue state for bucket tests; this is not worker execution evidence."""
    with engine.begin() as connection:
        connection.execute(update(job_runs).values(status="succeeded", finished_at=NOW))


def test_tick_registers_nine_sources_and_atomically_saves_bounded_live_jobs(catalog_engine):
    result = tick(catalog_engine)
    assert len(set(result.queued_job_ids)) == 9
    with Session(catalog_engine) as session:
        assert session.scalar(select(func.count()).select_from(job_runs)) == 9
        assert session.scalar(select(func.count()).select_from(outbox_events)) == 9
        requests = tuple(
            SourcePageRequest.model_validate_json(value)
            for value in session.scalars(select(job_payloads.c.payload))
        )
        assert len({request.source_kind for request in requests}) == 9
        assert all(
            request.remaining_pages == 5 and request.stream_kind == "live" for request in requests
        )
        assert all(
            request.window_end == datetime(2026, 10, 15, 10, tzinfo=UTC) for request in requests
        )
    repeated = tick(catalog_engine, NOW + timedelta(seconds=1))
    assert repeated.queued_job_ids == () and len(repeated.busy_sources) == 9


def test_completed_same_bucket_is_not_reenqueued_and_vendor_next_bucket_is(catalog_engine):
    tick(catalog_engine)
    mark_fixture_jobs_completed(catalog_engine)
    repeated = tick(catalog_engine, NOW + timedelta(seconds=1))
    assert repeated.already_scheduled == 9 and repeated.queued_job_ids == ()
    later = tick(catalog_engine, NOW.replace(minute=31))
    assert len(later.queued_job_ids) == 1 and later.already_scheduled == 8
    with Session(catalog_engine) as session:
        payload = session.scalar(
            select(job_payloads.c.payload).where(job_payloads.c.job_id == later.queued_job_ids[0])
        )
        request = SourcePageRequest.model_validate_json(payload)
        assert request.source_kind == "vllm_vendor"
        assert request.window_end == NOW.replace(minute=30)


def test_simultaneous_ticks_have_only_nine_durable_jobs(catalog_engine):
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = tuple(executor.map(lambda _: tick(catalog_engine), range(3)))
    assert sum(len(result.queued_job_ids) for result in results) == 9
    with Session(catalog_engine) as session:
        assert session.scalar(select(func.count()).select_from(job_runs)) == 9
        assert session.scalar(select(func.count()).select_from(outbox_events)) == 9


def test_poll_transaction_rollback_leaves_no_jobs_or_outbox(catalog_engine):
    with (
        pytest.raises(RuntimeError, match="fixture rollback"),
        Session(catalog_engine) as session,
        session.begin(),
    ):
        enqueue_due_source_collections(session, ADMIN, NOW)
        raise RuntimeError("fixture rollback")
    with Session(catalog_engine) as session:
        assert session.scalar(select(func.count()).select_from(job_runs)) == 0
        assert session.scalar(select(func.count()).select_from(outbox_events)) == 0


def test_pending_continuation_defers_only_its_source(catalog_engine):
    with Session(catalog_engine) as session, session.begin():
        ensure_source_registration(session, ADMIN, "osv_ollama", NOW)
        queued = enqueue_source_page(
            session,
            SourcePageRequest(source_kind="osv_ollama", window_end=NOW, remaining_pages=2),
            NOW,
            idempotency_key="source-next-fixture",
        )
    result = tick(catalog_engine)
    assert len(result.queued_job_ids) == 8 and result.busy_sources == ("osv_ollama",)
    assert queued not in result.queued_job_ids


@pytest.mark.parametrize("payload", [b"invalid-json", b"{}" + b" " * 4096])
def test_invalid_or_oversize_active_request_stops_new_rounds(catalog_engine, payload):
    with Session(catalog_engine) as session, session.begin():
        enqueue_job(
            session, None, SOURCE_JOB_TYPE, payload, NOW, idempotency_key="malformed-fixture"
        )
    with pytest.raises(SourcePollingError):
        tick(catalog_engine)
    with Session(catalog_engine) as session:
        assert session.scalar(select(func.count()).select_from(job_runs)) == 1


def test_full_source_queue_does_not_grow(catalog_engine):
    payload = SourcePageRequest(source_kind="nvd_ollama", window_end=NOW).model_dump_json().encode()
    with Session(catalog_engine) as session, session.begin():
        for _ in range(MAX_ACTIVE_SOURCE_JOBS + 1):
            enqueue_job(session, None, SOURCE_JOB_TYPE, payload, NOW)
    with pytest.raises(SourcePollingError, match="queue exceeds"):
        tick(catalog_engine)
    with Session(catalog_engine) as session:
        assert session.scalar(select(func.count()).select_from(job_runs)) == 501


def test_scheduler_job_executes_existing_source_worker_and_commits_pg(catalog_engine, tmp_path):
    queued = tick(catalog_engine).queued_job_ids
    with Session(catalog_engine) as session:
        identifier = next(
            identifier
            for identifier in queued
            if SourcePageRequest.model_validate_json(
                session.scalar(
                    select(job_payloads.c.payload).where(job_payloads.c.job_id == identifier)
                )
            ).source_kind
            == "osv_ollama"
        )
    result = execute_job(
        catalog_engine,
        identifier,
        "fixture-poller-worker",
        {SOURCE_JOB_TYPE: handler_for(ContentStore(tmp_path), "osv_ollama", clock=lambda: NOW)},
        clock=lambda: NOW,
    )
    assert result == "succeeded"
    with Session(catalog_engine) as session:
        row = (
            session.execute(select(job_runs).where(job_runs.c.job_id == identifier))
            .mappings()
            .one()
        )
        assert row["status"] == "succeeded" and row["attempt_count"] == 1
        assert row["result_ref"].startswith("pg:source:")


def test_other_process_restart_observes_existing_round(catalog_engine):
    tick(catalog_engine)
    script = """
import os
from datetime import UTC, datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from ai_intel.domain.access import AccessScope, Role
from ai_intel.ingestion.source_polling import enqueue_due_source_collections
try:
    engine = create_engine(os.environ['TEST_DATABASE_URL'], connect_args={'connect_timeout': 5})
    with Session(engine) as session, session.begin():
        scope = AccessScope.for_authenticated_user('fixture-restart', None, Role.SYSTEM_ADMIN)
        at = datetime(2026,10,15,10,17,tzinfo=UTC)
        result = enqueue_due_source_collections(session, scope, at)
    engine.dispose()
    assert len(result.busy_sources) == 9 and not result.queued_job_ids
    print('restart preserved nine active source rounds')
except Exception as error:
    print(type(error).__name__)
    raise SystemExit(1) from None
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", script],
        env=dict(
            os.environ, TEST_DATABASE_URL=catalog_engine.url.render_as_string(hide_password=False)
        ),
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert result.returncode == 0, result.stdout
    assert "restart preserved nine active source rounds" in result.stdout
