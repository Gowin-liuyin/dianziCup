"""Real isolated PG verifies policy rollback and raw-preserving unknown timestamp projection."""

import json
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_r06_catalog_documents_pg import ADMIN
from test_r06_source_worker_pg import NOW, queue, run
from test_r06_source_worker_pg import catalog_worker_engine as catalog_worker_engine
from tests.r06_source_worker_fixtures import policy_without_article_body, source_response

from ai_intel.api.document_read_service import DocumentReadService
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.network import FetchResult
from ai_intel.ingestion.source_jobs import build_source_page_handler
from ai_intel.knowledge.models import (
    document_revisions,
    documents,
    source_cursors,
    source_page_receipts,
)

pytestmark = pytest.mark.real_pg
ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("kind", ["cac_generative_ai", "cac_missing_article", "osv_ollama"])
def test_bad_source_content_cannot_commit_document_or_cursor(catalog_worker_engine, tmp_path, kind):
    if kind == "cac_missing_article":
        kind = "cac_generative_ai"
        body, media = policy_without_article_body("八"), "text/html"
    elif kind == "cac_generative_ai":
        original = (ROOT / "fixtures/recorded/cac_generative_ai_20261015_public.html").read_bytes()
        body = original.replace("本办法自2023年8月15日起施行。".encode(), b"")
        media = "text/html"
    else:
        source = json.loads(source_response(kind)[0])
        source["vulns"][0]["published"] = "2024-01-01T00:00:00+00:99"
        body, media = json.dumps(source).encode(), "application/json"
    handler = build_source_page_handler(
        ContentStore(tmp_path),
        clock=lambda: NOW,
        fetcher=lambda url: FetchResult(url, 200, media, body),
        poster=lambda url, payload: FetchResult(url, 200, media, body),
    )
    identifier = queue(catalog_worker_engine, kind)
    assert run(catalog_worker_engine, identifier, handler) == "blocked"
    with Session(catalog_worker_engine) as session:
        assert all(
            session.scalar(select(func.count()).select_from(table)) == 0
            for table in (documents, document_revisions, source_cursors, source_page_receipts)
        )


@pytest.mark.parametrize(
    "timestamp",
    ["2024-01-01T00:00:00-00:00", "2024-01-01T00:00:00.1234567Z", "2024-01-01T00:00:00.123456789Z"],
)
def test_legal_unknown_source_time_has_null_instant_and_visible_raw_precision(
    catalog_worker_engine, tmp_path, timestamp
):
    source = json.loads(source_response("osv_ollama")[0])
    source["vulns"][0]["published"] = timestamp
    body = json.dumps(source).encode()
    store = ContentStore(tmp_path)
    handler = build_source_page_handler(
        store,
        clock=lambda: NOW,
        poster=lambda url, payload: FetchResult(url, 200, "application/json", body),
    )
    identifier = queue(catalog_worker_engine, "osv_ollama")
    assert run(catalog_worker_engine, identifier, handler) == "succeeded"
    with Session(catalog_worker_engine) as session:
        revision = session.execute(select(document_revisions)).mappings().one()
        assert revision["source_published_at"] is None
        assert revision["source_metadata"]["published_precision"] == "unknown"
        assert revision["source_metadata"]["published_at_raw"] == timestamp
        detail = DocumentReadService(session, ADMIN, "fixture").document_detail(
            UUID(revision["document_id"])
        )
        assert detail.document.source_published_at is None
        assert detail.document.published_precision == "unknown"
        assert detail.document.published_at_raw == timestamp
        assert json.loads(store.read_verified(revision["content_hash"]))["published"] == timestamp
