"""Real isolated PG, explicit offline transport fixtures, immutable source mode history."""

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema
from tests.r06_source_worker_fixtures import source_response
from tests.unit.test_r06_source_data_mode import paper

from ai_intel.domain.access import AccessScope, Role
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.network import FetchResult
from ai_intel.ingestion import catalog_documents, source_documents
from ai_intel.ingestion.catalog_documents import persist_catalog_documents
from ai_intel.ingestion.source_documents import (
    SourceResponse,
    ensure_source_registration,
    persist_source_response,
)
from ai_intel.ingestion.source_failure_models import source_response_receipts
from ai_intel.ingestion.source_jobs import (
    SOURCE_JOB_TYPE,
    SourcePageRequest,
    build_source_page_handler,
    enqueue_source_page,
    source_page_url,
)
from ai_intel.knowledge.models import (
    document_revisions,
    documents,
    job_runs,
    source_cursors,
    source_page_receipts,
)
from ai_intel.knowledge.persistence_models import claims, event_documents
from ai_intel.knowledge.revisions import register_response_content
from ai_intel.workers.executor import execute_job

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 16, 12, tzinfo=UTC)
ADMIN = AccessScope.for_authenticated_user("mode-fixture-admin", None, Role.SYSTEM_ADMIN)


@pytest.fixture
def mode_engine(isolated_test_database_url: str) -> Iterator[Engine]:
    url = make_url(isolated_test_database_url)
    assert url.host == "127.0.0.1" and url.port == 25432
    assert url.database == "test_dianzi_r06_source_data_mode_20261016"
    base = create_engine(url, poolclass=NullPool, hide_parameters=True)
    schema = "test_r06_mode_" + uuid4().hex
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
        connection.exec_driver_sql(f"COMMENT ON SCHEMA \"{schema}\" IS 'r06-source-mode-fixture'")
    isolated = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=5000"}
    )
    engine = create_engine(isolated, poolclass=NullPool, hide_parameters=True)
    try:
        run_migrations(isolated.render_as_string(hide_password=False))
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "0030_revalidation_actor_bindings"
            )
        yield engine
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


@pytest.mark.parametrize("kind", ["nvd_ollama", "vllm_vendor"])
def test_same_bytes_mode_changes_append_revisions_and_move_current_claim_event_links(
    mode_engine, tmp_path, kind
):
    store = ContentStore(tmp_path)
    body, _content_type = source_response(kind)
    url = source_page_url(kind, {})
    saved = []
    for index, mode in enumerate((None, "fixture", "live", "live", None)):
        at = NOW + timedelta(seconds=index)
        with Session(mode_engine) as session, session.begin():
            saved.append(
                persist_source_response(
                    session,
                    store,
                    ADMIN,
                    SourceResponse(kind, body, url, at, data_mode=mode),
                    ingested_at=at,
                )
            )
    assert [item.new_revision_count for item in saved] == [1, 1, 1, 0, 1]
    ids = [saved[index].revision_ids[0] for index in (0, 1, 2, 4)]
    assert len(set(ids)) == 4 and saved[2].revision_ids == saved[3].revision_ids
    with Session(mode_engine) as session:
        rows = list(
            session.execute(
                select(document_revisions).order_by(document_revisions.c.revision_number)
            ).mappings()
        )
        assert [row["source_metadata"].get("data_mode") for row in rows] == (
            [None, "fixture", "live", None]
        )
        assert rows[0]["source_metadata"] == rows[-1]["source_metadata"] == {}
        assert [row["is_current"] for row in rows] == [False, False, False, True]
        assert [row["previous_revision_id"] for row in rows] == [None, *ids[:-1]]
        assert len({row["content_hash"] for row in rows}) == 1
        assert {row["source_response_hash"] for row in rows} == {saved[0].response_content_hash}
        assert {store.read_verified(row["content_hash"]) for row in rows} == {
            source_documents._prepare_documents(SourceResponse(kind, body, url, NOW))[0].payload
        }
        assert set(
            session.scalars(select(claims.c.source_revision_id).where(claims.c.is_current))
        ) == {ids[-1]}
        assert set(session.scalars(select(claims.c.source_revision_id))) == set(ids)
        links = list(session.execute(select(event_documents)).mappings())
        assert {row["revision_id"] for row in links if row["active"]} == {ids[-1]}
        assert {row["revision_id"] for row in links} == set(ids)


def test_catalog_mode_changes_keep_normal_metadata_and_ignore_external_mode(mode_engine, tmp_path):
    store = ContentStore(tmp_path)
    member = replace(
        paper(), metadata={"data_mode": "live", "data_mode_policy_version": "forged", "v": 1}
    )
    saved = []
    for index, mode in enumerate((None, "fixture", "live", "live", None)):
        at = NOW + timedelta(seconds=index)
        with Session(mode_engine) as session, session.begin():
            ensure_source_registration(session, ADMIN, "arxiv_security", at)
            content = register_response_content(session, store, b"offline catalog response", at)
            saved.append(
                persist_catalog_documents(
                    session,
                    store,
                    ADMIN,
                    "arxiv_security",
                    (member,),
                    response_hash=content.content_hash,
                    observed_at=at,
                    ingested_at=at,
                    data_mode=mode,
                )
            )
    assert [item.new_revision_count for item in saved] == [1, 1, 1, 0, 1]
    with Session(mode_engine) as session:
        rows = list(
            session.execute(
                select(document_revisions).order_by(document_revisions.c.revision_number)
            ).mappings()
        )
        assert [row["source_metadata"].get("data_mode") for row in rows] == (
            [None, "fixture", "live", None]
        )
        for row in rows:
            metadata = row["source_metadata"]
            assert metadata["title"] == "Synthetic paper" and metadata["v"] == 1
            assert metadata["parser_version"] == "json-2.0.0"
            assert metadata["normalizer_version"] == member.parsed.normalizer_version
            assert metadata["published_at"] == "2026-10-16T00:00:00+00:00"
            assert metadata.get("data_mode_policy_version") != "forged"
            assert store.read_verified(row["content_hash"]) == member.payload
        assert rows[0]["source_metadata"] == rows[-1]["source_metadata"]


def queue_and_run(engine, store, kind, *, at=NOW):
    body, content_type = source_response(kind)
    handler = build_source_page_handler(
        store,
        data_mode="fixture",
        fetcher=lambda url: FetchResult(url, 200, content_type, body),
        clock=lambda: at,
    )
    with Session(engine) as session, session.begin():
        job_id = enqueue_source_page(
            session,
            SourcePageRequest(source_kind=kind, window_end=at - timedelta(seconds=1)),
            at,
        )
    return execute_job(
        engine, job_id, "mode-fixture-worker", {SOURCE_JOB_TYPE: handler}, clock=lambda: at
    )


@pytest.mark.parametrize("kind", ["nvd_ollama", "ollama_releases"])
def test_worker_stamps_fixture_and_receipt_points_to_same_revision(mode_engine, tmp_path, kind):
    assert queue_and_run(mode_engine, ContentStore(tmp_path), kind) == "succeeded"
    with Session(mode_engine) as session:
        revision = session.execute(select(document_revisions)).mappings().one()
        receipt = session.execute(select(source_page_receipts)).mappings().one()
        assert revision["source_metadata"]["data_mode"] == "fixture"
        assert receipt["revision_ids"] == [revision["revision_id"]]
        assert session.scalar(select(func.count()).select_from(source_cursors)) == 1


@pytest.mark.parametrize("kind", ["nvd_ollama", "ollama_releases"])
def test_invalid_revision_metadata_preserves_failed_response_and_rolls_back_cursor(
    mode_engine, tmp_path, monkeypatch, kind
):
    invalid = {"oversize": "x" * 70000}
    if kind == "nvd_ollama":
        monkeypatch.setattr(source_documents, "source_data_mode_metadata", lambda mode: invalid)
    else:
        monkeypatch.setattr(catalog_documents, "_revision_metadata", lambda *a, **k: invalid)
    assert queue_and_run(mode_engine, ContentStore(tmp_path), kind) == "blocked"
    with Session(mode_engine) as session:
        for table in (documents, document_revisions, claims, source_cursors, source_page_receipts):
            assert session.scalar(select(func.count()).select_from(table)) == 0
        receipt = session.execute(select(source_response_receipts)).mappings().one()
        if kind == "nvd_ollama":
            assert receipt["parse_outcome"] == "normalization_failed"
            assert receipt["error_code"] == "source_response_invalid"
        else:
            assert receipt["parse_outcome"] == "normalized"
            assert receipt["error_code"] is None
        job = session.execute(select(job_runs)).mappings().one()
        assert job["status"] == "blocked" and job["error_code"] == "source_response_invalid"
        assert receipt["response_content_hash"] is not None
