"""Nine-source worker wiring in real UUID-isolated PG with offline source responses."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema
from tests.r06_source_worker_fixtures import avid_responses, avid_second_blob, source_response

from ai_intel.domain.access import AccessScope, Role
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.network import FetchResult, NetworkTimeoutError
from ai_intel.ingestion import source_jobs
from ai_intel.ingestion.source_catalog import CATALOG_SOURCES
from ai_intel.ingestion.source_documents import ensure_source_registration
from ai_intel.ingestion.source_failure_models import source_response_receipts
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
    outbox_events,
    source_cursors,
    source_page_receipts,
    text_blocks,
)
from ai_intel.knowledge.persistence_models import claims, events
from ai_intel.workers.executor import execute_job

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 15, 10, tzinfo=UTC)


@pytest.fixture
def catalog_worker_engine(isolated_test_database_url):
    url = make_url(isolated_test_database_url)
    assert url.database is not None and url.database.startswith("test_dianzi_r06_catalog_")
    base = create_engine(url, connect_args={"connect_timeout": 5})
    schema = "test_r06_worker_" + uuid4().hex
    with base.begin() as connection:
        assert connection.scalar(text("SELECT current_database()")) == url.database
        connection.execute(CreateSchema(schema))
    migration = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=5000"}
    )
    engine = create_engine(migration, connect_args={"connect_timeout": 5})
    try:
        run_migrations(migration.render_as_string(hide_password=False))
        with engine.connect() as connection:
            assert (
                connection.scalar(
                    text(
                        "SELECT n.nspname FROM pg_class c "
                        "JOIN pg_namespace n ON n.oid=c.relnamespace "
                        "WHERE c.oid=to_regclass('alembic_version')"
                    )
                )
                == schema
            )
        yield engine
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


def queue(engine, kind, *, pages=1, at=NOW, key=None):
    with Session(engine) as session, session.begin():
        return enqueue_source_page(
            session,
            SourcePageRequest(
                source_kind=kind, window_end=at - timedelta(seconds=1), remaining_pages=pages
            ),
            at,
            idempotency_key=key,
        )


def run(engine, job_id, handler, at=NOW):
    return execute_job(
        engine, job_id, "fixture-worker", {SOURCE_JOB_TYPE: handler}, clock=lambda: at
    )


def handler_for(store, kind, *, clock=lambda: NOW, fetcher=None, poster=None):
    if kind == "avid_community":
        tree, blob = avid_responses()

        def read(url):
            return FetchResult(url, 200, "application/json", blob if "/git/blobs/" in url else tree)
    else:
        body, media = source_response(kind)

        def read(url):
            return FetchResult(url, 200, media, body)

    return build_source_page_handler(
        store, fetcher=fetcher or read, poster=poster or (lambda url, body: read(url)), clock=clock
    )


def test_nine_source_registrations_have_one_fixed_identity_and_eight_categories(
    catalog_worker_engine,
):
    scope = AccessScope.for_authenticated_user("fixture-admin", None, Role.SYSTEM_ADMIN)
    with Session(catalog_worker_engine) as session, session.begin():
        for kind, source in CATALOG_SOURCES.items():
            assert ensure_source_registration(session, scope, kind, NOW) == source.source_id
            assert ensure_source_registration(session, scope, kind, NOW) == source.source_id
        assert session.scalar(text("SELECT count(*) FROM sources")) == 9
        assert session.scalar(text("SELECT count(DISTINCT category) FROM sources")) == 8


@pytest.mark.parametrize(
    ("kind", "count"),
    [
        ("nvd_ollama", 1),
        ("vllm_vendor", 1),
        ("osv_ollama", 1),
        ("avid_community", 1),
        ("ollama_releases", 1),
        ("trailofbits_blog", 20),
        ("arxiv_security", 2),
        ("nist_ai_rmf", 1),
        ("cac_generative_ai", 1),
    ],
)
def test_nine_source_jobs_commit_raw_content_evidence_cursor_and_status(
    catalog_worker_engine, tmp_path, kind, count
):
    engine = catalog_worker_engine
    store = ContentStore(tmp_path)
    job_id = queue(engine, kind)
    handler = handler_for(store, kind)
    outcome = run(engine, job_id, handler)
    assert outcome == ("partial" if kind in {"arxiv_security", "nvd_ollama"} else "succeeded")
    assert run(engine, job_id, handler) == "not_claimed"
    raw_inputs = list(avid_responses()) if kind == "avid_community" else [source_response(kind)[0]]
    raw_hashes = {hashlib.sha256(body).hexdigest() for body in raw_inputs}
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(documents)) == count
        assert session.scalar(select(func.count()).select_from(document_revisions)) == count
        assert session.scalar(select(func.count()).select_from(source_page_receipts)) == 1
        observed_hashes = set(session.scalars(select(fetch_attempts.c.response_content_hash)))
        assert raw_hashes == observed_hashes
        for body in raw_inputs:
            assert store.read_verified(hashlib.sha256(body).hexdigest()) == body
        revisions = session.execute(select(document_revisions)).mappings().all()
        for revision in revisions:
            assert revision["source_response_hash"] in raw_hashes
            assert (
                hashlib.sha256(store.read_verified(revision["content_hash"])).hexdigest()
                == revision["content_hash"]
            )
        for item in session.execute(
            select(
                evidence.c.quote,
                evidence.c.quote_sha256,
                evidence.c.start_offset,
                evidence.c.end_offset,
                text_blocks.c.block_text,
                text_blocks.c.start_offset.label("block_start"),
            ).join(text_blocks, evidence.c.block_id == text_blocks.c.block_id)
        ):
            assert (
                item.block_text[
                    item.start_offset - item.block_start : item.end_offset - item.block_start
                ]
                == item.quote
            )
            assert hashlib.sha256(item.quote.encode()).hexdigest() == item.quote_sha256
        assert session.scalar(select(func.count()).select_from(evidence)) > 0
        assert (
            session.scalar(select(job_runs.c.status).where(job_runs.c.job_id == job_id)) == outcome
        )
        cursor = session.execute(select(source_cursors)).mappings().one()
        assert (
            cursor["source_id"] == CATALOG_SOURCES[kind].source_id and cursor["lease_owner"] is None
        )
        assert cursor["cursor_json"]["window_complete"] is (
            kind not in {"arxiv_security", "nvd_ollama"}
        )
        if kind not in {"nvd_ollama", "vllm_vendor"}:
            assert session.scalar(select(func.count()).select_from(events)) == 0
            assert all(item["source_metadata"] for item in revisions)


@pytest.mark.parametrize(
    "failure",
    [
        "storage",
        "second_document",
        "cursor_commit",
        "continuation",
        "invalid_page",
        "blob_corrupt",
        "blob_limit",
        "wrong_type",
        "timeout",
    ],
)
def test_catalog_failure_never_publishes_partial_page_or_cursor(
    catalog_worker_engine, tmp_path, monkeypatch, failure
):
    engine = catalog_worker_engine
    kind = "avid_community" if failure in {"blob_corrupt", "blob_limit"} else "arxiv_security"
    store = ContentStore(tmp_path)
    job_id = queue(engine, kind, pages=2)

    def unavailable(*args, **kwargs):
        raise OSError("fixture persistence failure")

    if failure == "storage":
        monkeypatch.setattr(store, "store_bytes", unavailable)
    if failure == "second_document":
        save = source_jobs.persist_catalog_documents

        def reject_after_save(*args, **kwargs):
            save(*args, **kwargs)
            raise OSError("fixture failure after page documents")

        monkeypatch.setattr(source_jobs, "persist_catalog_documents", reject_after_save)
    if failure == "cursor_commit":
        monkeypatch.setattr(
            source_jobs.SourceCursorRepository,
            "commit_page",
            unavailable,
        )
    if failure == "continuation":
        monkeypatch.setattr(
            source_jobs,
            "enqueue_source_page",
            unavailable,
        )
    tree, blob = avid_responses()

    def read(url):
        if failure == "invalid_page":
            return FetchResult(url, 200, "application/atom+xml", b"malformed source page")
        if failure == "wrong_type":
            return FetchResult(url, 200, "image/png", b"wrong source type")
        if failure == "timeout":
            raise NetworkTimeoutError("fixture timeout")
        if "/git/blobs/" in url:
            if failure == "blob_limit":
                return FetchResult(url, 429, "application/json", b"", {"Retry-After": "13"})
            return FetchResult(
                url, 200, "application/json", blob.replace(b'"sha": "', b'"sha": "f')
            )
        return FetchResult(url, 200, "application/json", tree)

    special = (
        read
        if failure in {"invalid_page", "blob_corrupt", "blob_limit", "wrong_type", "timeout"}
        else None
    )
    outcome = run(engine, job_id, handler_for(store, kind, fetcher=special))
    assert outcome == ("blocked" if failure in {"invalid_page", "blob_corrupt"} else "retry_wait")
    expected_error = {
        "storage": "source_response_storage_failed",
        "second_document": "handler_failed",
        "cursor_commit": "handler_failed",
        "continuation": "handler_failed",
        "invalid_page": "source_response_invalid",
        "blob_corrupt": "source_response_invalid",
        "blob_limit": "source_rate_limited",
        "wrong_type": "unsupported_content_type",
        "timeout": "network_timeout",
    }[failure]
    expected_bodies: tuple[bytes | None, ...]
    if failure == "blob_corrupt":
        expected_bodies = (tree, blob.replace(b'"sha": "', b'"sha": "f'))
        expected_outcomes = ("normalized", "normalization_failed")
        expected_errors = (None, "source_response_invalid")
        expected_statuses = (200, 200)
    elif failure == "blob_limit":
        expected_bodies = (tree, None)
        expected_outcomes = ("normalized", "transport_failed")
        expected_errors = (None, "source_rate_limited")
        expected_statuses = (200, 429)
    elif failure == "invalid_page":
        expected_bodies = (b"malformed source page",)
        expected_outcomes = ("normalization_failed",)
        expected_errors = ("source_response_invalid",)
        expected_statuses = (200,)
    elif failure in {"storage", "wrong_type", "timeout"}:
        expected_bodies = (None,)
        expected_outcomes = ("transport_failed",)
        expected_errors = (expected_error,)
        expected_statuses = (None if failure == "timeout" else 200,)
    else:
        expected_bodies = (source_response(kind)[0],)
        expected_outcomes = ("normalized",)
        expected_errors = (None,)
        expected_statuses = (200,)
    with Session(engine) as session:
        for table in (
            documents,
            document_revisions,
            evidence,
            text_blocks,
            claims,
            events,
            fetch_attempts,
            source_page_receipts,
            source_cursors,
        ):
            assert session.scalar(select(func.count()).select_from(table)) == 0
        assert session.scalar(select(func.count()).select_from(job_runs)) == 1
        job = session.execute(select(job_runs).where(job_runs.c.job_id == job_id)).mappings().one()
        assert job["status"] == outcome and job["error_code"] == expected_error
        assert job["attempt_count"] == 1
        outbox_job_ids = list(session.scalars(select(outbox_events.c.job_id)))
        assert outbox_job_ids == [job_id] * (2 if outcome == "retry_wait" else 1)
        receipts = list(
            session.execute(
                select(source_response_receipts).order_by(
                    source_response_receipts.c.response_ordinal
                )
            ).mappings()
        )
        assert len(receipts) == len(expected_bodies)
        assert [row["response_ordinal"] for row in receipts] == list(
            range(1, len(expected_bodies) + 1)
        )
        assert all(row["job_id"] == job_id and row["attempt_count"] == 1 for row in receipts)
        assert all(row["source_kind"] == kind for row in receipts)
        assert all(row["source_id"] == CATALOG_SOURCES[kind].source_id for row in receipts)
        assert [row["parse_outcome"] for row in receipts] == list(expected_outcomes)
        assert [row["error_code"] for row in receipts] == list(expected_errors)
        assert [row["http_status"] for row in receipts] == list(expected_statuses)
        retained_hashes = {
            row["response_content_hash"]
            for row in receipts
            if row["response_content_hash"] is not None
        }
        expected_hashes = {
            hashlib.sha256(body).hexdigest() for body in expected_bodies if body is not None
        }
        assert retained_hashes == expected_hashes
        assert set(session.scalars(select(content_objects.c.content_hash))) == retained_hashes
        if failure in {"storage", "wrong_type", "timeout"}:
            assert session.scalar(select(func.count()).select_from(content_objects)) == 0
        for row, body in zip(receipts, expected_bodies, strict=True):
            if body is None:
                assert row["response_content_hash"] is row["response_size_bytes"] is None
            else:
                assert row["response_content_hash"] == hashlib.sha256(body).hexdigest()
                assert row["response_size_bytes"] == len(body)
                assert store.read_verified(row["response_content_hash"]) == body


@pytest.mark.parametrize("pages", [1, 2])
def test_osv_partial_or_durable_continuation_preserves_post_body_and_resume(
    catalog_worker_engine, tmp_path, pages
):
    engine = catalog_worker_engine
    store = ContentStore(tmp_path)
    body, _ = source_response("osv_ollama")
    first_page = json.loads(body)
    first_page["next_page_token"] = "fixture-next"
    current = [NOW]
    seen = []

    def post(url, payload):
        submitted = json.loads(payload)
        seen.append(submitted)
        assert url == "https://api.osv.dev/v1/query"
        assert submitted["package"] == {"ecosystem": "Go", "name": "github.com/ollama/ollama"}
        response = body if "page_token" in submitted else json.dumps(first_page).encode()
        return FetchResult(url, 200, "application/json", response)

    first = queue(engine, "osv_ollama", pages=pages)
    assert run(
        engine, first, handler_for(store, "osv_ollama", poster=post, clock=lambda: current[0])
    ) == ("partial" if pages == 1 else "succeeded")
    with Session(engine) as session:
        state = session.scalar(select(source_cursors.c.cursor_json))
        assert state["position"] == {"page_token": "fixture-next"} and not state["window_complete"]
        next_id = session.scalar(select(job_runs.c.job_id).where(job_runs.c.job_id != first))
        if pages == 2:
            assert next_id is not None
            assert session.scalar(
                select(outbox_events.c.next_delivery_at).where(outbox_events.c.job_id == next_id)
            ) == NOW + timedelta(seconds=7)
        else:
            assert next_id is None
    current[0] += timedelta(seconds=8)
    if pages == 1:
        next_id = queue(engine, "osv_ollama", at=current[0])
    restarted = handler_for(store, "osv_ollama", poster=post, clock=lambda: current[0])
    assert run(engine, next_id, restarted, current[0]) == "succeeded"
    assert seen[-1]["page_token"] == "fixture-next"
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(document_revisions)) == 1
        assert session.scalar(select(func.count()).select_from(source_page_receipts)) == 2
        assert session.scalar(select(source_cursors.c.cursor_json))["window_complete"] is True


@pytest.mark.parametrize("corrupt", [False, True])
def test_avid_restart_uses_pinned_tree_and_retains_both_raw_requests(
    catalog_worker_engine, tmp_path, corrupt
):
    engine = catalog_worker_engine
    tree, blob = avid_responses(two_records=True)
    current = [NOW]
    seen = []

    def read(url):
        seen.append(url)
        content = tree
        if "/git/blobs/" in url:
            content = blob if len(seen) <= 2 or corrupt else avid_second_blob()
        return FetchResult(url, 200, "application/json", content)

    first = queue(engine, "avid_community", pages=1)
    assert (
        run(engine, first, handler_for(ContentStore(tmp_path), "avid_community", fetcher=read))
        == "partial"
    )
    with Session(engine) as session:
        before = session.execute(select(source_cursors)).mappings().one()
        assert before["cursor_json"]["position"] == {"tree_sha": "a" * 40, "record_offset": 1}
    current[0] += timedelta(seconds=8)
    second = queue(engine, "avid_community", at=current[0])
    assert run(
        engine,
        second,
        handler_for(
            ContentStore(tmp_path), "avid_community", fetcher=read, clock=lambda: current[0]
        ),
        current[0],
    ) == ("blocked" if corrupt else "succeeded")
    assert (
        seen[2]
        == "https://api.github.com/repos/avidml/avid-db/git/trees/" + "a" * 40 + "?recursive=1"
    )
    with Session(engine) as session:
        if corrupt:
            assert session.execute(select(source_cursors)).mappings().one() == before
        else:
            assert session.scalar(select(source_cursors.c.cursor_json))["window_complete"] is True
        assert session.scalar(select(func.count()).select_from(fetch_attempts)) == (
            2 if corrupt else 4
        )
        assert session.scalar(select(func.count()).select_from(document_revisions)) == (
            1 if corrupt else 2
        )


def test_conflicting_registered_identity_is_rejected_without_network(
    catalog_worker_engine, tmp_path
):
    engine = catalog_worker_engine
    scope = AccessScope.for_authenticated_user("fixture-admin", None, Role.SYSTEM_ADMIN)
    with Session(engine) as session, session.begin():
        source_id = ensure_source_registration(session, scope, "osv_ollama", NOW)
        session.execute(
            text("UPDATE sources SET category='academic_paper' WHERE source_id=:id"),
            {"id": source_id},
        )
    job_id = queue(engine, "osv_ollama")
    handler = handler_for(
        ContentStore(tmp_path),
        "osv_ollama",
        poster=lambda url, body: pytest.fail("conflicting source sent request"),
    )
    assert run(engine, job_id, handler) == "retry_wait"
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(source_cursors)) == 0
        assert session.scalar(select(func.count()).select_from(document_revisions)) == 0


@pytest.mark.parametrize("kind", tuple(source_jobs.CATALOG_CONTENT_TYPES))
def test_each_bad_catalog_page_is_blocked_without_business_or_cursor_writes(
    catalog_worker_engine, tmp_path, kind
):
    engine = catalog_worker_engine
    content_type = source_jobs.CATALOG_CONTENT_TYPES[kind][0]

    def read(url):
        return FetchResult(url, 200, content_type, b"invalid recorded source response")

    job_id = queue(engine, kind)
    handler = handler_for(
        ContentStore(tmp_path), kind, fetcher=read, poster=lambda url, body: read(url)
    )
    assert run(engine, job_id, handler) == "blocked"
    with Session(engine) as session:
        assert session.scalar(select(job_runs.c.error_code)) == "source_response_invalid"
        for table in (
            documents,
            document_revisions,
            source_cursors,
            source_page_receipts,
            fetch_attempts,
        ):
            assert session.scalar(select(func.count()).select_from(table)) == 0


@pytest.mark.parametrize("kind", ["osv_ollama", "avid_community"])
def test_valid_empty_catalog_response_is_recorded_without_fabricated_document(
    catalog_worker_engine, tmp_path, kind
):
    engine = catalog_worker_engine
    store = ContentStore(tmp_path)
    body = (
        b'{"vulns":[]}'
        if kind == "osv_ollama"
        else b'{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","truncated":false,"tree":[]}'
    )

    def read(url):
        return FetchResult(url, 200, "application/json", body)

    job_id = queue(engine, kind)
    assert (
        run(
            engine,
            job_id,
            handler_for(store, kind, fetcher=read, poster=lambda url, posted: read(url)),
        )
        == "succeeded"
    )
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(documents)) == 0
        assert session.scalar(select(func.count()).select_from(fetch_attempts)) == 1
        assert session.scalar(select(func.count()).select_from(source_page_receipts)) == 1
        assert session.scalar(select(source_cursors.c.cursor_json))["window_complete"] is True
        assert (
            session.scalar(select(fetch_attempts.c.response_content_hash))
            == hashlib.sha256(body).hexdigest()
        )
    assert store.read_verified(hashlib.sha256(body).hexdigest()) == body
