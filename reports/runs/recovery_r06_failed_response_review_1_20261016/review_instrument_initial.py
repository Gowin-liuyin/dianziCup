"""Independent context, success and unchanged failure checks in the reviewer database."""

import hashlib
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.integration.test_r06_failed_response_persistence_pg import (
    ADMIN, NOW, catalog_engine, queue, recorder_for, receipts, run,
)
from tests.integration.test_r06_source_worker_pg import handler_for

from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.network import FetchResult
from ai_intel.ingestion.source_catalog import CATALOG_SOURCES, build_catalog_request
from ai_intel.knowledge.models import content_objects, job_runs, outbox_events, text_blocks
from ai_intel.workers.executor import JobExecutionContext, JobExecutionError


@pytest.mark.parametrize("mutation", ["missing", "job_type", "source_kind", "stream_kind", "future_window", "beyond_payload_window"])
def test_false_context_does_not_publish_receipt(catalog_engine, tmp_path, mutation):
    store = ContentStore(tmp_path / "raw")
    job_id = queue(catalog_engine, "arxiv_security")
    recorder = recorder_for(catalog_engine, store, job_id)
    if mutation == "missing":
        recorder = replace(recorder, context=JobExecutionContext(str(uuid4()), "receipt-fixture-worker", 1, None))
    elif mutation == "job_type":
        with Session(catalog_engine) as session, session.begin():
            session.execute(job_runs.update().where(job_runs.c.job_id == job_id).values(job_type="unrelated_task"))
    elif mutation == "source_kind":
        recorder = replace(recorder, source_kind="ollama_releases")
    elif mutation == "stream_kind":
        recorder = replace(recorder, stream_kind="live")
    elif mutation == "future_window":
        recorder = replace(recorder, window_end=NOW + timedelta(seconds=1))
    else:
        recorder = replace(recorder, window_end=NOW)
    request = build_catalog_request(recorder.source_kind, {})
    with pytest.raises(JobExecutionError, match="source_receipt_context_invalid"):
        recorder.record_response(request, FetchResult(request.url, 200, "application/atom+xml", b"<feed>"), 1, NOW, allowed_content_types=("application/atom+xml",))
    assert receipts(catalog_engine) == []
    with Session(catalog_engine) as session:
        assert session.scalar(select(func.count()).select_from(content_objects)) == 0


def test_older_frozen_window_is_retained_exactly(catalog_engine, tmp_path):
    job_id = queue(catalog_engine, "arxiv_security")
    recorder = recorder_for(catalog_engine, ContentStore(tmp_path / "raw"), job_id)
    frozen = NOW - timedelta(days=1)
    recorder = replace(recorder, window_end=frozen)
    request = build_catalog_request("arxiv_security", {})
    recorder.record_response(request, FetchResult(request.url, 200, "application/atom+xml", b"<feed>"), 1, NOW, allowed_content_types=("application/atom+xml",))
    assert receipts(catalog_engine)[0]["window_end"] == frozen


@pytest.mark.parametrize("kind", tuple(CATALOG_SOURCES))
def test_normal_worker_receipts_keep_exact_response_context(catalog_engine, tmp_path, kind):
    store = ContentStore(tmp_path / "raw")
    job_id = queue(catalog_engine, kind, pages=1)
    assert run(catalog_engine, job_id, handler_for(store, kind, clock=lambda: NOW)) in {"succeeded", "partial"}
    rows = receipts(catalog_engine)
    assert len(rows) == (2 if kind == "avid_community" else 1)
    assert all(row["job_id"] == job_id and row["source_kind"] == kind and row["source_id"] == CATALOG_SOURCES[kind].source_id and row["parse_outcome"] == "normalized" and row["error_code"] is None for row in rows)
    for row in rows:
        body = store.read_verified(row["response_content_hash"])
        assert hashlib.sha256(body).hexdigest() == row["response_content_hash"]
        assert len(body) == row["response_size_bytes"]


def test_business_rollback_has_no_text_blocks_or_continuation_outbox(catalog_engine, tmp_path, monkeypatch):
    from ai_intel.ingestion import source_jobs
    save = source_jobs.persist_catalog_documents

    def reject_after_save(*args, **kwargs):
        save(*args, **kwargs)
        raise OSError("independent synthetic failure after document persistence")

    monkeypatch.setattr(source_jobs, "persist_catalog_documents", reject_after_save)
    job_id = queue(catalog_engine, "arxiv_security", pages=2)
    assert run(catalog_engine, job_id, handler_for(ContentStore(tmp_path / "raw"), "arxiv_security", clock=lambda: NOW)) == "retry_wait"
    with Session(catalog_engine) as session:
        assert session.scalar(select(func.count()).select_from(text_blocks)) == 0
        assert session.scalar(select(func.count()).select_from(outbox_events)) == 1
        assert session.scalar(select(func.count()).select_from(job_runs)) == 1
    assert len(receipts(catalog_engine)) == 1
