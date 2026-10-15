"""Real PG checks for source bulk equivalence, atomic batches and unchanged page semantics."""

import hashlib
import json
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select, update
from sqlalchemy.orm import Session
from tests.integration.test_r06_catalog_documents_pg import NOW, paper, save
from tests.integration.test_r06_catalog_documents_pg import catalog_engine as catalog_engine
from tests.integration.test_r06_source_worker_pg import queue, run

from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.network import FetchResult
from ai_intel.ingestion.source_jobs import build_source_page_handler
from ai_intel.knowledge.models import (
    document_revisions,
    documents,
    evidence,
    source_cursors,
    source_page_receipts,
    text_blocks,
)
from ai_intel.knowledge.revisions import (
    SourceRevisionBlock,
    add_text_block,
    attach_evidence_span,
    register_source_revision_blocks,
)

pytestmark = pytest.mark.real_pg


def source_block(ordinal=0, *, page=None, pointer=None):
    text = "原文🙂\n"
    start = ordinal * len(text)
    return SourceRevisionBlock(
        ordinal,
        start,
        start + len(text),
        text,
        hashlib.sha256(text.encode()).hexdigest(),
        "json_field" if pointer is not None else "paragraph",
        page,
        pointer,
    )


def empty_revision(engine, store):
    saved = save(engine, store, (replace(paper(), source_record_id=uuid4().hex),))
    revision_id = saved.revision_ids[0]
    with Session(engine) as session, session.begin():
        session.execute(evidence.delete().where(evidence.c.revision_id == revision_id))
        session.execute(text_blocks.delete().where(text_blocks.c.revision_id == revision_id))
    return revision_id


def test_bulk_rows_match_original_single_row_semantics_field_for_field(catalog_engine, tmp_path):
    store = ContentStore(tmp_path)
    original = empty_revision(catalog_engine, store)
    bulk = empty_revision(catalog_engine, store)
    blocks = (source_block(), source_block(1, pointer="/escaped~1🙂"), source_block(2, page=3))
    with Session(catalog_engine) as session, session.begin():
        for block in blocks:
            block_id = add_text_block(
                session, original, block.ordinal, block.start_offset, block.end_offset, block.text
            )
            session.execute(
                update(text_blocks)
                .where(text_blocks.c.block_id == block_id)
                .values(
                    block_type=block.block_type,
                    page_number=block.page_number,
                    json_pointer=block.json_pointer,
                )
            )
            attach_evidence_span(
                session,
                original,
                block.start_offset,
                block.end_offset,
                f"page:{block.page_number}"
                if block.page_number
                else (block.json_pointer or f"block:{block.ordinal}"),
                block.text,
                False,
                "public",
                None,
                NOW,
                block_id=block_id,
                verified_at=NOW,
            )
        register_source_revision_blocks(
            session, bulk, blocks, "public", None, NOW, attach_full_block_evidence=True
        )
    with Session(catalog_engine) as session:
        block_columns = [c for c in text_blocks.c if c.name not in {"block_id", "revision_id"}]
        evidence_columns = [
            c
            for c in evidence.c
            if c.name
            not in {
                "evidence_id",
                "block_id",
                "revision_id",
            }
        ]
        for columns, table, order in (
            (block_columns, text_blocks, text_blocks.c.ordinal),
            (evidence_columns, evidence, evidence.c.start_offset),
        ):
            expected = session.execute(
                select(*columns).where(table.c.revision_id == original).order_by(order)
            ).all()
            actual = session.execute(
                select(*columns).where(table.c.revision_id == bulk).order_by(order)
            ).all()
            assert actual == expected
        assert (
            session.scalar(
                select(func.count())
                .select_from(
                    evidence.join(text_blocks, evidence.c.block_id == text_blocks.c.block_id)
                )
                .where(evidence.c.revision_id == bulk, text_blocks.c.revision_id == bulk)
            )
            == 3
        )


def test_failure_in_second_batch_rolls_back_all_first_batch_rows(catalog_engine, tmp_path):
    revision_id = empty_revision(catalog_engine, ContentStore(tmp_path))
    inserts = 0

    def fail_second(connection, cursor, statement, parameters, context, executemany):
        nonlocal inserts
        if statement.startswith("INSERT INTO text_blocks"):
            inserts += 1
            if inserts == 2:
                raise OSError("fixture failure in the second bulk batch")

    event.listen(catalog_engine, "before_cursor_execute", fail_second)
    try:
        with Session(catalog_engine) as session, session.begin():
            with pytest.raises(OSError):
                register_source_revision_blocks(
                    session,
                    revision_id,
                    tuple(source_block(i) for i in range(501)),
                    "public",
                    None,
                    NOW,
                    attach_full_block_evidence=True,
                )
            for table in (text_blocks, evidence):
                assert (
                    session.scalar(
                        select(func.count())
                        .select_from(table)
                        .where(table.c.revision_id == revision_id)
                    )
                    == 0
                )
    finally:
        event.remove(catalog_engine, "before_cursor_execute", fail_second)


@pytest.mark.parametrize("failure", ["batch", "storage"])
def test_handler_failure_never_advances_cursor_or_publishes_partial_page(
    catalog_engine, tmp_path, failure
):
    release = {
        "id": 123,
        "tag_name": "v1.2.3",
        "name": "fixture release",
        "body": "source text",
        "html_url": "https://github.com/ollama/ollama/releases/tag/v1.2.3",
        "published_at": "2026-10-15T00:00:00Z",
        "draft": False,
        "prerelease": False,
        "extra": list(range(600)),
    }
    raw = json.dumps([release]).encode()
    store = ContentStore(tmp_path)
    original_store = store.store_bytes

    def reject_member(body):
        if failure == "storage" and body != raw:
            raise OSError("fixture member storage failure")
        return original_store(body)

    store.store_bytes = reject_member
    inserts = 0

    def fail_second(connection, cursor, statement, parameters, context, executemany):
        nonlocal inserts
        if failure == "batch" and statement.startswith("INSERT INTO text_blocks"):
            inserts += 1
            if inserts == 2:
                raise OSError("fixture second source batch failure")

    event.listen(catalog_engine, "before_cursor_execute", fail_second)
    try:
        job_id = queue(catalog_engine, "ollama_releases")
        handler = build_source_page_handler(
            store,
            fetcher=lambda url: FetchResult(url, 200, "application/json", raw),
            clock=lambda: NOW,
        )
        assert run(catalog_engine, job_id, handler) == "retry_wait"
        with Session(catalog_engine) as session:
            for table in (
                documents,
                document_revisions,
                text_blocks,
                evidence,
                source_page_receipts,
                source_cursors,
            ):
                assert session.scalar(select(func.count()).select_from(table)) == 0
        assert store.read_verified(hashlib.sha256(raw).hexdigest()) == raw
    finally:
        event.remove(catalog_engine, "before_cursor_execute", fail_second)


def test_history_and_replay_keep_old_evidence_and_new_revision_coordinates(
    catalog_engine, tmp_path
):
    store = ContentStore(tmp_path)
    first = save(catalog_engine, store, (paper(),))
    changed = replace(paper(), metadata={"version_label": "v2"})
    second = save(catalog_engine, store, (changed,), at=NOW + timedelta(seconds=8))
    repeated = save(catalog_engine, store, (changed,), at=NOW + timedelta(seconds=16))
    assert first.revision_ids != second.revision_ids == repeated.revision_ids
    assert repeated.new_revision_count == 0
    with Session(catalog_engine) as session:
        assert session.scalar(select(func.count()).select_from(evidence)) == 4
        assert session.scalar(select(func.count()).select_from(document_revisions)) == 2
        assert (
            session.scalar(
                select(document_revisions.c.is_current).where(
                    document_revisions.c.revision_id == first.revision_ids[0]
                )
            )
            is False
        )
