"""Reviewer-only real PG checks use the actual source handler, immutable content and REST."""

import base64
import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
sys.path.insert(0, str(ROOT / "backend/tests/integration"))
from test_r06_source_worker_pg import catalog_worker_engine as catalog_worker_engine
from test_r04_knowledge_api_pg import clients as clients
from test_offline_inputs import HEADERS, PIN, official_bytes

from ai_intel.domain.access import AccessScope, Role
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.network import FetchResult
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.ingestion import source_jobs
from ai_intel.ingestion.catalog_pages import select_avid_blob
from ai_intel.ingestion.source_catalog import CATALOG_SOURCES
from ai_intel.ingestion.source_documents import ensure_source_registration
from ai_intel.ingestion.source_jobs import SOURCE_JOB_TYPE, SourcePageRequest, build_source_page_handler, enqueue_source_page
from ai_intel.knowledge.models import content_objects, document_revisions, documents, evidence, fetch_attempts, job_runs, source_cursors, source_page_receipts, text_blocks
from ai_intel.knowledge.persistence_models import events
from ai_intel.workers.executor import execute_job

NOW = datetime(2026, 10, 15, 14, tzinfo=UTC)
ADMIN = AccessScope.for_authenticated_user("review-worker", None, Role.SYSTEM_ADMIN)
BUSINESS = (documents, document_revisions, evidence, text_blocks, content_objects, fetch_attempts, source_page_receipts)


@pytest.fixture
def api_engine(catalog_worker_engine):
    return catalog_worker_engine


def queue(engine, kind, at=NOW):
    with Session(engine) as session, session.begin():
        return enqueue_source_page(session, SourcePageRequest(source_kind=kind, window_end=at - timedelta(seconds=1), remaining_pages=1), at)


def execute(engine, job_id, store, fetcher, at=NOW):
    handler = build_source_page_handler(store, fetcher=fetcher, clock=lambda: at)
    def observed_handler(session, context, payload):
        try:
            return handler(session, context, payload)
        except Exception as error:
            diagnostic = {"exception_type": type(error).__name__, "error_code": getattr(error, "error_code", None)}
            if type(error).__name__ in {"CursorCommitError", "SourceLeaseLostError", "StaleSourceCursorError"}:
                diagnostic["safe_message"] = str(error)
            origin = getattr(error, "orig", None)
            if origin is not None:
                diagnostic["database_error_code"] = getattr(origin, "sqlstate", None)
                diagnostic["database_primary_message"] = getattr(getattr(origin, "diag", None), "message_primary", None)
            record("exception_" + json.loads(payload)["source_kind"] + "_" + job_id, diagnostic)
            raise
    return execute_job(engine, job_id, "independent-review-worker", {SOURCE_JOB_TYPE: observed_handler}, clock=lambda: at)


def counts(engine):
    with Session(engine) as session:
        return {table.name: session.scalar(select(func.count()).select_from(table)) for table in BUSINESS}


def assert_evidence(engine):
    with Session(engine) as session:
        rows = session.execute(select(evidence, text_blocks.c.block_text, text_blocks.c.start_offset.label("block_start"))
            .join(text_blocks, evidence.c.block_id == text_blocks.c.block_id)).mappings().all()
        assert rows
        for row in rows:
            assert row["block_text"][row["start_offset"] - row["block_start"]: row["end_offset"] - row["block_start"]] == row["quote"]
            assert hashlib.sha256(row["quote"].encode()).hexdigest() == row["quote_sha256"]
            assert row["supports_claim"] is False
        assert session.scalar(select(func.count()).select_from(events)) == 0


def record(label, result):
    (RUN / (label + "_observation.json")).write_text(json.dumps(result, indent=2), encoding="utf-8")


def avid_snapshot(payload=None):
    original = json.loads(official_bytes("avid"))
    decoded = base64.b64decode(original["content"]) if payload is None else payload
    digest = hashlib.sha1(b"blob " + str(len(decoded)).encode() + b"\0" + decoded).hexdigest()
    envelope = official_bytes("avid") if payload is None else json.dumps({"sha": digest, "encoding": "base64", "size": len(decoded), "content": base64.b64encode(decoded).decode()}).encode()
    identifier = json.loads(decoded)["metadata"]["vuln_id"]
    path = "vulnerabilities/" + identifier[5:9] + "/" + identifier + ".json"
    tree = json.dumps({"sha": "a" * 40, "truncated": False, "tree": [{"path": path, "sha": digest, "size": len(decoded), "type": "blob"}]}).encode()
    return tree, envelope, decoded


@pytest.mark.parametrize("kind", ["ollama_releases", "avid_community"])
def test_actual_saved_responses_commit_raw_revision_evidence_cursor_and_rest(catalog_worker_engine, tmp_path, clients, kind):
    engine = catalog_worker_engine
    store = ContentStore(tmp_path)
    seen = []
    if kind == "avid_community":
        tree, body = official_bytes("tree"), official_bytes("avid")
        selected = select_avid_blob(tree, PIN)
        with Session(engine) as session, session.begin():
            ensure_source_registration(session, ADMIN, kind, NOW)
            session.execute(source_cursors.insert().values(source_id=CATALOG_SOURCES[kind].source_id, stream_kind="backfill", cursor_json={"position": PIN, "window_complete": False,
                "pending_watermark_published_at": None, "recovery_tracking_version": 1, "pending_recovery_job_ids": []},
                window_end=NOW - timedelta(seconds=1), last_successful_page=1, generation=0, updated_at=NOW))
        expected = 1
    else:
        body = official_bytes("release")
        expected = 20

    def fetch(url):
        seen.append(url)
        if kind == "avid_community":
            return FetchResult(url, 200, "application/json", body if "/git/blobs/" in url else tree)
        return FetchResult(url, 200, "application/json", body, HEADERS)

    identifier = queue(engine, kind)
    assert execute(engine, identifier, store, fetch) == "partial"
    before = counts(engine)
    assert execute(engine, identifier, store, fetch) == "not_claimed"
    assert counts(engine) == before
    assert len(seen) == (2 if kind == "avid_community" else 1)
    assert all("/img/" not in url for url in seen)
    if kind == "avid_community":
        assert seen[0].endswith(PIN["tree_sha"] + "?recursive=1")
        assert seen[1].endswith(selected.blob_sha)
    assert before["documents"] == before["document_revisions"] == expected
    assert_evidence(engine)
    with Session(engine) as session:
        state = session.scalar(select(source_cursors.c.cursor_json))
        assert state["position"] == (selected.next_cursor if kind == "avid_community" else {"page": 2})
        assert state["window_complete"] is False
        assert session.scalar(select(func.count()).select_from(source_page_receipts)) == 1
        attempts = session.execute(select(fetch_attempts)).mappings().all()
        for attempt in attempts:
            raw = store.read_verified(attempt["response_content_hash"])
            assert raw in ([tree, body] if kind == "avid_community" else [body])
        revisions = session.execute(select(document_revisions)).mappings().all()
        assert all(row["source_response_hash"] == hashlib.sha256(body).hexdigest() for row in revisions)
        if kind == "avid_community":
            assert store.read_verified(revisions[0]["content_hash"]) == base64.b64decode(json.loads(body)["content"])
            assert revisions[0]["source_metadata"]["git_tree_sha"] == PIN["tree_sha"]
        else:
            assert {json.loads(store.read_verified(row["content_hash"]))["id"] for row in revisions} == {x["id"] for x in json.loads(body)}
        document_id = revisions[0]["document_id"]
        revision_id = revisions[0]["revision_id"]
    client = clients[0](Role.VIEWER, "tenant-a")
    for prefix in ("/v1", "/api/v1"):
        detail = client.get(prefix + "/documents/" + document_id)
        assert detail.status_code == 200
        assert detail.json()["document"]["revision_id"] == revision_id
        assert detail.json()["evidence_total"] > 0
        assert detail.json()["data_mode"] == "fixture"
        if kind == "avid_community":
            assert any("未获取或读取图片" in x for x in detail.json()["source_notes"])
    rejected = client.post("/v1/sources/" + kind + "/collect", json={"window_end": "2026-10-15T00:00:00Z", "max_pages": 1},
        headers={"Origin": "http://localhost:5173", "x-csrf-token": client.get("/v1/auth/csrf").json()["csrf_token"], "Idempotency-Key": "review-denied"})
    assert rejected.status_code == 403
    with engine.begin() as connection:
        connection.execute(update(document_revisions).where(document_revisions.c.revision_id == revision_id).values(visibility="tenant", tenant_id="tenant-b"))
    assert client.get("/v1/documents/" + document_id).status_code == 404
    record(kind + "_actual_handler", {"counts": before, "cursor": state, "requests": len(seen), "screenshot_requests": 0,
        "same_job_replay": "not_claimed", "rest_both_prefixes": 200, "viewer_collect": 403, "foreign_revision": 404})


@pytest.mark.parametrize("kind", ["ollama_releases", "avid_community"])
def test_handler_replay_and_a_b_a_keep_immutable_history(catalog_worker_engine, tmp_path, kind):
    engine = catalog_worker_engine
    store = ContentStore(tmp_path)
    release = json.loads(official_bytes("release"))[0]
    tree, blob, avid = avid_snapshot()
    current = [NOW]
    payloads = []
    initial_state = None
    for index in range(4):
        if kind == "ollama_releases":
            item = dict(release)
            if index == 2:
                item["body"] = (item["body"] or "") + "\nReviewer synthetic revision B"
            body = json.dumps([item]).encode()
            member_payload = json.dumps(item, ensure_ascii=False, separators=(",", ":")).encode()
            def fetch(url):
                return FetchResult(url, 200, "application/json", body)
        else:
            if index == 2:
                item = json.loads(avid)
                item["description"]["value"] += "\nReviewer synthetic revision B"
                tree, blob, member_payload = avid_snapshot(json.dumps(item).encode())
            else:
                tree, blob, member_payload = avid_snapshot()
            def fetch(url):
                return FetchResult(url, 200, "application/json", blob if "/git/blobs/" in url else tree)
        payloads.append(member_payload)
        identifier = queue(engine, kind, current[0])
        assert execute(engine, identifier, store, fetch, current[0]) == "succeeded"
        assert execute(engine, identifier, store, fetch, current[0]) == "not_claimed"
        assert counts(engine)["document_revisions"] == [1, 1, 2, 3][index]
        current[0] += timedelta(seconds=8)
    assert_evidence(engine)
    with Session(engine) as session:
        history = session.execute(select(document_revisions).order_by(document_revisions.c.revision_number)).mappings().all()
        assert [row["revision_number"] for row in history] == [1, 2, 3]
        assert [row["is_current"] for row in history] == [False, False, True]
        assert history[1]["previous_revision_id"] == history[0]["revision_id"]
        assert history[2]["previous_revision_id"] == history[1]["revision_id"]
        assert [store.read_verified(row["content_hash"]) for row in history] == [payloads[0], payloads[2], payloads[3]]
        assert history[0]["content_hash"] == history[2]["content_hash"]
        assert session.scalar(select(func.count()).select_from(source_page_receipts)) == 4
        assert session.scalar(select(source_cursors.c.cursor_json))["window_complete"] is True
    record(kind + "_history", {"revisions": 3, "receipt_count": 4, "a_b_a_hash_equal": True, "same_latest_reuses_revision": True})


@pytest.mark.parametrize("kind", ["ollama_releases", "avid_community"])
@pytest.mark.parametrize("failure", ["invalid_input", "after_documents", "cursor_commit"])
def test_handler_failure_does_not_advance_cursor_or_leave_pg_writes(catalog_worker_engine, tmp_path, monkeypatch, kind, failure):
    engine = catalog_worker_engine
    store = ContentStore(tmp_path)
    tree, blob, avid = avid_snapshot()
    release = json.loads(official_bytes("release"))[0]
    if failure == "invalid_input":
        if kind == "avid_community":
            item = json.loads(avid)
            next(x for x in item["references"] if x["type"] == "screenshot")["url"] = "../../img/R00031.png"
            tree, blob, _ = avid_snapshot(json.dumps(item).encode())
        else:
            release["padding"] = [0] * 50001
    body = json.dumps([release]).encode()
    def fetch(url):
        if kind == "avid_community":
            return FetchResult(url, 200, "application/json", blob if "/git/blobs/" in url else tree)
        return FetchResult(url, 200, "application/json", body)
    if failure == "after_documents":
        original = source_jobs.persist_catalog_documents
        def reject(*args, **kwargs):
            original(*args, **kwargs)
            raise OSError("review injected transaction failure")
        monkeypatch.setattr(source_jobs, "persist_catalog_documents", reject)
    if failure == "cursor_commit":
        def reject(*args, **kwargs):
            raise OSError("review injected cursor failure")
        monkeypatch.setattr(source_jobs.SourceCursorRepository, "commit_page", reject)
    identifier = queue(engine, kind)
    assert execute(engine, identifier, store, fetch) == ("blocked" if failure == "invalid_input" else "retry_wait")
    assert all(value == 0 for value in counts(engine).values())
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(source_cursors)) == 0
        assert session.scalar(select(job_runs.c.error_code)) == ("source_response_invalid" if failure == "invalid_input" else "handler_failed")


@pytest.mark.parametrize("kind", ["ollama_releases", "avid_community"])
def test_tenant_job_cannot_invoke_public_source_handler(catalog_worker_engine, tmp_path, kind):
    engine = catalog_worker_engine
    request = SourcePageRequest(source_kind=kind, window_end=NOW - timedelta(seconds=1), remaining_pages=1)
    with Session(engine) as session, session.begin():
        identifier = enqueue_job(session, "tenant-a", SOURCE_JOB_TYPE, request.model_dump_json().encode(), NOW, idempotency_key="review-tenant-job")
    def rejected_fetch(url):
        pytest.fail("tenant scoped job attempted external read")
    assert execute(engine, identifier, ContentStore(tmp_path), rejected_fetch) == "blocked"
    assert all(value == 0 for value in counts(engine).values())
    with Session(engine) as session:
        assert session.scalar(select(job_runs.c.error_code)) == "source_scope_denied"


def test_uuid_search_paths_share_postgres_advisory_lock_namespace(catalog_worker_engine):
    from sqlalchemy import text
    key = "source:" + CATALOG_SOURCES["ollama_releases"].source_id
    with catalog_worker_engine.connect() as first, catalog_worker_engine.connect() as second:
        with first.begin(), second.begin():
            first_path = first.scalar(text("SHOW search_path"))
            second.execute(text("SET LOCAL search_path=pg_catalog"))
            second_path = second.scalar(text("SHOW search_path"))
            assert first_path != second_path
            first.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {"key": key})
            assert second.scalar(text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key,0))"), {"key": key}) is False
    record("shared_advisory_lock_namespace", {"same_database": True, "distinct_search_paths": True,
           "second_try_lock": False, "product_change": False, "scope": "review harness concurrency; source lock is intentionally database scoped"})
