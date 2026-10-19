"""Independent contract-update probes; the original 19 probes stay unchanged next to this file."""

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend/tests/integration"))
pytest_plugins = ["tests.conftest"]

from test_r04_knowledge_api_pg import clients as clients
from test_r06_source_worker_pg import NOW, queue, run
from test_r06_source_worker_pg import catalog_worker_engine as catalog_worker_engine
from tests.r06_source_worker_fixtures import source_response

from ai_intel.domain.access import Role
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.network import FetchResult
from ai_intel.ingestion.catalog_pages import normalize_catalog_page
from ai_intel.ingestion.source_catalog import SourceCatalogError, parse_source_timestamp
from ai_intel.ingestion.source_jobs import build_source_page_handler

TIMESTAMPS = ("2026-10-15T01:02:03-00:00", "2026-10-15T01:02:03.1234567Z",
              "2026-10-15T01:02:03.123456789Z")


@pytest.fixture
def api_engine(catalog_worker_engine):
    return catalog_worker_engine


def policy_missing_body_before_chapter(ordinal):
    text = (ROOT / "fixtures/recorded/cac_generative_ai_20261015_public.html").read_text(encoding="utf-8")
    article = re.search(r"<strong>第" + ordinal + r"条</strong>", text)
    assert article is not None
    chapter = re.search(r"<p\b[^>]*>\s*<strong>第[一二三四五六七八九十]+章", text[article.end():])
    assert chapter is not None
    chapter_start = article.end() + chapter.start()
    following_article = re.search(r"<strong>第[一二三四五六七八九十]+条</strong>", text[article.end():chapter_start])
    assert following_article is None, "the selected article must be immediately before a chapter"
    changed = text[:article.end()] + "</p>" + text[chapter_start:]
    return changed.encode()


@pytest.mark.parametrize("ordinal", ["四", "八", "十五", "二十一"])
def test_chapter_title_is_not_the_missing_body_of_the_preceding_policy_article(ordinal):
    with pytest.raises(SourceCatalogError):
        normalize_catalog_page("cac_generative_ai", policy_missing_body_before_chapter(ordinal), {})


@pytest.mark.parametrize("timestamp", TIMESTAMPS)
def test_legal_unknown_timestamp_is_kept_raw_with_unknown_precision(timestamp):
    source = json.loads(source_response("osv_ollama")[0])
    source["vulns"][0]["published"] = timestamp
    document = normalize_catalog_page("osv_ollama", json.dumps(source).encode(), {}).documents[0]
    assert parse_source_timestamp(timestamp) is None
    assert document.published_at is None
    assert document.metadata["published_precision"] == "unknown"
    assert document.metadata["published_at_raw"] == timestamp
    assert json.loads(document.payload)["published"] == timestamp
    assert document.metadata["source_adapter_version"] == "catalog-pages-2"
    assert any("精度" in note for note in document.metadata["source_notes"])


@pytest.mark.parametrize("value", ["2024-02-30T00:00:00Z", "2024-01-01T00:00:00+00:99",
    "2024-01-01T00:00:00+24:00", "２０２４-01-01T00:00:00Z", "2024-01-01T00:00:00+00:00:10"])
def test_invalid_calendar_offset_ascii_or_seconds_are_rejected(value):
    with pytest.raises(SourceCatalogError):
        parse_source_timestamp(value)


@pytest.mark.real_pg
def test_missing_body_before_chapter_rolls_back_document_and_cursor(catalog_worker_engine, tmp_path):
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session
    from ai_intel.knowledge.models import documents, document_revisions, source_cursors, source_page_receipts

    raw = policy_missing_body_before_chapter("八")
    handler = build_source_page_handler(ContentStore(tmp_path), clock=lambda: NOW,
        fetcher=lambda url: FetchResult(url, 200, "text/html", raw))
    job_id = queue(catalog_worker_engine, "cac_generative_ai")
    outcome = run(catalog_worker_engine, job_id, handler)
    with Session(catalog_worker_engine) as session:
        counts = {table.name: session.scalar(select(func.count()).select_from(table))
                  for table in (documents, document_revisions, source_cursors, source_page_receipts)}
    assert {"outcome": outcome, **counts} == {"outcome": "blocked", "documents": 0,
        "document_revisions": 0, "source_cursors": 0, "source_page_receipts": 0}


@pytest.mark.real_pg
@pytest.mark.parametrize("kind", ["osv_ollama", "ollama_releases"])
@pytest.mark.parametrize("timestamp", TIMESTAMPS)
def test_raw_preserved_null_precision_is_visible_through_authenticated_http(api_engine, clients, tmp_path, kind, timestamp):
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from ai_intel.knowledge.models import document_revisions, fetch_attempts

    source = json.loads(source_response(kind)[0])
    record = source["vulns"][0] if kind == "osv_ollama" else source[0]
    field = "published" if kind == "osv_ollama" else "published_at"
    record[field] = timestamp
    original_modified = record.get("modified")
    raw = json.dumps(source, indent=2).encode()
    store = ContentStore(tmp_path)
    handler = build_source_page_handler(store, clock=lambda: NOW,
        fetcher=lambda url: FetchResult(url, 200, "application/json", raw),
        poster=lambda url, body: FetchResult(url, 200, "application/json", raw))
    job_id = queue(api_engine, kind)
    assert run(api_engine, job_id, handler) == "succeeded"
    with Session(api_engine) as session:
        revision = session.execute(select(document_revisions)).mappings().one()
        assert revision["source_published_at"] is None
        assert revision["source_metadata"]["published_at_raw"] == timestamp
        assert revision["source_metadata"]["published_precision"] == "unknown"
        assert revision["source_metadata"]["source_adapter_version"] == "catalog-pages-2"
        assert revision["source_response_hash"] == hashlib.sha256(raw).hexdigest()
        assert revision["content_hash"] != revision["source_response_hash"]
        assert store.read_verified(revision["source_response_hash"]) == raw
        assert json.loads(store.read_verified(revision["content_hash"]))[field] == timestamp
        assert session.scalar(select(fetch_attempts.c.response_content_hash)) == revision["source_response_hash"]
        if kind == "osv_ollama":
            assert original_modified == "2026-09-10T03:49:48.487641080Z"
            assert revision["source_modified_at"] is None
            assert revision["source_metadata"]["modified_at_raw"] == original_modified
            assert json.loads(store.read_verified(revision["content_hash"]))["modified"] == original_modified
    client = clients[0](Role.SYSTEM_ADMIN, None)
    response = client.get("/v1/documents/" + revision["document_id"])
    assert response.status_code == 200, response.text
    item = response.json()["document"]
    assert item["source_published_at"] is None and item["published_precision"] == "unknown"
    assert item["published_at_raw"] == timestamp
    assert any("精度" in note for note in response.json()["source_notes"])
    assert client.get("/api/v1/documents/" + revision["document_id"]).json() == response.json()
