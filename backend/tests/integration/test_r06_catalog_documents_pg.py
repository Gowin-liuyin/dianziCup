"""资料文档在真实隔离PG保留正文、元数据修订和权限，不能造漏洞事件。"""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from ai_intel.api.knowledge_read_service import KnowledgeReadService
from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from ai_intel.domain.enums import DocumentKind
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.ingestion.catalog_documents import (
    NormalizedSourceDocument,
    persist_catalog_documents,
)
from ai_intel.ingestion.parsing.parsers import parse_json_document
from ai_intel.ingestion.source_catalog import SourceCatalogError
from ai_intel.ingestion.source_documents import ensure_source_registration
from ai_intel.knowledge.models import document_revisions, documents, evidence, scope_epochs
from ai_intel.knowledge.persistence_models import events
from ai_intel.knowledge.revisions import register_response_content

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 15, 10, tzinfo=UTC)
ADMIN = AccessScope.for_authenticated_user("catalog-worker", None, Role.SYSTEM_ADMIN)


@pytest.fixture
def catalog_engine(isolated_test_database_url):
    url = make_url(isolated_test_database_url)
    assert url.database.startswith("test_dianzi_r06_catalog_")
    base = create_engine(url, connect_args={"connect_timeout": 5})
    schema = "test_r06_catalog_" + uuid4().hex
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=5000"}
    )
    run_migrations(isolated.render_as_string(hide_password=False))
    engine = create_engine(isolated, connect_args={"connect_timeout": 5})
    try:
        yield engine
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


def paper():
    body = json.dumps(
        {
            "title": "真实坐标结构的合成论文🙂",
            "abstract": "Quoted metadata is evidence of source text, not a security verdict.",
        },
        ensure_ascii=False,
    ).encode()
    return NormalizedSourceDocument(
        "2601.00001",
        DocumentKind.PAPER,
        "Synthetic paper metadata",
        "https://arxiv.org/abs/2601.00001v1",
        body,
        parse_json_document(body),
        None,
        None,
        {
            "version_label": "v1",
            "full_text_fetched": False,
            "published_at_raw": "2026-01-01",
            "published_precision": "calendar_date",
        },
    )


def save(engine, store, members, *, at=NOW, scope=ADMIN):
    with Session(engine) as session, session.begin():
        ensure_source_registration(session, ADMIN, "arxiv_security", at)
        response = register_response_content(
            session, store, b"synthetic upstream response bytes", at
        )
        return persist_catalog_documents(
            session,
            store,
            scope,
            "arxiv_security",
            members,
            response_hash=response.content_hash,
            observed_at=at,
            ingested_at=at,
            data_mode="fixture",
        )


def test_paper_is_replayable_document_with_openable_verified_spans_not_a_vulnerability(
    catalog_engine, tmp_path
):
    store = ContentStore(tmp_path / "raw")
    first = save(catalog_engine, store, (paper(),))
    repeated = save(catalog_engine, store, (paper(),), at=NOW + timedelta(seconds=1))
    assert first.new_revision_count == 1 and repeated.new_revision_count == 0
    assert repeated.revision_ids == first.revision_ids
    with Session(catalog_engine) as session:
        assert session.scalar(select(func.count()).select_from(documents)) == 1
        assert session.scalar(select(func.count()).select_from(events)) == 0
        revision = session.execute(select(document_revisions)).mappings().one()
        assert revision["source_published_at"] is None
        assert revision["source_metadata"]["published_at_raw"] == "2026-01-01"
        row = session.execute(select(evidence).limit(1)).mappings().one()
        result = KnowledgeReadService(session, ADMIN, "fixture").read_evidence(
            UUID(row["evidence_id"])
        )
        assert result.verified_at is not None and result.quote_text == row["quote"]
        assert result.quote_sha256 == hashlib.sha256(result.quote_text.encode()).hexdigest()
        assert row["supports_claim"] is False
        assert store.read_verified(revision["content_hash"]) == paper().payload


def test_metadata_changes_and_a_b_a_keep_three_distinct_historical_revisions(
    catalog_engine, tmp_path
):
    store = ContentStore(tmp_path / "raw")
    original = paper()
    changed = replace(original, metadata={**original.metadata, "version_label": "v2"})
    ids = [
        save(catalog_engine, store, (member,), at=NOW + timedelta(seconds=index)).revision_ids[0]
        for index, member in enumerate((original, changed, original))
    ]
    assert len(set(ids)) == 3
    with Session(catalog_engine) as session:
        rows = list(
            session.execute(
                select(document_revisions).order_by(document_revisions.c.revision_number)
            ).mappings()
        )
        assert [row["source_metadata"]["version_label"] for row in rows] == ["v1", "v2", "v1"]
        assert [row["is_current"] for row in rows] == [False, False, True]
        assert [row["previous_revision_id"] for row in rows] == [None, ids[0], ids[1]]
        assert (
            session.scalar(select(scope_epochs.c.epoch).where(scope_epochs.c.scope_key == "public"))
            == 3
        )


@pytest.mark.parametrize(
    "scope",
    [
        AccessScope.for_authenticated_user("viewer", "tenant-a", Role.VIEWER),
        AccessScope.for_authenticated_user("tenant-admin", "tenant-a", Role.TENANT_ADMIN),
    ],
)
def test_tenant_roles_cannot_publish_public_source_documents(catalog_engine, tmp_path, scope):
    with pytest.raises((SourceCatalogError, PermissionDeniedError)):
        save(catalog_engine, ContentStore(tmp_path / "raw"), (paper(),), scope=scope)
    with catalog_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(documents)) == 0


@pytest.mark.parametrize(
    "mutation",
    [
        "foreign_uri",
        "duplicate",
        "coordinates",
        "del_uri",
        "kind",
        "long_uri",
        "del_identifier",
        "sensitive_query",
    ],
)
def test_bad_member_rejects_the_whole_page_without_partial_documents(
    catalog_engine, tmp_path, mutation
):
    original = paper()
    bad = replace(original, source_record_id="2601.00002")
    if mutation == "foreign_uri":
        bad = replace(bad, canonical_uri="https://attacker.invalid/document")
    elif mutation == "duplicate":
        bad = original
    elif mutation == "del_uri":
        bad = replace(bad, canonical_uri="https://arxiv.org/abs/2601.00002\x7f")
    elif mutation == "kind":
        bad = replace(bad, kind=DocumentKind.ADVISORY)
    elif mutation == "long_uri":
        bad = replace(bad, canonical_uri="https://arxiv.org/abs/" + "x" * 2083)
    elif mutation == "del_identifier":
        bad = replace(bad, source_record_id="2601.00002\x7f")
    elif mutation == "sensitive_query":
        bad = replace(bad, canonical_uri="https://arxiv.org/abs/2601.00002?access_token=synthetic")
    else:
        parsed = replace(
            bad.parsed,
            blocks=(replace(bad.parsed.blocks[0], start_offset=99), *bad.parsed.blocks[1:]),
        )
        bad = replace(bad, parsed=parsed)
    with pytest.raises(SourceCatalogError):
        save(catalog_engine, ContentStore(tmp_path / "raw"), (original, bad))
    with catalog_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(document_revisions)) == 0
        assert connection.scalar(select(func.count()).select_from(evidence)) == 0


@pytest.mark.parametrize("field", ["canonical_uri", "published_at", "modified_at"])
def test_source_metadata_identity_changes_create_new_revisions(catalog_engine, tmp_path, field):
    original = paper()
    changes = {
        "canonical_uri": "https://arxiv.org/abs/2601.00001v2",
        "published_at": NOW,
        "modified_at": NOW,
    }
    changed = replace(original, **{field: changes[field]})
    store = ContentStore(tmp_path / "raw")
    first = save(catalog_engine, store, (original,))
    second = save(catalog_engine, store, (changed,), at=NOW + timedelta(seconds=1))
    assert first.new_revision_count == second.new_revision_count == 1
    assert first.revision_ids != second.revision_ids
    with catalog_engine.connect() as connection:
        current = (
            connection.execute(
                select(document_revisions).where(document_revisions.c.is_current.is_(True))
            )
            .mappings()
            .one()
        )
        assert current["source_metadata"][field] == (
            changes[field].isoformat() if isinstance(changes[field], datetime) else changes[field]
        )


def test_concurrent_replay_creates_only_one_revision(catalog_engine, tmp_path):
    store = ContentStore(tmp_path / "raw")
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(save, catalog_engine, store, (paper(),)) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert sum(result.new_revision_count for result in results) == 1
    assert results[0].revision_ids == results[1].revision_ids


def test_boolean_and_number_metadata_changes_preserve_distinct_history(catalog_engine, tmp_path):
    original = paper()
    members = [
        replace(original, metadata={**original.metadata, "upstream_flag": value})
        for value in (True, 1, True)
    ]
    store = ContentStore(tmp_path / "raw")
    ids = [
        save(catalog_engine, store, (member,), at=NOW + timedelta(seconds=index)).revision_ids[0]
        for index, member in enumerate(members)
    ]
    assert len(set(ids)) == 3
    with catalog_engine.connect() as connection:
        rows = (
            connection.execute(
                select(document_revisions.c.source_metadata).order_by(
                    document_revisions.c.revision_number
                )
            )
            .scalars()
            .all()
        )
        assert [type(row["upstream_flag"]) for row in rows] == [bool, int, bool]


@pytest.mark.parametrize("number", [1e16, 1e20, -0.0])
def test_jsonb_equivalent_number_replay_does_not_create_new_revision(
    catalog_engine, tmp_path, number
):
    original = replace(paper(), metadata={"upstream_number": number})
    store = ContentStore(tmp_path / "raw")
    first = save(catalog_engine, store, (original,))
    replay = save(catalog_engine, store, (original,), at=NOW + timedelta(seconds=1))
    assert first.new_revision_count == 1 and replay.new_revision_count == 0
    assert replay.revision_ids == first.revision_ids


def test_mid_page_storage_failure_cannot_commit_first_member(catalog_engine, tmp_path):
    second_payload = b'{"title":"Second synthetic paper","abstract":"storage failure"}'
    second = replace(
        paper(),
        source_record_id="2601.00002",
        payload=second_payload,
        parsed=parse_json_document(second_payload),
    )

    class FailingStore(ContentStore):
        """Only the second document's bytes fail; the upstream response remains writable."""

        def store_bytes(self, payload):
            if payload == second_payload:
                raise OSError("synthetic storage failure")
            return super().store_bytes(payload)

    store = FailingStore(tmp_path / "raw")
    with Session(catalog_engine) as session, session.begin():
        ensure_source_registration(session, ADMIN, "arxiv_security", NOW)
        response = register_response_content(session, store, b"upstream synthetic response", NOW)
        with pytest.raises(OSError):
            persist_catalog_documents(
                session,
                store,
                ADMIN,
                "arxiv_security",
                (paper(), second),
                response_hash=response.content_hash,
                observed_at=NOW,
                ingested_at=NOW,
            )
    with catalog_engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(document_revisions)) == 0
        assert connection.scalar(select(func.count()).select_from(evidence)) == 0
        assert connection.scalar(select(func.count()).select_from(scope_epochs)) == 0
