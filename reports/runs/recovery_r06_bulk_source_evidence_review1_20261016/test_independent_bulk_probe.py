"""Independent PostgreSQL failures, scope collision and observed two-writer lock checks."""

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from tests.integration.test_r06_bulk_source_evidence_pg import empty_revision, source_block
from tests.integration.test_r06_catalog_documents_pg import ADMIN, NOW, paper, save
from tests.integration.test_r06_catalog_documents_pg import catalog_engine as catalog_engine
from tests.integration.test_r06_source_worker_pg import queue, run
from tests.integration.test_r04_source_documents import vendor_record, vendor_response

from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.network import FetchResult
from ai_intel.ingestion.catalog_documents import persist_catalog_documents
from ai_intel.ingestion.source_catalog import SourceCatalogError
from ai_intel.ingestion.source_failure_models import source_response_receipts
from ai_intel.ingestion.source_jobs import build_source_page_handler
from ai_intel.knowledge.models import (
    document_revisions,
    documents,
    evidence,
    fetch_attempts,
    job_runs,
    source_cursors,
    source_page_receipts,
    text_blocks,
)
from ai_intel.knowledge.revisions import (
    QuoteConsistencyError,
    add_text_block,
    register_response_content,
    register_source_revision_blocks,
)

pytestmark = pytest.mark.real_pg


def test_actual_second_batch_constraint_failure_preserves_only_preexisting_row(catalog_engine, tmp_path):
    revision_id = empty_revision(catalog_engine, ContentStore(tmp_path))
    with Session(catalog_engine) as session, session.begin():
        existing = add_text_block(session, revision_id, 500, 0, 8, "existing")
    with Session(catalog_engine) as session, session.begin():
        with pytest.raises(IntegrityError):
            register_source_revision_blocks(session, revision_id, tuple(source_block(index) for index in range(501)), "public", None, NOW, attach_full_block_evidence=True)
        assert session.execute(select(text_blocks.c.block_id, text_blocks.c.ordinal)).all() == [(existing, 500)]
        assert session.scalar(select(func.count()).select_from(evidence)) == 0
        assert session.scalar(text("SELECT 42")) == 42


def test_revision_row_lock_blocks_real_source_updater_and_preserves_history(catalog_engine, tmp_path):
    store = ContentStore(tmp_path)
    member = replace(paper(), source_record_id=uuid4().hex)
    original = save(catalog_engine, store, (member,)).revision_ids[0]
    with Session(catalog_engine) as session, session.begin():
        session.execute(evidence.delete().where(evidence.c.revision_id == original))
        session.execute(text_blocks.delete().where(text_blocks.c.revision_id == original))
    lock_held, updater_ready, release = threading.Event(), threading.Event(), threading.Event()
    pids = {}

    def block_writer():
        with Session(catalog_engine) as session, session.begin():
            pids["block_writer"] = session.scalar(text("SELECT pg_backend_pid()"))
            register_source_revision_blocks(session, original, (source_block(),), "public", None, NOW, attach_full_block_evidence=True)
            lock_held.set()
            assert release.wait(10)

    def source_updater():
        assert lock_held.wait(10)
        updater_engine = create_engine(catalog_engine.url, hide_parameters=True)
        try:
            with Session(updater_engine) as session, session.begin():
                pids["source_updater"] = session.scalar(text("SELECT pg_backend_pid()"))
                response = register_response_content(session, store, b"independent source update", NOW)
                updater_ready.set()
                changed = replace(member, metadata={"version_label": "v2"})
                return persist_catalog_documents(session, store, ADMIN, "arxiv_security", (changed,), response_hash=response.content_hash, observed_at=NOW, ingested_at=NOW)
        finally:
            updater_engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(block_writer), pool.submit(source_updater)
        try:
            assert updater_ready.wait(10)
            observed = False
            deadline = time.perf_counter() + 5
            while time.perf_counter() < deadline:
                with catalog_engine.connect() as connection:
                    blocking = connection.scalar(text("SELECT pg_blocking_pids(:pid)"), {"pid": pids["source_updater"]})
                if pids["block_writer"] in blocking:
                    observed = True
                    break
                time.sleep(0.02)
            assert observed and not second.done()
        finally:
            release.set()
        first.result(timeout=10)
        saved = second.result(timeout=10)
    assert saved.new_revision_count == 1 and saved.revision_ids != (original,)
    with Session(catalog_engine) as session, session.begin():
        assert session.scalar(select(document_revisions.c.is_current).where(document_revisions.c.revision_id == original)) is False
        assert session.scalar(select(func.count()).select_from(evidence).where(evidence.c.revision_id == original)) == 1
        with pytest.raises(QuoteConsistencyError):
            register_source_revision_blocks(session, original, (source_block(1),), "public", None, NOW, attach_full_block_evidence=True)


def test_document_scope_collision_is_rejected_before_bulk_writes(catalog_engine, tmp_path):
    store = ContentStore(tmp_path)
    member = replace(paper(), source_record_id=uuid4().hex)
    first = save(catalog_engine, store, (member,))
    with Session(catalog_engine) as session, session.begin():
        session.execute(update(documents).values(visibility="tenant", tenant_id="isolated-other-tenant"))
    with pytest.raises(SourceCatalogError, match="identity or scope"):
        save(catalog_engine, store, (replace(member, metadata={"version_label": "v2"}),))
    with catalog_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(document_revisions)) == 1
        assert connection.scalar(select(func.count()).select_from(evidence)) == 2
        assert connection.scalar(select(document_revisions.c.revision_id)) == first.revision_ids[0]


def test_sql_failure_in_second_evidence_batch_keeps_receipt_and_rolls_back_job_page(catalog_engine, tmp_path):
    record = {"id": 90123, "tag_name": "v1.2.3", "name": "isolated replay", "body": "independent fixture", "html_url": "https://github.com/ollama/ollama/releases/tag/v1.2.3", "published_at": "2026-10-15T00:00:00Z", "draft": False, "prerelease": False, "extra": list(range(600))}
    raw = json.dumps([record]).encode()
    store = ContentStore(tmp_path)
    writes = 0

    def fail_second_evidence(connection, cursor, statement, parameters, context, executemany):
        nonlocal writes
        if statement.startswith("INSERT INTO evidence"):
            writes += 1
            if writes == 2:
                connection.exec_driver_sql("SELECT 1 / 0")

    event.listen(catalog_engine, "before_cursor_execute", fail_second_evidence)
    try:
        job = queue(catalog_engine, "ollama_releases")
        handler = build_source_page_handler(store, fetcher=lambda url: FetchResult(url, 200, "application/json", raw, {}), clock=lambda: NOW)
        assert run(catalog_engine, job, handler) == "retry_wait"
        with Session(catalog_engine) as session:
            for table in (documents, document_revisions, text_blocks, evidence, fetch_attempts, source_page_receipts, source_cursors):
                assert session.scalar(select(func.count()).select_from(table)) == 0
            receipt = session.execute(select(source_response_receipts)).mappings().one()
            assert receipt["response_content_hash"] == hashlib.sha256(raw).hexdigest()
            assert receipt["response_size_bytes"] == len(raw)
            assert receipt["parse_outcome"] == "normalized"
            assert session.scalar(select(job_runs.c.error_code).where(job_runs.c.job_id == job)) == "database_operation_failed"
        assert store.read_verified(hashlib.sha256(raw).hexdigest()) == raw
    finally:
        event.remove(catalog_engine, "before_cursor_execute", fail_second_evidence)


def test_two_real_source_writers_keep_only_updated_claims_current(catalog_engine, tmp_path, monkeypatch):
    from datetime import timedelta
    from ai_intel.ingestion import source_documents
    from ai_intel.knowledge.persistence_models import claims, event_documents

    store = ContentStore(tmp_path)
    held, updater_ready, release = threading.Event(), threading.Event(), threading.Event()
    local = threading.local()
    pids = {}
    original = source_documents.register_source_revision_blocks

    def pause_after_real_bulk(*args, **kwargs):
        result = original(*args, **kwargs)
        if getattr(local, "first_writer", False):
            held.set()
            assert release.wait(10)
        return result

    monkeypatch.setattr(source_documents, "register_source_revision_blocks", pause_after_real_bulk)

    def write_source(first):
        local.first_writer = first
        if not first:
            assert held.wait(10)
        record = vendor_record()
        if not first:
            record["description"] = "Independent fixture source correction retained in its exact quote."
        response = vendor_response(record, NOW if first else NOW + timedelta(seconds=60))
        with Session(catalog_engine) as session, session.begin():
            pids["first" if first else "updater"] = session.scalar(text("SELECT pg_backend_pid()"))
            if not first:
                updater_ready.set()
            return source_documents.persist_source_response(session, store, ADMIN, response, ingested_at=response.observed_at + timedelta(seconds=1))

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(write_source, True), pool.submit(write_source, False)
        try:
            assert updater_ready.wait(10)
            observed = False
            deadline = time.perf_counter() + 5
            while time.perf_counter() < deadline:
                with catalog_engine.connect() as connection:
                    blocking = connection.scalar(text("SELECT pg_blocking_pids(:pid)"), {"pid": pids["updater"]})
                if pids["first"] in blocking:
                    observed = True
                    break
                time.sleep(0.02)
            assert observed and not second.done()
        finally:
            release.set()
        saved_first, saved_second = first.result(timeout=10), second.result(timeout=10)
    assert saved_first.new_revision_count == saved_second.new_revision_count == 1
    assert saved_first.event_ids == saved_second.event_ids
    with Session(catalog_engine) as session:
        assert session.scalar(select(func.count()).select_from(document_revisions)) == 2
        assert session.scalar(select(func.count()).select_from(claims).where(claims.c.source_revision_id == saved_first.revision_ids[0], claims.c.is_current.is_(True))) == 0
        assert session.scalar(select(func.count()).select_from(claims).where(claims.c.source_revision_id == saved_second.revision_ids[0], claims.c.is_current.is_(True))) == 2
        assert session.scalar(select(func.count()).select_from(evidence).where(evidence.c.revision_id == saved_first.revision_ids[0])) == 2
        assert session.scalar(select(event_documents.c.active).where(event_documents.c.revision_id == saved_first.revision_ids[0])) is False
