"""Independent boundary assertions; real PostgreSQL only in a unique review schema."""

import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, insert, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from ai_intel.domain.access import AccessScope, Role
from ai_intel.domain.enums import DocumentKind
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.ingestion.catalog_documents import NormalizedSourceDocument, persist_catalog_documents
from ai_intel.ingestion.parsing.parsers import parse_json_document
from ai_intel.ingestion.source_catalog import SourceCatalogError
from ai_intel.ingestion.source_documents import SourceDocumentError, SourceResponse, ensure_source_registration, persist_source_response
from ai_intel.knowledge.models import content_objects, document_revisions, documents, evidence, scope_epochs, text_blocks
from ai_intel.knowledge.revisions import register_response_content

NOW = datetime(2026, 10, 15, 12, tzinfo=UTC)
ADMIN = AccessScope.for_authenticated_user("independent-review", None, Role.SYSTEM_ADMIN)


@pytest.fixture
def engine():
    assert os.environ["DIANZI_TEST_RUN_ID"] == "r06_catalog_final_review_20261015"
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert url.database == "test_dianzi_r06_catalog_final_review_20261015"
    base = create_engine(url)
    schema = "test_r06_review_probe_" + uuid4().hex
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    scoped = url.update_query_dict({"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=5000"})
    run_migrations(scoped.render_as_string(hide_password=False))
    result = create_engine(scoped)
    with result.connect() as connection:
        assert connection.scalar(text("SELECT current_schema()")) == schema
        assert connection.scalar(text("SELECT n.nspname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.oid=to_regclass('alembic_version')")) == schema
    try:
        yield result
    finally:
        result.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


def member():
    payload = json.dumps({"title": "Independent text", "abstract": "Evidence🙂 is source text."}, ensure_ascii=False).encode()
    return NormalizedSourceDocument("independent-record", DocumentKind.PAPER, "Independent title", "https://arxiv.org/abs/2601.22222", payload, parse_json_document(payload), None, None, {"content_coverage": "abstract"})


def persist(engine, store, members, index=0):
    at = NOW + timedelta(seconds=index)
    with Session(engine) as session, session.begin():
        ensure_source_registration(session, ADMIN, "arxiv_security", at)
        response = register_response_content(session, store, b"independent response", at)
        return persist_catalog_documents(session, store, ADMIN, "arxiv_security", members, response_hash=response.content_hash, observed_at=at, ingested_at=at)


@pytest.mark.parametrize("uri", [
    "https://arxiv.org/abs/2601.22222?%61ccess_token=synthetic",
    "https://arxiv.org/abs/2601.22222?PASSWORD=synthetic",
    "https://arxiv.org/abs/2601.22222\x7f",
    "https://arxiv.org/abs/" + "x" * (2084 - len("https://arxiv.org/abs/")),
])
def test_bad_second_uri_leaves_no_committable_document(engine, tmp_path, uri):
    store = ContentStore(tmp_path / "store")
    first = member()
    second = replace(first, source_record_id="other", canonical_uri=uri)
    with Session(engine) as session, session.begin():
        ensure_source_registration(session, ADMIN, "arxiv_security", NOW)
        response = register_response_content(session, store, b"independent response", NOW)
        with pytest.raises(SourceCatalogError):
            persist_catalog_documents(session, store, ADMIN, "arxiv_security", (first, second), response_hash=response.content_hash, observed_at=NOW, ingested_at=NOW)
    with engine.connect() as connection:
        assert all(connection.scalar(select(func.count()).select_from(table)) == 0 for table in (documents, document_revisions, text_blocks, evidence, scope_epochs))


def test_exact_uri_length_boundary_and_identifier_del(engine, tmp_path):
    store = ContentStore(tmp_path / "store")
    original = replace(member(), canonical_uri="https://arxiv.org/abs/" + "x" * (2083 - len("https://arxiv.org/abs/")))
    assert persist(engine, store, (original,)).new_revision_count == 1
    with pytest.raises(SourceCatalogError):
        persist(engine, store, (replace(original, source_record_id="bad\x7f"),), 1)
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(document_revisions)) == 1


def test_second_storage_error_caught_and_outer_commit_remains_atomic(engine, tmp_path):
    payload = b'{"title":"Second","abstract":"fail writing this"}'
    second = replace(member(), source_record_id="second", payload=payload, parsed=parse_json_document(payload))

    class SecondWriteFails(ContentStore):
        def store_bytes(self, body):
            if body == payload:
                raise OSError("controlled second write error")
            return super().store_bytes(body)

    store = SecondWriteFails(tmp_path / "store")
    with Session(engine) as session, session.begin():
        ensure_source_registration(session, ADMIN, "arxiv_security", NOW)
        response = register_response_content(session, store, b"independent response", NOW)
        with pytest.raises(OSError):
            persist_catalog_documents(session, store, ADMIN, "arxiv_security", (member(), second), response_hash=response.content_hash, observed_at=NOW, ingested_at=NOW)
    with engine.connect() as connection:
        assert all(connection.scalar(select(func.count()).select_from(table)) == 0 for table in (documents, document_revisions, text_blocks, evidence, scope_epochs))
        assert connection.scalar(select(func.count()).select_from(content_objects)) == 1


@pytest.mark.parametrize("value", [1e20, -0.0])
def test_numeric_metadata_replay_and_type_distinction(engine, tmp_path, value):
    store = ContentStore(tmp_path / "store")
    original = replace(member(), metadata={"upstream_number": value, "flag": True})
    first = persist(engine, store, (original,))
    replay = persist(engine, store, (original,), 1)
    number = replace(original, metadata={"upstream_number": value, "flag": 1})
    second = persist(engine, store, (number,), 2)
    third = persist(engine, store, (original,), 3)
    assert first.revision_ids == replay.revision_ids and replay.new_revision_count == 0
    assert len({first.revision_ids[0], second.revision_ids[0], third.revision_ids[0]}) == 3
    with engine.connect() as connection:
        rows = connection.execute(select(document_revisions.c.revision_number, document_revisions.c.source_metadata, document_revisions.c.is_current).order_by(document_revisions.c.revision_number)).all()
        assert [type(row.source_metadata["flag"]) for row in rows] == [bool, int, bool]
        assert [row.is_current for row in rows] == [False, False, True]
        assert connection.scalar(select(scope_epochs.c.epoch)) == 3


def test_jsonb_nonobject_direct_write_is_rejected(engine, tmp_path):
    result = persist(engine, ContentStore(tmp_path / "store"), (member(),))
    with Session(engine) as session:
        with pytest.raises(IntegrityError):
            session.execute(document_revisions.update().where(document_revisions.c.revision_id == result.revision_ids[0]).values(source_metadata=["invalid"]))
        session.rollback()
        assert session.scalar(select(document_revisions.c.source_metadata))["title"] == "Independent title"


def test_old_source_writer_still_reuses_head_without_explicit_metadata(engine, tmp_path):
    root = Path(__file__).resolve().parents[3]
    records = json.loads((root / "fixtures/recorded/vllm_vendor_20261015_public.json").read_bytes())
    body = json.dumps([records[0]]).encode()
    store = ContentStore(tmp_path / "store")
    response = SourceResponse("vllm_vendor", body, "https://api.github.com/repos/vllm-project/vllm/security-advisories?per_page=10&state=published", NOW)
    results = []
    for index in range(2):
        with Session(engine) as session, session.begin():
            results.append(persist_source_response(session, store, ADMIN, response, ingested_at=NOW + timedelta(seconds=index)))
    assert [result.new_revision_count for result in results] == [1, 0]
    assert results[0].revision_ids == results[1].revision_ids
    with engine.connect() as connection:
        assert connection.scalar(select(document_revisions.c.source_metadata)) == {}


def test_source_registration_rejects_scope_conflict_and_unknown_kind(engine):
    with Session(engine) as session, session.begin():
        source_id = ensure_source_registration(session, ADMIN, "arxiv_security", NOW)
        session.execute(text("UPDATE sources SET name=:name WHERE source_id=:id"), {"name": "conflicting identity", "id": source_id})
    with Session(engine) as session, session.begin():
        with pytest.raises(SourceDocumentError, match="conflicts"):
            ensure_source_registration(session, ADMIN, "arxiv_security", NOW)
        with pytest.raises(SourceDocumentError, match="unsupported"):
            ensure_source_registration(session, ADMIN, "synthetic_unregistered", NOW)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM sources")) == 1
        assert connection.scalar(text("SELECT name FROM sources")) == "conflicting identity"
