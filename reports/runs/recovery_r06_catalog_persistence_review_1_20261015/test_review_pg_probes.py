"""Independent real PostgreSQL boundary probes, isolated UUID schemas only."""

import os
from dataclasses import replace
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from ai_intel.api.document_contracts import validate_public_source_uri
from ai_intel.domain.access import AccessScope, Role
from ai_intel.domain.enums import DocumentKind
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.ingestion.catalog_documents import NormalizedSourceDocument, persist_catalog_documents
from ai_intel.ingestion.parsing.parsers import parse_json_document
from ai_intel.ingestion.source_catalog import CATALOG_SOURCES, SourceCatalogError
from ai_intel.ingestion.source_documents import ensure_source_registration
from ai_intel.knowledge.models import document_revisions, documents, evidence
from ai_intel.knowledge.revisions import cleanup_unreferenced_object, register_response_content, save_document_revision

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 15, 12, tzinfo=UTC)
ADMIN = AccessScope.for_authenticated_user("independent-review", None, Role.SYSTEM_ADMIN)


@pytest.fixture
def engine():
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert url.database.startswith("test_dianzi_r06_catalog_review_")
    base = create_engine(url)
    schema = "test_review_" + uuid4().hex
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = url.update_query_dict({"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=5000"})
    run_migrations(isolated.render_as_string(hide_password=False))
    result = create_engine(isolated)
    try:
        yield result
    finally:
        result.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


def member(identifier="review-a", body=b'{"abstract":"review text"}'):
    return NormalizedSourceDocument(identifier, DocumentKind.PAPER, "Review title",
        "https://arxiv.org/abs/2601.00001v1", body, parse_json_document(body), None, None,
        {"published_precision": "unknown", "full_text_fetched": False})


def persist(session, store, items):
    ensure_source_registration(session, ADMIN, "arxiv_security", NOW)
    response = register_response_content(session, store, b"synthetic response for independent probe", NOW)
    return persist_catalog_documents(session, store, ADMIN, "arxiv_security", items,
        response_hash=response.content_hash, observed_at=NOW, ingested_at=NOW)


def test_sensitive_canonical_query_is_rejected_before_public_persistence(engine, tmp_path):
    item = replace(member(), canonical_uri="https://arxiv.org/abs/2601.00001?access_token=synthetic")
    with Session(engine) as session, session.begin():
        with pytest.raises(SourceCatalogError):
            persist(session, ContentStore(tmp_path / "raw"), (item,))
        assert session.scalar(select(func.count()).select_from(document_revisions)) == 0


def test_caught_midpage_storage_error_does_not_leave_committable_first_member(engine, tmp_path):
    class FaultyStore(ContentStore):
        def store_bytes(self, payload):
            if payload == b'{"abstract":"second content"}':
                raise OSError("synthetic bounded storage failure")
            return super().store_bytes(payload)

    first = member()
    second = member("review-b", b'{"abstract":"second content"}')
    with Session(engine) as session, session.begin():
        try:
            persist(session, FaultyStore(tmp_path / "raw"), (first, second))
        except OSError:
            pass
    with Session(engine) as session:
        count = session.scalar(select(func.count()).select_from(document_revisions))
        assert count == 0, f"caught error committed {count} revision(s) from a failed page"
        assert session.scalar(select(func.count()).select_from(evidence)) == 0


def test_prevalidation_rejects_all_members_even_when_caller_catches_error(engine, tmp_path):
    with Session(engine) as session, session.begin():
        with pytest.raises(SourceCatalogError):
            persist(session, ContentStore(tmp_path / "raw"),
                (member(), replace(member("review-b"), title="")))
        assert session.scalar(select(func.count()).select_from(document_revisions)) == 0


def test_referenced_response_and_payload_are_both_protected_from_gc(engine, tmp_path):
    store = ContentStore(tmp_path / "raw")
    with Session(engine) as session, session.begin():
        persist(session, store, (member(),))
        revision = session.execute(select(document_revisions)).mappings().one()
        for key in ("content_hash", "source_response_hash"):
            assert cleanup_unreferenced_object(session, store, revision[key]) is False
            assert store.read_verified(revision[key])


def test_old_positional_caller_still_reuses_metadata_revision_at_head(engine, tmp_path):
    store = ContentStore(tmp_path / "raw")
    with Session(engine) as session, session.begin():
        original = persist(session, store, (member(),))
        document_id = str(uuid5(NAMESPACE_URL, "dianzi:document:" + CATALOG_SOURCES["arxiv_security"].source_id + ":review-a"))
        saved = save_document_revision(session, store, document_id, member().payload, "public", None, NOW)
        assert saved.reused is True
        assert saved.revision_id == original.revision_ids[0]
        assert session.scalar(select(func.count()).select_from(document_revisions)) == 1


def test_revision_metadata_must_remain_object_under_direct_database_write(engine, tmp_path):
    from sqlalchemy.exc import IntegrityError

    with Session(engine) as session, session.begin():
        saved = persist(session, ContentStore(tmp_path / "raw"), (member(),))
        with pytest.raises(IntegrityError):
            with session.begin_nested():
                session.execute(text("UPDATE document_revisions SET source_metadata='[]'::jsonb WHERE revision_id=:id"), {"id": saved.revision_ids[0]})
        assert session.scalar(select(func.count()).select_from(documents)) == 1


def test_json_boolean_and_number_are_distinct_revision_metadata(engine, tmp_path):
    store = ContentStore(tmp_path / "raw")
    with Session(engine) as session, session.begin():
        first = persist(session, store, (replace(member(), metadata={"upstream_flag": True}),))
        second = persist(session, store, (replace(member(), metadata={"upstream_flag": 1}),))
        assert second.new_revision_count == 1, f"boolean-to-number metadata change reused={second.new_revision_count == 0}"
        assert first.revision_ids != second.revision_ids
        assert session.scalar(select(func.count()).select_from(document_revisions)) == 2
