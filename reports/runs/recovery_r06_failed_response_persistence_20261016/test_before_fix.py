"""Run the durable-evidence assertion against the untouched c3 source files."""

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.test_r06_catalog_documents_pg import catalog_engine as _catalog_fixture

from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.network import FetchResult
from ai_intel.ingestion.source_jobs import SOURCE_JOB_TYPE, SourcePageRequest, build_source_page_handler, enqueue_source_page
from ai_intel.knowledge.models import content_objects
from ai_intel.workers.executor import execute_job

catalog_engine = _catalog_fixture
pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 16, tzinfo=UTC)


@pytest.mark.parametrize(("kind", "media", "body"), [
    ("arxiv_security", "application/atom+xml", b"<feed>"),
    ("ollama_releases", "application/json", b"[{"),
    ("osv_ollama", "application/json", b'{"vulns":[1]}'),
])
def test_failure_raw_bytes_must_have_durable_pg_reference(catalog_engine, tmp_path, kind, media, body):
    with Session(catalog_engine) as session, session.begin():
        job_id = enqueue_source_page(session, SourcePageRequest(source_kind=kind, window_end=NOW - timedelta(seconds=1)), NOW)
    handler = build_source_page_handler(ContentStore(tmp_path / "raw"), fetcher=lambda url: FetchResult(url, 200, media, body), poster=lambda url, request_body: FetchResult(url, 200, media, body), clock=lambda: NOW)
    assert execute_job(catalog_engine, job_id, "red-fixture-worker", {SOURCE_JOB_TYPE: handler}, clock=lambda: NOW) == "blocked"
    with Session(catalog_engine) as session:
        assert session.scalar(select(content_objects.c.content_hash).where(content_objects.c.content_hash == hashlib.sha256(body).hexdigest())) == hashlib.sha256(body).hexdigest()
