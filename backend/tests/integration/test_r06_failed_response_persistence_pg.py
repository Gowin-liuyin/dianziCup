"""Offline transport failures retain durable PG evidence in an isolated catalog database."""

import hashlib
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from tests.integration.test_r06_catalog_documents_pg import (
    catalog_engine as _catalog_engine_fixture,
)
from tests.r06_source_worker_fixtures import avid_responses, source_response

from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.network import FetchResult, NetworkTimeoutError
from ai_intel.ingestion import source_jobs
from ai_intel.ingestion.source_catalog import (
    SourceCatalogError,
    build_catalog_request,
)
from ai_intel.ingestion.source_failure_models import source_response_receipts
from ai_intel.ingestion.source_failure_receipts import SourceResponseRecorder
from ai_intel.ingestion.source_jobs import (
    SOURCE_JOB_TYPE,
    SourcePageRequest,
    build_source_page_handler,
    enqueue_source_page,
)
from ai_intel.knowledge.models import (
    content_objects,
    document_revisions,
    documents,
    evidence,
    fetch_attempts,
    job_runs,
    source_cursors,
    source_page_receipts,
)
from ai_intel.knowledge.persistence_models import claims, events
from ai_intel.knowledge.revisions import cleanup_unreferenced_object
from ai_intel.workers.executor import JobExecutionContext, JobExecutionError, execute_job
from ai_intel.workers.jobs import claim_job

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 16, tzinfo=UTC)
ADMIN = AccessScope.for_authenticated_user("failure-fixture-admin", None, Role.SYSTEM_ADMIN)
catalog_engine = _catalog_engine_fixture


def queue(engine, kind, *, at=NOW, tenant_id=None, pages=20):
    with Session(engine) as session, session.begin():
        job_id = enqueue_source_page(
            session,
            SourcePageRequest(
                source_kind=kind, window_end=at - timedelta(seconds=1), remaining_pages=pages
            ),
            at,
        )
        if tenant_id is not None:
            session.execute(
                job_runs.update().where(job_runs.c.job_id == job_id).values(tenant_id=tenant_id)
            )
        return job_id


def run(engine, job_id, handler, at=NOW):
    return execute_job(
        engine, job_id, "failure-fixture-worker", {SOURCE_JOB_TYPE: handler}, clock=lambda: at
    )


def receipts(engine):
    with Session(engine) as session:
        return list(
            session.execute(
                text("SELECT * FROM source_response_receipts ORDER BY response_ordinal")
            ).mappings()
        )


def assert_no_business_effects(engine):
    with Session(engine) as session:
        for table in (
            documents,
            document_revisions,
            evidence,
            claims,
            events,
            source_cursors,
            source_page_receipts,
            fetch_attempts,
        ):
            assert session.scalar(select(func.count()).select_from(table)) == 0


@pytest.mark.parametrize(
    "failure",
    [
        "second_document",
        "cursor_commit",
        "continuation",
        "invalid_page",
        "blob_corrupt",
        "blob_limit",
    ],
)
def test_approved_contract_retains_raw_but_rolls_back_all_six_old_failure_effects(
    catalog_engine, tmp_path, monkeypatch, failure
):
    kind = "avid_community" if failure in {"blob_corrupt", "blob_limit"} else "arxiv_security"
    store = ContentStore(tmp_path / "raw")
    job_id = queue(catalog_engine, kind, pages=2)

    def unavailable(*args, **kwargs):
        raise OSError("synthetic persistence failure")

    if failure == "second_document":
        save = source_jobs.persist_catalog_documents

        def reject_after_save(*args, **kwargs):
            save(*args, **kwargs)
            raise OSError("synthetic failure after page documents")

        monkeypatch.setattr(source_jobs, "persist_catalog_documents", reject_after_save)
    elif failure == "cursor_commit":
        monkeypatch.setattr(source_jobs.SourceCursorRepository, "commit_page", unavailable)
    elif failure == "continuation":
        monkeypatch.setattr(source_jobs, "enqueue_source_page", unavailable)
    tree, blob = avid_responses()
    body, media = source_response("arxiv_security")

    def read(url):
        if failure == "invalid_page":
            return FetchResult(url, 200, "application/atom+xml", b"malformed source page")
        if kind == "arxiv_security":
            return FetchResult(url, 200, media, body)
        if "/git/blobs/" in url:
            if failure == "blob_limit":
                return FetchResult(url, 429, "application/json", b"", {"Retry-After": "13"})
            return FetchResult(
                url, 200, "application/json", blob.replace(b'"sha": "', b'"sha": "f')
            )
        return FetchResult(url, 200, "application/json", tree)

    handler = build_source_page_handler(store, fetcher=read, clock=lambda: NOW)
    assert run(catalog_engine, job_id, handler) == (
        "blocked" if failure in {"invalid_page", "blob_corrupt"} else "retry_wait"
    )
    assert_no_business_effects(catalog_engine)
    rows = receipts(catalog_engine)
    assert len(rows) == (2 if kind == "avid_community" else 1)
    hashes = {
        row["response_content_hash"] for row in rows if row["response_content_hash"] is not None
    }
    with Session(catalog_engine) as session:
        assert set(session.scalars(select(content_objects.c.content_hash))) == hashes
        assert session.scalar(select(func.count()).select_from(job_runs)) == 1
    for row in rows:
        if row["response_content_hash"]:
            assert (
                len(store.read_verified(row["response_content_hash"])) == row["response_size_bytes"]
            )


@pytest.mark.parametrize(
    ("kind", "media", "body"),
    [
        ("arxiv_security", "application/atom+xml", b"<feed><entry>"),
        ("trailofbits_blog", "application/rss+xml", b"<rss><channel>"),
        ("ollama_releases", "application/json", b"{not-json"),
        ("osv_ollama", "application/json", b'{"vulns":[1]}'),
        ("nvd_ollama", "application/json", b'{"vulnerabilities":[1]}'),
        ("vllm_vendor", "application/json", b"[1]"),
    ],
)
def test_invalid_page_body_survives_handler_rollback(catalog_engine, tmp_path, kind, media, body):
    store = ContentStore(tmp_path / "raw")
    job_id = queue(catalog_engine, kind)
    handler = build_source_page_handler(
        store,
        fetcher=lambda url: FetchResult(url, 200, media, body),
        poster=lambda url, request_body: FetchResult(url, 200, media, body),
        clock=lambda: NOW,
    )
    assert run(catalog_engine, job_id, handler) == "blocked"
    digest = hashlib.sha256(body).hexdigest()
    with Session(catalog_engine) as session:
        assert (
            session.scalar(
                select(content_objects.c.content_hash).where(
                    content_objects.c.content_hash == digest
                )
            )
            == digest
        )
        job = session.execute(select(job_runs).where(job_runs.c.job_id == job_id)).mappings().one()
        assert job["status"] == "blocked" and job["error_code"] == "source_response_invalid"
    assert store.read_verified(digest) == body
    row = receipts(catalog_engine)[0]
    assert row["response_content_hash"] == digest
    assert row["response_size_bytes"] == len(body)
    assert row["http_status"] == 200 and row["error_code"] == "source_response_invalid"
    assert_no_business_effects(catalog_engine)


def recorder_for(engine, store, job_id, *, scope=ADMIN):
    with Session(engine) as session, session.begin():
        claimed = claim_job(session, job_id, "receipt-fixture-worker", NOW)
    return SourceResponseRecorder(
        engine,
        store,
        scope,
        JobExecutionContext(job_id, "receipt-fixture-worker", claimed["attempt_count"], None),
        "arxiv_security",
        "backfill",
        NOW - timedelta(seconds=1),
        {},
    )


def test_avid_second_response_failure_keeps_tree_and_bad_blob_receipts(catalog_engine, tmp_path):
    store = ContentStore(tmp_path / "raw")
    tree, _ = avid_responses()
    broken_blob = b'{"encoding":"base64","content":"bad"}'

    def fetch(url):
        return FetchResult(
            url, 200, "application/json", broken_blob if "/git/blobs/" in url else tree
        )

    job_id = queue(catalog_engine, "avid_community")
    handler = build_source_page_handler(store, fetcher=fetch, clock=lambda: NOW)
    assert run(catalog_engine, job_id, handler) == "blocked"
    rows = receipts(catalog_engine)
    assert len(rows) == 2
    assert [row["response_content_hash"] for row in rows] == [
        hashlib.sha256(body).hexdigest() for body in (tree, broken_blob)
    ]
    assert [row["parse_outcome"] for row in rows] == ["normalized", "normalization_failed"]
    assert rows[0]["request_fingerprint_sha256"] != rows[1]["request_fingerprint_sha256"]
    assert_no_business_effects(catalog_engine)


@pytest.mark.parametrize("failure", ["write", "readback"])
def test_object_failure_leaves_accurate_metadata_and_no_cursor(catalog_engine, tmp_path, failure):
    delegate = ContentStore(tmp_path / "raw")

    class FailingStore:
        def store_bytes(self, payload):
            if failure == "write":
                raise OSError("synthetic storage error with credentials and body")
            return delegate.store_bytes(payload)

        def read_verified(self, digest):
            return b"corrupted response"

        def delete_object(self, digest):
            delegate.delete_object(digest)

    handler = build_source_page_handler(
        FailingStore(),
        fetcher=lambda url: FetchResult(url, 200, "application/atom+xml", b"<feed>"),
        clock=lambda: NOW,
    )
    job_id = queue(catalog_engine, "arxiv_security")
    assert run(catalog_engine, job_id, handler) == "retry_wait"
    row = receipts(catalog_engine)[0]
    assert row["http_status"] == 200
    assert row["response_content_hash"] is row["response_size_bytes"] is None
    assert row["error_code"] == "source_response_storage_failed"
    with Session(catalog_engine) as session:
        assert session.scalar(select(func.count()).select_from(content_objects)) == 0
    assert_no_business_effects(catalog_engine)


def test_business_pg_failure_rolls_back_but_durable_receipt_survives(
    catalog_engine, tmp_path, monkeypatch
):
    body, media = source_response("arxiv_security")
    store = ContentStore(tmp_path / "raw")

    def fail(*args, **kwargs):
        raise SQLAlchemyError("synthetic database error containing a secret")

    monkeypatch.setattr(source_jobs, "persist_catalog_documents", fail)
    job_id = queue(catalog_engine, "arxiv_security")
    handler = build_source_page_handler(
        store, fetcher=lambda url: FetchResult(url, 200, media, body), clock=lambda: NOW
    )
    assert run(catalog_engine, job_id, handler) == "retry_wait"
    row = receipts(catalog_engine)[0]
    assert row["parse_outcome"] == "normalized"
    assert row["response_content_hash"] == hashlib.sha256(body).hexdigest()
    assert store.read_verified(row["response_content_hash"]) == body
    with Session(catalog_engine) as session:
        assert (
            session.scalar(select(job_runs.c.error_code).where(job_runs.c.job_id == job_id))
            == "database_operation_failed"
        )
    assert_no_business_effects(catalog_engine)


def test_receipt_db_failure_prevents_parse_and_cursor(catalog_engine, tmp_path, monkeypatch):
    body = b"<feed>"
    store = ContentStore(tmp_path / "raw")

    def fail(*args, **kwargs):
        raise JobExecutionError("source_receipt_database_failed", retry_after_seconds=7)

    monkeypatch.setattr(SourceResponseRecorder, "record_response", fail)
    monkeypatch.setattr(
        source_jobs,
        "normalize_catalog_page",
        lambda *args, **kwargs: pytest.fail("receipt failure reached parser"),
    )
    job_id = queue(catalog_engine, "arxiv_security")
    handler = build_source_page_handler(
        store,
        fetcher=lambda url: FetchResult(url, 200, "application/atom+xml", body),
        clock=lambda: NOW,
    )
    assert run(catalog_engine, job_id, handler) == "retry_wait"
    assert receipts(catalog_engine) == []
    assert_no_business_effects(catalog_engine)


def test_actual_pg_receipt_insert_error_prevents_normalization(
    catalog_engine, tmp_path, monkeypatch
):
    store = ContentStore(tmp_path / "raw")
    with catalog_engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE source_response_receipts ADD CONSTRAINT "
                "fixture_receipt_insert_failure CHECK (false)"
            )
        )
    monkeypatch.setattr(
        source_jobs,
        "normalize_catalog_page",
        lambda *args, **kwargs: pytest.fail("receipt INSERT failure reached parser"),
    )
    job_id = queue(catalog_engine, "arxiv_security")
    handler = build_source_page_handler(
        store,
        fetcher=lambda url: FetchResult(url, 200, "application/atom+xml", b"<feed>"),
        clock=lambda: NOW,
    )
    assert run(catalog_engine, job_id, handler) == "retry_wait"
    with Session(catalog_engine) as session:
        assert (
            session.scalar(select(job_runs.c.error_code).where(job_runs.c.job_id == job_id))
            == "source_receipt_database_failed"
        )
        assert session.scalar(select(func.count()).select_from(content_objects)) == 0
    assert receipts(catalog_engine) == []
    assert_no_business_effects(catalog_engine)


def test_concurrent_receipt_replay_is_one_pg_row_and_retains_object(catalog_engine, tmp_path):
    store = ContentStore(tmp_path / "raw")
    job_id = queue(catalog_engine, "arxiv_security")
    recorder = recorder_for(catalog_engine, store, job_id)
    request = build_catalog_request("arxiv_security", {})
    response = FetchResult(
        "https://ignored.invalid?token=synthetic-secret", 200, "application/atom+xml", b"<feed>"
    )

    def write(_):
        return recorder.record_response(
            request, response, 1, NOW, allowed_content_types=("application/atom+xml",)
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(write, range(2)))
    assert ids[0] == ids[1] and len(receipts(catalog_engine)) == 1
    digest = hashlib.sha256(response.body).hexdigest()
    with Session(catalog_engine) as session, session.begin():
        assert cleanup_unreferenced_object(session, store, digest) is False
    assert store.read_verified(digest) == response.body
    changed = FetchResult(request.url, 200, "application/atom+xml", b"<changed>")
    with pytest.raises(JobExecutionError, match="source_receipt_replay_conflict"):
        recorder.record_response(
            request, changed, 1, NOW, allowed_content_types=("application/atom+xml",)
        )
    assert receipts(catalog_engine)[0]["response_content_hash"] == digest


def test_duplicate_worker_delivery_does_not_fetch_twice(catalog_engine, tmp_path):
    calls = []

    def fetch(url):
        calls.append(url)
        return FetchResult(url, 200, "application/atom+xml", b"<feed>")

    job_id = queue(catalog_engine, "arxiv_security")
    handler = build_source_page_handler(
        ContentStore(tmp_path / "raw"), fetcher=fetch, clock=lambda: NOW
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: run(catalog_engine, job_id, handler), range(2)))
    assert sorted(outcomes) == ["blocked", "not_claimed"]
    assert len(calls) == len(receipts(catalog_engine)) == 1


@pytest.mark.parametrize("status", [None, 401, 429, 503])
def test_transport_failure_never_fabricates_body_hash(catalog_engine, tmp_path, status):
    def fetch(url):
        if status is None:
            raise NetworkTimeoutError("synthetic secret diagnostics")
        return FetchResult(
            "https://ignored.invalid?token=secret",
            status,
            "text/plain",
            b"synthetic discarded diagnostics",
            {"Retry-After": "13"},
        )

    job_id = queue(catalog_engine, "arxiv_security")
    handler = build_source_page_handler(
        ContentStore(tmp_path / "raw"), fetcher=fetch, clock=lambda: NOW
    )
    assert run(catalog_engine, job_id, handler) == ("blocked" if status == 401 else "retry_wait")
    row = receipts(catalog_engine)[0]
    assert row["http_status"] == status
    assert row["response_content_hash"] is row["response_size_bytes"] is None
    assert row["parse_outcome"] == "transport_failed"
    assert_no_business_effects(catalog_engine)


def test_received_body_after_deadline_is_retained_without_parse_success(
    catalog_engine, tmp_path, monkeypatch
):
    current = [100.0]
    monkeypatch.setattr(source_jobs.time, "monotonic", lambda: current[0])
    body = b"<feed>"
    store = ContentStore(tmp_path / "raw")

    def fetch(url):
        current[0] += 13
        return FetchResult(url, 200, "application/atom+xml", body)

    job_id = queue(catalog_engine, "arxiv_security")
    handler = build_source_page_handler(store, fetcher=fetch, clock=lambda: NOW)
    assert run(catalog_engine, job_id, handler) == "retry_wait"
    row = receipts(catalog_engine)[0]
    assert row["response_content_hash"] == hashlib.sha256(body).hexdigest()
    assert row["parse_outcome"] == "received" and row["error_code"] == "network_timeout"
    assert_no_business_effects(catalog_engine)


def test_scope_denial_has_no_external_call_or_receipt(catalog_engine, tmp_path):
    job_id = queue(catalog_engine, "arxiv_security", tenant_id=str(uuid4()))
    handler = build_source_page_handler(
        ContentStore(tmp_path / "raw"),
        fetcher=lambda url: pytest.fail("tenant job fetched public source"),
        clock=lambda: NOW,
    )
    assert run(catalog_engine, job_id, handler) == "blocked"
    assert receipts(catalog_engine) == []
    assert_no_business_effects(catalog_engine)


def test_receipt_scope_and_context_checks_do_not_disclose_synthetic_secrets(
    catalog_engine, tmp_path, caplog
):
    job_id = queue(catalog_engine, "arxiv_security")
    scope = AccessScope.for_authenticated_user("fixture-viewer", str(uuid4()), Role.VIEWER)
    recorder = recorder_for(catalog_engine, ContentStore(tmp_path / "raw"), job_id, scope=scope)
    secret = "synthetic-source-secret-marker"
    response = FetchResult(
        "https://ignored.invalid?token=" + secret,
        200,
        "application/atom+xml",
        secret.encode(),
        {"Authorization": secret},
    )
    with pytest.raises(PermissionDeniedError):
        recorder.record_response(
            build_catalog_request("arxiv_security", {}),
            response,
            1,
            NOW,
            allowed_content_types=("application/atom+xml",),
        )
    assert receipts(catalog_engine) == []
    assert secret not in caplog.text


@pytest.mark.parametrize("mutation", ["owner", "attempt", "tenant", "expired"])
def test_stale_or_changed_committed_job_context_rejects_receipt(catalog_engine, tmp_path, mutation):
    job_id = queue(catalog_engine, "arxiv_security")
    store = ContentStore(tmp_path / "raw")
    recorder = recorder_for(catalog_engine, store, job_id)
    changes = {
        "owner": {"lease_owner": "new-worker"},
        "attempt": {"attempt_count": 2},
        "tenant": {"tenant_id": str(uuid4())},
        "expired": {"lease_expires_at": NOW},
    }
    with Session(catalog_engine) as session, session.begin():
        session.execute(
            job_runs.update().where(job_runs.c.job_id == job_id).values(**changes[mutation])
        )
    request = build_catalog_request("arxiv_security", {})
    with pytest.raises(JobExecutionError, match="source_receipt_context_invalid"):
        recorder.record_response(
            request,
            FetchResult(request.url, 200, "application/atom+xml", b"<feed>"),
            1,
            NOW,
            allowed_content_types=("application/atom+xml",),
        )
    assert receipts(catalog_engine) == []
    with Session(catalog_engine) as session:
        assert session.scalar(select(func.count()).select_from(content_objects)) == 0


def test_empty_http200_retains_actual_empty_bytes_not_missing_transport(catalog_engine, tmp_path):
    store = ContentStore(tmp_path / "raw")
    job_id = queue(catalog_engine, "arxiv_security")
    handler = build_source_page_handler(
        store,
        fetcher=lambda url: FetchResult(url, 200, "application/atom+xml", b""),
        clock=lambda: NOW,
    )
    assert run(catalog_engine, job_id, handler) == "blocked"
    row = receipts(catalog_engine)[0]
    assert row["response_size_bytes"] == 0
    assert row["response_content_hash"] == hashlib.sha256(b"").hexdigest()
    assert store.read_verified(row["response_content_hash"]) == b""


def test_response_metadata_excludes_url_headers_and_body(catalog_engine, tmp_path, caplog):
    job_id = queue(catalog_engine, "arxiv_security")
    recorder = recorder_for(catalog_engine, ContentStore(tmp_path / "raw"), job_id)
    request = build_catalog_request("arxiv_security", {})
    secret = "synthetic-secret-only-in-fixture-bytes"
    response = FetchResult(
        "https://ignored.invalid?token=" + secret,
        200,
        "application/atom+xml",
        secret.encode(),
        {"Authorization": secret, "X-Unknown": secret},
    )
    recorder.record_response(
        request, response, 1, NOW, allowed_content_types=("application/atom+xml",)
    )
    row = dict(receipts(catalog_engine)[0])
    assert not {"url", "final_url", "headers", "body", "worker_id", "tenant_id"} & set(row)
    assert secret not in str(row) and secret not in caplog.text


@pytest.mark.parametrize(
    "changed",
    [
        {"response_content_hash": None},
        {"response_size_bytes": None},
        {"parse_outcome": "normalized", "http_status": None},
        {"parse_outcome": "normalized", "error_code": "source_response_invalid"},
        {"parse_outcome": "normalization_failed", "error_code": None},
        {"parse_outcome": "transport_failed", "error_code": "network_error"},
        {"response_ordinal": 3},
        {"response_size_bytes": 5242881},
    ],
)
def test_database_constraints_reject_ambiguous_or_fabricated_receipts(
    catalog_engine, tmp_path, changed
):
    job_id = queue(catalog_engine, "arxiv_security")
    recorder = recorder_for(catalog_engine, ContentStore(tmp_path / "raw"), job_id)
    request = build_catalog_request("arxiv_security", {})
    recorder.record_response(
        request,
        FetchResult(request.url, 200, "application/atom+xml", b"<feed>"),
        1,
        NOW,
        allowed_content_types=("application/atom+xml",),
    )
    with pytest.raises(IntegrityError), catalog_engine.begin() as connection:
        connection.execute(source_response_receipts.update().values(**changed))
    assert len(receipts(catalog_engine)) == 1


def test_migrated_table_matches_model_and_new_process_can_read_failed_raw(catalog_engine, tmp_path):
    schema = inspect(catalog_engine)
    actual = {column["name"]: column for column in schema.get_columns("source_response_receipts")}
    assert set(actual) == set(source_response_receipts.c.keys())
    for column in source_response_receipts.columns:
        assert actual[column.name]["nullable"] == column.nullable
        assert str(actual[column.name]["type"].compile(catalog_engine.dialect)) == str(
            column.type.compile(catalog_engine.dialect)
        )
    foreign_keys = schema.get_foreign_keys("source_response_receipts")
    assert [(key["constrained_columns"], key["referred_table"]) for key in foreign_keys] == [
        (["response_content_hash"], "content_objects")
    ]
    store = ContentStore(tmp_path / "raw")
    body = b"<feed>"
    digest = hashlib.sha256(body).hexdigest()
    job_id = queue(catalog_engine, "arxiv_security")
    handler = build_source_page_handler(
        store,
        fetcher=lambda url: FetchResult(url, 200, "application/atom+xml", body),
        clock=lambda: NOW,
    )
    assert run(catalog_engine, job_id, handler) == "blocked"
    child = """
import os, sys
from pathlib import Path
from sqlalchemy import create_engine, text
from ai_intel.infrastructure.content_store import ContentStore
try:
    engine = create_engine(os.environ['TEST_DATABASE_URL'], connect_args={'connect_timeout': 5})
    with engine.connect() as connection:
        row = connection.execute(text(
            'SELECT response_content_hash, parse_outcome FROM source_response_receipts'
        )).one()
    assert row[0] == sys.argv[2] and row[1] == 'normalization_failed'
    assert ContentStore(Path(sys.argv[1])).read_verified(row[0]) == b'<feed>'
    engine.dispose()
except Exception:
    print('receipt_reopen_failed')
    raise SystemExit(1)
print('receipt_reopen_verified')
"""
    environment = dict(
        os.environ, TEST_DATABASE_URL=catalog_engine.url.render_as_string(hide_password=False)
    )
    completed = subprocess.run(
        [sys.executable, "-c", child, str(tmp_path / "raw"), digest],
        env=environment,
        capture_output=True,
        timeout=15,
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == b"receipt_reopen_verified"


def test_parse_failure_can_be_reprocessed_from_retained_bytes_after_fix(
    catalog_engine, tmp_path, monkeypatch
):
    body, media = source_response("arxiv_security")
    digest = hashlib.sha256(body).hexdigest()
    store = ContentStore(tmp_path / "raw")
    original = source_jobs.normalize_catalog_page

    def broken_parser(*args, **kwargs):
        raise SourceCatalogError("synthetic parser defect")

    monkeypatch.setattr(source_jobs, "normalize_catalog_page", broken_parser)
    failed_job = queue(catalog_engine, "arxiv_security")
    handler = build_source_page_handler(
        store, fetcher=lambda url: FetchResult(url, 200, media, body), clock=lambda: NOW
    )
    assert run(catalog_engine, failed_job, handler) == "blocked"
    assert_no_business_effects(catalog_engine)
    monkeypatch.setattr(source_jobs, "normalize_catalog_page", original)
    recovered_at = NOW + timedelta(seconds=8)
    recovered_job = queue(catalog_engine, "arxiv_security", at=recovered_at)
    repaired = build_source_page_handler(
        store,
        fetcher=lambda url: FetchResult(url, 200, media, store.read_verified(digest)),
        clock=lambda: recovered_at,
    )
    assert run(catalog_engine, recovered_job, repaired, at=recovered_at) == "succeeded"
    with Session(catalog_engine) as session:
        assert session.scalar(select(func.count()).select_from(documents)) == 2
        assert (
            session.scalar(select(job_runs.c.status).where(job_runs.c.job_id == failed_job))
            == "blocked"
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(fetch_attempts)
                .where(fetch_attempts.c.outcome == "succeeded")
            )
            == 1
        )
    rows = receipts(catalog_engine)
    assert len(rows) == 2
    assert {row["parse_outcome"] for row in rows} == {"normalization_failed", "normalized"}
    assert {row["response_content_hash"] for row in rows} == {digest}
