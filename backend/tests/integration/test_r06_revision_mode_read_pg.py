"""Real isolated PG reads of explicit synthetic revisions; no transport or model calls."""

import hashlib
import json
import os
import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema
from tests.r06_source_worker_fixtures import source_response
from tests.unit.test_r06_source_data_mode import paper

from ai_intel.api.document_read_service import DocumentFilters, DocumentReadService
from ai_intel.api.knowledge_read_service import KnowledgeReadService
from ai_intel.domain.access import AccessScope, Role
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.ingestion.catalog_documents import persist_catalog_documents
from ai_intel.ingestion.source_documents import (
    SourceResponse,
    ensure_source_registration,
    persist_source_response,
)
from ai_intel.knowledge.models import document_revisions, evidence
from ai_intel.knowledge.revisions import register_response_content

pytestmark = pytest.mark.real_pg
ADMIN = AccessScope.for_authenticated_user("mode-read-fixture", None, Role.SYSTEM_ADMIN)
NOW = datetime(2026, 10, 17, tzinfo=UTC)


@pytest.fixture
def revision_mode_engine(isolated_test_database_url: str) -> Iterator[Engine]:
    url = make_url(isolated_test_database_url)
    if (
        url.host != "127.0.0.1"
        or url.port != 25432
        or url.username != "test_dianzi_r01"
        or not re.fullmatch(r"test_dianzi_r06_mode_[a-f0-9]{12,16}", url.database or "")
    ):
        raise pytest.UsageError("blocked: a controller-owned R06 mode database is required")
    expected_oid = os.environ.get("R06_MODE_DATABASE_OID", "")
    expected_hash = os.environ.get("R06_MODE_DATABASE_COMMENT_SHA256", "")
    if not expected_oid.isdecimal() or not re.fullmatch(r"[a-f0-9]{64}", expected_hash):
        raise pytest.UsageError("blocked: controller database identity evidence is required")
    base = create_engine(url, poolclass=NullPool, connect_args={"connect_timeout": 5})
    schema = "test_r06_read_mode_" + uuid4().hex
    marker = json.dumps(
        {
            "project": "dianzi",
            "kind": "r06-revision-mode-test-schema",
            "nonce": uuid4().hex,
            "owner": "r06-revision-mode-read-fix",
        },
        sort_keys=True,
    )
    schema_oid = None
    engine = None
    try:
        with base.begin() as connection:
            database = connection.execute(
                text(
                    "SELECT oid, shobj_description(oid, 'pg_database') FROM pg_database "
                    "WHERE datname = current_database()"
                )
            ).one()
            if (
                database.oid != int(expected_oid)
                or not isinstance(database[1], str)
                or hashlib.sha256(database[1].encode()).hexdigest() != expected_hash
            ):
                raise pytest.UsageError("blocked: controller database identity changed")
            connection.execute(CreateSchema(schema))
            connection.exec_driver_sql(f"COMMENT ON SCHEMA {schema} IS '{marker}'")
            schema_oid = connection.scalar(
                text("SELECT oid FROM pg_namespace WHERE nspname=:name"), {"name": schema}
            )
        isolated = url.update_query_dict(
            {"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=5000"}
        )
        run_migrations(isolated.render_as_string(hide_password=False))
        engine = create_engine(isolated, poolclass=NullPool, connect_args={"connect_timeout": 5})
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if schema_oid is not None:
            with base.begin() as connection:
                actual = connection.execute(
                    text(
                        "SELECT oid, obj_description(oid, 'pg_namespace') FROM pg_namespace "
                        "WHERE nspname=:name"
                    ),
                    {"name": schema},
                ).one_or_none()
                if actual is None or actual.oid != schema_oid or actual[1] != marker:
                    raise RuntimeError("owned mode-test schema identity changed; cleanup refused")
                connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


def save_paper(engine, store, mode, ordinal=0):
    at = NOW + timedelta(seconds=ordinal)
    with Session(engine) as session, session.begin():
        ensure_source_registration(session, ADMIN, "arxiv_security", at)
        response = register_response_content(
            session, store, b"explicit synthetic paper response", at
        )
        saved = persist_catalog_documents(
            session,
            store,
            ADMIN,
            "arxiv_security",
            (paper(),),
            response_hash=response.content_hash,
            observed_at=at,
            ingested_at=at,
            data_mode=mode,
        )
        row = (
            session.execute(
                select(document_revisions).where(
                    document_revisions.c.revision_id == saved.revision_ids[0]
                )
            )
            .mappings()
            .one()
        )
        return UUID(row["document_id"]), UUID(row["revision_id"])


@pytest.mark.parametrize("stored", (None, "fixture", "live"))
def test_document_detail_uses_selected_pg_revision_mode(revision_mode_engine, tmp_path, stored):
    document_id, revision_id = save_paper(revision_mode_engine, ContentStore(tmp_path), stored)
    with Session(revision_mode_engine) as session:
        reader = DocumentReadService(session, ADMIN, "live", require_expected_mode=False)
        if stored is None:
            with pytest.raises(ValueError, match="stored_source_mode_unavailable"):
                reader.document_detail(document_id, revision_id)
        else:
            detail = reader.document_detail(document_id, revision_id)
            assert detail.data_mode == stored
            assert detail.document.revision_id == revision_id
            assert detail.evidence and all(item.data_mode == stored for item in detail.evidence)


def test_pg_unknown_fixture_live_history_is_immutable_and_not_a_live_envelope(
    revision_mode_engine, tmp_path
):
    store = ContentStore(tmp_path)
    saved = [
        save_paper(revision_mode_engine, store, mode, ordinal)
        for ordinal, mode in enumerate((None, "fixture", "live"))
    ]
    document_id = saved[-1][0]
    with Session(revision_mode_engine) as session:
        before = list(
            session.execute(
                select(
                    document_revisions.c.revision_id, document_revisions.c.source_metadata
                ).order_by(document_revisions.c.revision_number)
            )
        )
        reader = DocumentReadService(session, ADMIN, "live", require_expected_mode=False)
        assert reader.document_detail(document_id).data_mode == "live"
        assert reader.document_detail(document_id, saved[1][1]).data_mode == "fixture"
        with pytest.raises(ValueError):
            reader.document_detail(document_id, saved[0][1])
        with pytest.raises(ValueError):
            reader.list_revisions(document_id)
        after = list(
            session.execute(
                select(
                    document_revisions.c.revision_id, document_revisions.c.source_metadata
                ).order_by(document_revisions.c.revision_number)
            )
        )
        assert before == after
        assert [metadata.get("data_mode") for _, metadata in after] == [None, "fixture", "live"]


def test_internal_pg_evidence_reader_denies_fixture_under_live_before_citation_conversion(
    revision_mode_engine, tmp_path
):
    _document_id, revision_id = save_paper(revision_mode_engine, ContentStore(tmp_path), "fixture")
    with Session(revision_mode_engine) as session:
        evidence_id = session.scalar(
            select(evidence.c.evidence_id)
            .where(evidence.c.revision_id == str(revision_id))
            .limit(1)
        )
        with pytest.raises(ValueError, match="source_mode_does_not_match_consumer"):
            KnowledgeReadService(session, ADMIN, "live").read_evidence(UUID(evidence_id))
        assert (
            KnowledgeReadService(session, ADMIN, "fixture")
            .read_evidence(UUID(evidence_id))
            .data_mode
            == "fixture"
        )


@pytest.mark.parametrize("mode", ("fixture", "live"))
def test_event_detail_keeps_same_pg_source_mode(revision_mode_engine, tmp_path, mode):
    with Session(revision_mode_engine) as session, session.begin():
        saved = persist_source_response(
            session,
            ContentStore(tmp_path),
            ADMIN,
            SourceResponse(
                "nvd_ollama",
                source_response("nvd_ollama"),
                "https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=ollama&resultsPerPage=100&startIndex=0",
                NOW,
                data_mode=mode,
            ),
            ingested_at=NOW,
        )
    with Session(revision_mode_engine) as session:
        result = KnowledgeReadService(
            session, ADMIN, "live", require_expected_mode=False
        ).event_detail(UUID(saved.event_ids[0]))
        assert result.data_mode == mode and result.revisions


def test_pg_nonempty_unknown_list_is_unavailable_while_real_empty_filter_remains_empty(
    revision_mode_engine, tmp_path
):
    save_paper(revision_mode_engine, ContentStore(tmp_path), None)
    with Session(revision_mode_engine) as session:
        reader = DocumentReadService(session, ADMIN, "live", require_expected_mode=False)
        with pytest.raises(ValueError):
            reader.list_documents(DocumentFilters())
        empty = reader.list_documents(DocumentFilters(document_kind="policy"))
        assert empty.items == () and empty.data_mode == "live"
