"""实际隔离 PG 的分页任务与游标原子性；来源响应为显式录制 fixture。"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from test_r02_schema_migration import empty_schema_engine as empty_schema_engine

from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.network import FetchResult, NetworkTimeoutError
from ai_intel.ingestion.source_jobs import (
    SOURCE_JOB_TYPE,
    SourcePageRequest,
    build_source_page_handler,
    enqueue_source_page,
)
from ai_intel.knowledge.models import (
    document_revisions,
    fetch_attempts,
    job_runs,
    outbox_events,
    source_cursors,
    source_page_receipts,
)
from ai_intel.knowledge.persistence_models import (
    claims,
    event_documents,
    event_external_ids,
    events,
)
from ai_intel.workers.executor import execute_job

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 15, 6, 0, tzinfo=UTC)
FIXTURES = Path(__file__).resolve().parents[3] / "fixtures/recorded"


@pytest.fixture
def job_engine(empty_schema_engine):
    run_migrations(empty_schema_engine.url.render_as_string(hide_password=False))
    return empty_schema_engine


def queue(engine, *, kind="nvd_ollama", pages=20):
    with Session(engine) as session, session.begin():
        return enqueue_source_page(
            session,
            SourcePageRequest(
                source_kind=kind, window_end=NOW - timedelta(seconds=1), remaining_pages=pages
            ),
            NOW,
        )


def nvd_response(*, next_page=False):
    body = (FIXTURES / "nvd_api_20261015_public.json").read_bytes()
    payload = json.loads(body)
    payload["totalResults"] = 2 if next_page else 1
    body = json.dumps(payload).encode()
    return FetchResult("https://services.nvd.nist.gov", 200, "application/json", body)


def test_actual_vendor_page_with_unknown_package_persists_all_ten_records(job_engine, tmp_path):
    body = (FIXTURES / "vllm_api_page_20261015_public.json").read_bytes()
    store = ContentStore(tmp_path)
    handler = build_source_page_handler(
        store,
        fetcher=lambda url: FetchResult(url, 200, "application/json", body),
        clock=lambda: NOW,
    )
    job_id = queue(job_engine, kind="vllm_vendor")
    assert (
        execute_job(
            job_engine, job_id, "fixture-worker", {SOURCE_JOB_TYPE: handler}, clock=lambda: NOW
        )
        == "succeeded"
    )
    with Session(job_engine) as session:
        assert session.scalar(select(func.count()).select_from(events)) == 10
        revision_id = session.scalar(
            select(event_documents.c.revision_id)
            .join(event_external_ids, event_external_ids.c.event_id == event_documents.c.event_id)
            .where(event_external_ids.c.id_value == "GHSA-5FJ9-PFHR-6J48")
        )
        assert revision_id is not None
        assert (
            session.scalar(
                select(func.count())
                .select_from(claims)
                .where(
                    claims.c.source_revision_id == revision_id,
                    claims.c.predicate == "affected_product",
                )
            )
            == 0
        )
        digest = session.scalar(
            select(document_revisions.c.content_hash).where(
                document_revisions.c.revision_id == revision_id
            )
        )
        raw = json.loads(store.read_verified(digest))
        assert raw["vulnerabilities"][0]["package"] == {"ecosystem": "", "name": ""}
        assert raw["vulnerabilities"][0]["vulnerable_version_range"] == "< v0.30.0"
        assert session.scalar(select(source_cursors.c.cursor_json))["position"] == {"page": 2}


def test_real_job_commits_revision_receipt_cursor_and_terminal_state_together(job_engine, tmp_path):
    job_id = queue(job_engine)
    handler = build_source_page_handler(
        ContentStore(tmp_path), fetcher=lambda url: nvd_response(), clock=lambda: NOW
    )
    assert (
        execute_job(
            job_engine, job_id, "fixture-worker", {SOURCE_JOB_TYPE: handler}, clock=lambda: NOW
        )
        == "succeeded"
    )
    assert (
        execute_job(
            job_engine, job_id, "duplicate-worker", {SOURCE_JOB_TYPE: handler}, clock=lambda: NOW
        )
        == "not_claimed"
    )
    with Session(job_engine) as session:
        assert session.scalar(select(func.count()).select_from(document_revisions)) == 1
        assert session.scalar(select(func.count()).select_from(source_page_receipts)) == 1
        cursor = session.execute(select(source_cursors)).mappings().one()
        assert cursor["cursor_json"]["position"] == {}
        assert cursor["cursor_json"]["window_complete"] is True
        assert cursor["watermark_published_at"] is None
        assert cursor["lease_owner"] is None
        assert (
            session.scalar(select(job_runs.c.result_ref).where(job_runs.c.job_id == job_id))
            == "pg:source:" + cursor["source_id"]
        )
        assert session.scalar(select(fetch_attempts.c.response_content_hash))


@pytest.mark.parametrize("failure", ["storage", "invalid_json", "wrong_offset", "timeout", "auth"])
def test_failed_page_never_publishes_revision_or_advances_cursor(
    job_engine, tmp_path, monkeypatch, failure
):
    job_id = queue(job_engine)
    store = ContentStore(tmp_path)
    if failure == "storage":

        def unavailable(content):
            raise OSError("fixture object storage unavailable")

        monkeypatch.setattr(store, "store_bytes", unavailable)

    def read_page(url):
        if failure == "timeout":
            raise NetworkTimeoutError("fixture timeout")
        if failure == "auth":
            return FetchResult(url, 403, "", b"")
        if failure == "invalid_json":
            return FetchResult(url, 200, "application/json", b'{"duplicate":1,"duplicate":2}')
        result = nvd_response()
        if failure == "wrong_offset":
            value = json.loads(result.body)
            value["startIndex"] = 99
            return FetchResult(url, 200, "application/json", json.dumps(value).encode())
        return result

    handler = build_source_page_handler(store, fetcher=read_page, clock=lambda: NOW)
    outcome = execute_job(
        job_engine, job_id, "fixture-worker", {SOURCE_JOB_TYPE: handler}, clock=lambda: NOW
    )
    assert outcome in {"retry_wait", "blocked"}
    with Session(job_engine) as session:
        for table in (document_revisions, source_cursors, source_page_receipts, fetch_attempts):
            assert session.scalar(select(func.count()).select_from(table)) == 0
        assert session.scalar(select(job_runs.c.status)) == outcome


@pytest.mark.parametrize("pages", [1, 2])
def test_next_page_is_durable_delayed_or_explicitly_partial(job_engine, tmp_path, pages):
    job_id = queue(job_engine, pages=pages)
    handler = build_source_page_handler(
        ContentStore(tmp_path), fetcher=lambda url: nvd_response(next_page=True), clock=lambda: NOW
    )
    assert execute_job(
        job_engine, job_id, "fixture-worker", {SOURCE_JOB_TYPE: handler}, clock=lambda: NOW
    ) == ("partial" if pages == 1 else "succeeded")
    with Session(job_engine) as session:
        cursor = session.execute(select(source_cursors)).mappings().one()
        assert cursor["cursor_json"]["position"] == {"offset": 1}
        assert cursor["cursor_json"]["window_complete"] is False
        assert cursor["watermark_published_at"] is None
        if pages == 1:
            assert (
                session.scalar(select(job_runs.c.error_code).where(job_runs.c.job_id == job_id))
                == "source_page_limit_reached"
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(job_runs)
                    .where(job_runs.c.job_type == SOURCE_JOB_TYPE)
                )
                == 1
            )
        else:
            next_job = (
                session.execute(
                    select(job_runs).where(
                        job_runs.c.job_id != job_id, job_runs.c.job_type == SOURCE_JOB_TYPE
                    )
                )
                .mappings()
                .one()
            )
            assert next_job["status"] == "queued"
            assert session.scalar(
                select(outbox_events.c.next_delivery_at).where(
                    outbox_events.c.job_id == next_job["job_id"]
                )
            ) == NOW + timedelta(seconds=7)


def test_real_pg_timeout_does_not_erase_prior_successful_window(job_engine, tmp_path):
    first = queue(job_engine)
    handler = build_source_page_handler(
        ContentStore(tmp_path), fetcher=lambda url: nvd_response(), clock=lambda: NOW
    )
    assert (
        execute_job(job_engine, first, "worker-1", {SOURCE_JOB_TYPE: handler}, clock=lambda: NOW)
        == "succeeded"
    )
    with job_engine.connect() as connection:
        before = connection.execute(
            text("SELECT cursor_json,last_successful_page,window_end FROM source_cursors")
        ).one()
    second = queue(job_engine)

    def unavailable(url):
        raise NetworkTimeoutError("fixture timeout")

    later = NOW + timedelta(seconds=10)
    failing = build_source_page_handler(
        ContentStore(tmp_path), fetcher=unavailable, clock=lambda: later
    )
    assert (
        execute_job(job_engine, second, "worker-2", {SOURCE_JOB_TYPE: failing}, clock=lambda: later)
        == "retry_wait"
    )
    with job_engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT cursor_json,last_successful_page,window_end FROM source_cursors")
            ).one()
            == before
        )
