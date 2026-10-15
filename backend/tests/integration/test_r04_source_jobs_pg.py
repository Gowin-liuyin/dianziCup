"""实际隔离 PG 的分页任务与游标原子性；来源响应为显式录制 fixture。"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from test_r02_schema_migration import empty_schema_engine as empty_schema_engine

from ai_intel.domain.access import AccessScope, Role
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.network import FetchResult, NetworkTimeoutError
from ai_intel.ingestion.cursor_repository import SourceCursorRepository, make_page_key
from ai_intel.ingestion.source_documents import ensure_source_registration
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
NEXT_AFTER = "Y3Vyc29yOnYyOpHOAAg-eQ=="
RECORDED_LINK = (
    "<https://api.github.com/repositories/599547518/security-advisories?"
    'per_page=10&state=published&after=Y3Vyc29yOnYyOpHOAAg-eQ%3D%3D>; rel="next"'
)


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
        fetcher=lambda url: FetchResult(
            url, 200, "application/json", body, {"Link": RECORDED_LINK}
        ),
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
        assert session.scalar(select(source_cursors.c.cursor_json))["position"] == {
            "cursor_version": 2,
            "after": NEXT_AFTER,
        }


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


@pytest.mark.parametrize("last_page_empty", [False, True])
def test_vendor_two_pages_commit_actual_after_and_terminal_window(
    job_engine, tmp_path, last_page_empty
):
    body = (FIXTURES / "vllm_api_page_20261015_public.json").read_bytes()
    first = queue(job_engine, kind="vllm_vendor")
    current = [NOW]
    seen_urls = []

    def read_page(url):
        seen_urls.append(url)
        if len(seen_urls) == 1:
            return FetchResult(url, 200, "application/json", body, {"Link": RECORDED_LINK})
        assert url == (
            "https://api.github.com/repos/vllm-project/vllm/security-advisories?"
            "per_page=10&state=published&after=Y3Vyc29yOnYyOpHOAAg-eQ%3D%3D"
        )
        record = json.loads(body)[0]
        record.update(
            ghsa_id="GHSA-2345-2345-2345",
            cve_id=None,
            html_url="https://github.com/vllm-project/vllm/security/advisories/GHSA-2345-2345-2345",
        )
        last_body = b"[]" if last_page_empty else json.dumps([record]).encode()
        return FetchResult(url, 200, "application/json", last_body)

    handler = build_source_page_handler(
        ContentStore(tmp_path), fetcher=read_page, clock=lambda: current[0]
    )
    assert (
        execute_job(
            job_engine, first, "worker-first", {SOURCE_JOB_TYPE: handler}, clock=lambda: current[0]
        )
        == "succeeded"
    )
    with Session(job_engine) as session:
        next_job = session.scalar(
            select(job_runs.c.job_id).where(
                job_runs.c.job_id != first, job_runs.c.job_type == SOURCE_JOB_TYPE
            )
        )
        assert session.scalar(
            select(outbox_events.c.next_delivery_at).where(outbox_events.c.job_id == next_job)
        ) == NOW + timedelta(seconds=7)
    current[0] += timedelta(seconds=8)
    assert (
        execute_job(
            job_engine,
            next_job,
            "worker-second",
            {SOURCE_JOB_TYPE: handler},
            clock=lambda: current[0],
        )
        == "succeeded"
    )
    assert len(seen_urls) == 2 and "page=" not in seen_urls[0].replace("per_page=", "")
    with Session(job_engine) as session:
        state = session.scalar(select(source_cursors.c.cursor_json))
        assert state["position"] == {} and state["window_complete"] is True
        assert session.scalar(select(func.count()).select_from(source_page_receipts)) == 2
        assert session.scalar(select(func.count()).select_from(fetch_attempts)) == 2
        assert session.scalar(select(func.count()).select_from(events)) == (
            10 if last_page_empty else 11
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(job_runs)
                .where(job_runs.c.job_type == SOURCE_JOB_TYPE)
            )
            == 2
        )


def test_vendor_full_page_without_link_completes_without_unnecessary_next_job(job_engine, tmp_path):
    body = (FIXTURES / "vllm_api_page_20261015_public.json").read_bytes()
    job_id = queue(job_engine, kind="vllm_vendor")
    handler = build_source_page_handler(
        ContentStore(tmp_path),
        fetcher=lambda url: FetchResult(url, 200, "application/json", body),
        clock=lambda: NOW,
    )
    assert (
        execute_job(job_engine, job_id, "worker", {SOURCE_JOB_TYPE: handler}, clock=lambda: NOW)
        == "succeeded"
    )
    with Session(job_engine) as session:
        assert session.scalar(select(source_cursors.c.cursor_json))["window_complete"] is True
        assert (
            session.scalar(
                select(func.count())
                .select_from(job_runs)
                .where(job_runs.c.job_type == SOURCE_JOB_TYPE)
            )
            == 1
        )
        assert session.scalar(select(func.count()).select_from(events)) == 10


@pytest.mark.parametrize(
    "link",
    [
        RECORDED_LINK.replace("api.github.com", "127.0.0.1"),
        RECORDED_LINK + ", " + RECORDED_LINK,
        RECORDED_LINK.replace("&after=", "&page=2&after="),
        RECORDED_LINK.replace("599547518", "599547519"),
    ],
    ids=["private-host", "duplicate-next", "mixed-query", "other-repository"],
)
def test_malicious_vendor_link_rolls_back_entire_page(job_engine, tmp_path, link):
    body = (FIXTURES / "vllm_api_page_20261015_public.json").read_bytes()
    job_id = queue(job_engine, kind="vllm_vendor")
    handler = build_source_page_handler(
        ContentStore(tmp_path),
        fetcher=lambda url: FetchResult(url, 200, "application/json", body, {"Link": link}),
        clock=lambda: NOW,
    )
    assert (
        execute_job(job_engine, job_id, "worker", {SOURCE_JOB_TYPE: handler}, clock=lambda: NOW)
        == "blocked"
    )
    with Session(job_engine) as session:
        for table in (
            document_revisions,
            fetch_attempts,
            source_page_receipts,
            source_cursors,
            events,
        ):
            assert session.scalar(select(func.count()).select_from(table)) == 0
        assert session.scalar(select(job_runs.c.error_code)) == "source_response_invalid"


def test_vendor_repeated_after_preserves_prior_page_receipt_and_cursor(job_engine, tmp_path):
    first = queue(job_engine, kind="vllm_vendor")
    current = [NOW]
    body = (FIXTURES / "vllm_api_page_20261015_public.json").read_bytes()
    handler = build_source_page_handler(
        ContentStore(tmp_path),
        fetcher=lambda url: FetchResult(
            url, 200, "application/json", body, {"Link": RECORDED_LINK}
        ),
        clock=lambda: current[0],
    )
    assert (
        execute_job(
            job_engine, first, "worker", {SOURCE_JOB_TYPE: handler}, clock=lambda: current[0]
        )
        == "succeeded"
    )
    with Session(job_engine) as session:
        next_job = session.scalar(
            select(job_runs.c.job_id).where(
                job_runs.c.job_id != first, job_runs.c.job_type == SOURCE_JOB_TYPE
            )
        )
        before = session.execute(select(source_cursors)).mappings().one()
    current[0] += timedelta(seconds=8)
    assert (
        execute_job(
            job_engine,
            next_job,
            "worker-next",
            {SOURCE_JOB_TYPE: handler},
            clock=lambda: current[0],
        )
        == "blocked"
    )
    with Session(job_engine) as session:
        after = session.execute(select(source_cursors)).mappings().one()
        assert dict(after) == dict(before)
        assert session.scalar(select(func.count()).select_from(source_page_receipts)) == 1
        assert session.scalar(select(func.count()).select_from(fetch_attempts)) == 1
        assert session.scalar(select(func.count()).select_from(document_revisions)) == 10


def test_legacy_vendor_page_cursor_is_blocked_without_fetch_or_receipt_reset(job_engine, tmp_path):
    scope = AccessScope.for_authenticated_user("fixture-admin", None, Role.SYSTEM_ADMIN)
    with Session(job_engine) as session, session.begin():
        source_id = ensure_source_registration(session, scope, "vllm_vendor", NOW)
        repository = SourceCursorRepository(session, scope, source_id, clock=lambda: NOW)
        lease = repository.claim(
            stream_kind="backfill",
            lease_owner="fixture-legacy-owner",
            window_start=None,
            window_end=NOW - timedelta(seconds=1),
        )
        repository.commit_page(
            lease,
            page_key=make_page_key(lease, {}),
            input_cursor={},
            output_cursor={"page": 2},
            entries=(),
            persist_entry=lambda session, entry: None,
            is_last_page=False,
        )
        repository.release(lease)
    with Session(job_engine) as session:
        before = session.execute(select(source_cursors)).mappings().one()
    job_id = queue(job_engine, kind="vllm_vendor")
    seen = []

    def unexpected_fetch(url):
        seen.append(url)
        raise AssertionError("legacy cursor must not fetch")

    handler = build_source_page_handler(
        ContentStore(tmp_path), fetcher=unexpected_fetch, clock=lambda: NOW + timedelta(seconds=8)
    )
    assert (
        execute_job(
            job_engine,
            job_id,
            "worker",
            {SOURCE_JOB_TYPE: handler},
            clock=lambda: NOW + timedelta(seconds=8),
        )
        == "blocked"
    )
    assert seen == []
    with Session(job_engine) as session:
        assert dict(session.execute(select(source_cursors)).mappings().one()) == dict(before)
        assert session.scalar(select(func.count()).select_from(source_page_receipts)) == 1
        assert session.scalar(select(func.count()).select_from(fetch_attempts)) == 0
        assert (
            session.scalar(select(job_runs.c.error_code)) == "legacy_vendor_cursor_requires_restart"
        )
