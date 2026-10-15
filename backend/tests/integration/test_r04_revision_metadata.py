"""真实PG验证旧修订保留、原始HTTP响应的引用保护与非法定位拒绝。"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_r02_schema_migration import empty_schema_engine as empty_schema_engine
from test_t05_persistence_and_raw_store import seed_document

from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.knowledge.models import (
    content_objects,
    document_revisions,
    fetch_attempts,
    text_blocks,
)
from ai_intel.knowledge.revisions import (
    cleanup_unreferenced_object,
    register_response_content,
    save_document_revision,
)

pytestmark = pytest.mark.real_pg


def test_response_registration_verifies_bytes_and_reuses_one_pg_object(
    empty_schema_engine, tmp_path
):
    run_migrations(empty_schema_engine.url.render_as_string(hide_password=False))
    store = ContentStore(tmp_path / "objects")
    payload = b'{"original":true}'
    now = datetime.now(UTC)
    with Session(empty_schema_engine) as session, session.begin():
        first = register_response_content(session, store, payload, now)
        second = register_response_content(session, store, payload, now)
        assert first.content_hash == second.content_hash
        assert store.read_verified(first.content_hash) == payload
        rows = session.execute(select(content_objects)).mappings().all()
        assert len(rows) == 1 and rows[0]["size_bytes"] == len(payload)
        assert rows[0]["created_at"] == now


def test_0012_revision_times_and_blocks_are_not_fabricated_by_upgrade(empty_schema_engine):
    connection_url = empty_schema_engine.url.render_as_string(hide_password=False)
    run_migrations(connection_url, "0012_source_page_fingerprint")
    with empty_schema_engine.begin() as connection:
        seed_document(connection, "legacy-document", "public", None)
        connection.execute(
            text(
                "INSERT INTO document_revisions(revision_id,document_id,revision_number,"
                "content_hash,"
                "created_at,is_current,visibility) VALUES ('legacy-revision','legacy-document',1,"
                ":hash,:time,true,'public')"
            ),
            {"hash": "0" * 64, "time": datetime(2026, 10, 1, tzinfo=UTC)},
        )
        connection.execute(
            text(
                "INSERT INTO text_blocks(block_id,revision_id,ordinal,start_offset,end_offset,"
                "text_sha256,block_text) VALUES "
                "('legacy-block','legacy-revision',0,12,14,:hash,'原文')"
            ),
            {"hash": "1" * 64},
        )
    run_migrations(connection_url)
    with empty_schema_engine.connect() as connection:
        revision = connection.execute(select(document_revisions)).mappings().one()
        assert revision["created_at"] == datetime(2026, 10, 1, tzinfo=UTC)
        assert revision["parse_status"] == "legacy_unverified"
        assert all(
            revision[field] is None
            for field in (
                "source_published_at",
                "source_modified_at",
                "first_observed_at",
                "ingested_at",
                "canonical_uri",
                "parser_version",
                "normalizer_version",
                "source_response_hash",
                "source_json_pointer",
            )
        )
        block = connection.execute(select(text_blocks)).mappings().one()
        assert (block["block_text"], block["start_offset"], block["end_offset"]) == ("原文", 12, 14)
        assert block["page_number"] is None and block["json_pointer"] is None


@pytest.mark.parametrize("reference_kind", ["revision", "fetch_attempt"])
def test_full_http_response_references_prevent_object_cleanup(
    empty_schema_engine, tmp_path, reference_kind
):
    run_migrations(empty_schema_engine.url.render_as_string(hide_password=False))
    store = ContentStore(tmp_path / "objects")
    now = datetime.now(UTC)
    with Session(empty_schema_engine) as session, session.begin():
        seed_document(session, "document", "public", None)
        saved = save_document_revision(
            session, store, "document", b'{"cve":{}}', "public", None, now
        )
        response = store.store_bytes(b'{"timestamp":"volatile","vulnerabilities":[{"cve":{}}]}')
        session.execute(
            content_objects.insert().values(
                content_hash=response.content_hash, size_bytes=response.size_bytes, created_at=now
            )
        )
        if reference_kind == "revision":
            session.execute(
                update(document_revisions)
                .where(document_revisions.c.revision_id == saved.revision_id)
                .values(
                    source_response_hash=response.content_hash,
                    source_json_pointer="/vulnerabilities/0",
                )
            )
        else:
            source_id = session.scalar(
                text("SELECT source_id FROM documents WHERE document_id='document'")
            )
            session.execute(
                fetch_attempts.insert().values(
                    attempt_id="attempt",
                    source_id=source_id,
                    attempted_at=now,
                    outcome="succeeded",
                    new_event_count=0,
                    response_content_hash=response.content_hash,
                    final_url="https://example.invalid/public",
                )
            )
        assert cleanup_unreferenced_object(session, store, response.content_hash) is False
        assert store.read_verified(response.content_hash).startswith(b'{"timestamp"')
        assert cleanup_unreferenced_object(session, store, saved.content_hash) is False
    with empty_schema_engine.begin() as connection:
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(update(document_revisions).values(parse_status="pretend_success"))
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                text_blocks.insert().values(
                    block_id="bad-page",
                    revision_id=saved.revision_id,
                    ordinal=0,
                    start_offset=0,
                    end_offset=1,
                    text_sha256="a" * 64,
                    block_text="x",
                    page_number=0,
                )
            )
