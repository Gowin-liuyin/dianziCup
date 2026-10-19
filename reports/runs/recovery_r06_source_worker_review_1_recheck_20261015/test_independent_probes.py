"""Independent recorded-input and adversarial checks for the frozen catalog boundary."""

import base64
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend/tests/integration"))
pytest_plugins = ["tests.conftest"]

from test_r06_source_worker_pg import catalog_worker_engine as catalog_worker_engine

from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.models.json_output import strict_json_object
from ai_intel.infrastructure.network import FetchResult
from ai_intel.ingestion.catalog_pages import normalize_catalog_page, select_avid_blob
from ai_intel.ingestion.source_catalog import SourceCatalogError
from ai_intel.ingestion.source_jobs import build_source_page_handler
from ai_intel.ingestion.sources.osv import OsvContractError


def policy_bytes():
    return (ROOT / "fixtures/recorded/cac_generative_ai_20261015_public.html").read_bytes()


def osv_record():
    return json.loads((ROOT / "reports/runs/recovery_r06_repository_community_20261015/osv_ollama_real.body").read_bytes())


def test_actual_policy_has_all_articles_and_exact_last_body():
    body = policy_bytes()
    assert hashlib.sha256(body).hexdigest() == "7fae988c064dde72c95e96e5727bf9abee4b3a5a1ea817606a9ca1f97ffac54b"
    document = normalize_catalog_page("cac_generative_ai", body, {}).documents[0]
    headings = [block.text for block in document.parsed.blocks if re.fullmatch(r"第[一二三四五六七八九十]+条", block.text)]
    assert len(headings) == 24 and headings[-1] == "第二十四条"
    last_index = document.parsed.normalized_text.index("第二十四条")
    assert "本办法自2023年8月15日起施行。" in document.parsed.normalized_text[last_index:]
    assert document.published_at is None


def missing_last_policy_body():
    body = policy_bytes()
    clause = "本办法自2023年8月15日起施行。".encode()
    assert body.count(clause) == 1
    changed = body.replace(clause, b"")
    assert "第二十四条".encode() in changed
    return changed


def test_policy_with_last_heading_but_no_last_body_is_not_full_text():
    with pytest.raises(SourceCatalogError):
        normalize_catalog_page("cac_generative_ai", missing_last_policy_body(), {})


@pytest.mark.parametrize("timestamp", ["2026-10-15T01:02:03-00:00", "2026-10-15T01:02:03+00:99", "2026-10-15T01:02:03.1234567Z"])
def test_osv_invalid_or_unknown_offset_is_not_promoted_to_precise_utc(timestamp):
    record = osv_record()
    record["published"] = timestamp
    with pytest.raises((SourceCatalogError, OsvContractError)):
        normalize_catalog_page("osv_ollama", json.dumps({"vulns": [record]}).encode(), {})


@pytest.mark.parametrize("body", [b'{"vulns":null}', b'{"vulns":[],"next_page_token":null}', b'{"vulns":[],"next_page_token":"again"}'])
def test_osv_null_records_or_nonadvancing_empty_token_page_is_rejected(body):
    if body == b'{"vulns":[],"next_page_token":null}':
        assert normalize_catalog_page("osv_ollama", body, {}).documents == ()
    else:
        with pytest.raises(SourceCatalogError):
            normalize_catalog_page("osv_ollama", body, {})


def test_implicit_empty_osv_query_is_recorded_as_empty_page():
    page = normalize_catalog_page("osv_ollama", b"{}", {})
    assert page.documents == () and page.next_cursor == {}


@pytest.mark.parametrize("body", [b'{"vulns":[],"vulns":[]}', b'{"vulns":[],"field":NaN}'])
def test_osv_strict_json_rules_are_not_relaxed_by_larger_source_budget(body):
    with pytest.raises(ValueError):
        normalize_catalog_page("osv_ollama", body, {})


def test_source_json_limit_stops_at_50000_while_model_default_stays_10000():
    body = json.dumps({"items": list(range(10000))}).encode()
    with pytest.raises(ValueError):
        strict_json_object(body)
    assert len(strict_json_object(body, maximum_nodes=50000)["items"]) == 10000
    with pytest.raises(ValueError):
        strict_json_object(json.dumps({"items": list(range(50000))}), maximum_nodes=50000)


def test_actual_avid_directory_is_bounded_and_pins_only_vulnerability_path():
    body = (RUN / "avid_tree_public.body").read_bytes()
    assert hashlib.sha256(body).hexdigest() == "0c04c3689ee1cd32714083b8e066c8f10c06439ebd2b0c7a10b9a2c4ecb4b5e5"
    selection = select_avid_blob(body, {})
    assert selection.tree_sha == "8eda5f4e6f74a3738eb980b795c4f813c6e52ca8"
    assert selection.path.startswith("vulnerabilities/")
    assert selection.next_cursor["tree_sha"] == selection.tree_sha
    with pytest.raises(SourceCatalogError):
        select_avid_blob(body, {"tree_sha": "a" * 40, "record_offset": 0})


def test_actual_nist_pdf_preserves_48_page_text_coordinates_and_bytes():
    body = (RUN / "nist_ai_rmf.body").read_bytes()
    assert hashlib.sha256(body).hexdigest() == "7576edb531d9848825814ee88e28b1795d3a84b435b4b797d3670eafdc4a89f1"
    document = normalize_catalog_page("nist_ai_rmf", body, {}).documents[0]
    assert document.payload == body and document.published_at is None
    assert {block.page_number for block in document.parsed.blocks} == set(range(1, 49))
    assert "NIST" in document.parsed.normalized_text and "January 2023" in document.parsed.normalized_text
    assert document.metadata["published_precision"] == "unknown"


@pytest.mark.real_pg
def test_worker_does_not_commit_policy_when_last_article_body_is_missing(catalog_worker_engine, tmp_path):
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session
    from test_r06_source_worker_pg import queue, run, NOW
    from ai_intel.knowledge.models import documents, document_revisions, source_cursors, source_page_receipts

    job_id = queue(catalog_worker_engine, "cac_generative_ai")
    handler = build_source_page_handler(ContentStore(tmp_path), clock=lambda: NOW,
        fetcher=lambda url: FetchResult(url, 200, "text/html", missing_last_policy_body()))
    outcome = run(catalog_worker_engine, job_id, handler)
    with Session(catalog_worker_engine) as session:
        actual = {table.name: session.scalar(select(func.count()).select_from(table))
                  for table in (documents, document_revisions, source_cursors, source_page_receipts)}
    assert {"outcome": outcome, **actual} == {"outcome": "blocked", "documents": 0,
        "document_revisions": 0, "source_cursors": 0, "source_page_receipts": 0}


@pytest.mark.real_pg
def test_derived_osv_payload_and_original_response_keep_distinct_verified_hashes(catalog_worker_engine, tmp_path):
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from test_r06_source_worker_pg import queue, run, NOW
    from ai_intel.knowledge.models import document_revisions, fetch_attempts

    raw = json.dumps({"vulns": [osv_record()]}, indent=2).encode()
    store = ContentStore(tmp_path)
    handler = build_source_page_handler(store, clock=lambda: NOW,
        poster=lambda url, payload: FetchResult(url, 200, "application/json", raw))
    job_id = queue(catalog_worker_engine, "osv_ollama")
    assert run(catalog_worker_engine, job_id, handler) == "succeeded"
    with Session(catalog_worker_engine) as session:
        revision = session.execute(select(document_revisions)).mappings().one()
        response_hash = hashlib.sha256(raw).hexdigest()
        assert revision["source_response_hash"] == response_hash
        assert revision["content_hash"] != response_hash
        assert store.read_verified(response_hash) == raw
        assert json.loads(store.read_verified(revision["content_hash"])) == osv_record()
        assert session.scalar(select(fetch_attempts.c.response_content_hash)) == response_hash


@pytest.mark.real_pg
@pytest.mark.parametrize("timestamp", ["2026-10-15T01:02:03-00:00", "2026-10-15T01:02:03+00:99", "2026-10-15T01:02:03.1234567Z"])
def test_worker_does_not_commit_invalid_or_unknown_osv_source_timestamp(catalog_worker_engine, tmp_path, timestamp):
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from test_r06_source_worker_pg import queue, run, NOW
    from ai_intel.knowledge.models import document_revisions, source_cursors

    record = osv_record()
    record["published"] = timestamp
    raw = json.dumps({"vulns": [record]}).encode()
    handler = build_source_page_handler(ContentStore(tmp_path), clock=lambda: NOW,
        poster=lambda url, payload: FetchResult(url, 200, "application/json", raw))
    job_id = queue(catalog_worker_engine, "osv_ollama")
    outcome = run(catalog_worker_engine, job_id, handler)
    with Session(catalog_worker_engine) as session:
        row = session.execute(select(document_revisions)).mappings().first()
        actual_utc = row["source_published_at"].isoformat() if row else None
        cursor = session.scalar(select(source_cursors.c.cursor_json))
    assert {"outcome": outcome, "actual_utc": actual_utc, "cursor": cursor} == {
        "outcome": "blocked", "actual_utc": None, "cursor": None}
