"""Offline fixed-handler load replay; public source bytes stay outside the checkout."""

import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema

from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.network import FetchResult
from ai_intel.ingestion import source_jobs
from ai_intel.ingestion.source_failure_models import source_response_receipts
from ai_intel.ingestion.source_jobs import SOURCE_JOB_TYPE, SourcePageRequest, enqueue_source_page
from ai_intel.knowledge.models import (
    document_revisions, documents, evidence, source_cursors, source_page_receipts, text_blocks,
)
from ai_intel.workers.executor import execute_job

RUN = Path(__file__).resolve().parent
RAW = Path("D:/dianzi-local-evidence/recovery_r06_live_segment_8a_20261016/release_raw.bin")
RAW_SHA = "25e00623a07dcafe8d8d6b3535e400e078ef758e965742a37fe76d5186bb69f7"


def independently_expected_blocks(document):
    pending = [("", document)]
    result = []
    offset = 0
    while pending:
        pointer, value = pending.pop()
        if isinstance(value, dict) and value:
            pending.extend(reversed([
                (pointer + "/" + key.replace("~", "~0").replace("/", "~1"), item)
                for key, item in value.items()
            ]))
        elif isinstance(value, list) and value:
            pending.extend(reversed([
                (pointer + "/" + str(index), item) for index, item in enumerate(value)
            ]))
        else:
            rendered = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            quote = pointer + ": " + rendered
            result.append((len(result), offset, offset + len(quote), pointer, quote))
            offset += len(quote)
    return result


def main():
    iteration = int(sys.argv[1])
    assert iteration in (1, 2)
    raw = RAW.read_bytes()
    assert len(raw) == 616865 and hashlib.sha256(raw).hexdigest() == RAW_SHA
    members = json.loads(raw)
    assert len(members) == 20
    expectations = [independently_expected_blocks(member) for member in members]
    assert sum(map(len, expectations)) == 11827
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert url.port == 25432 and url.database == "test_dianzi_r06_catalog_bulk_20261016"
    base = create_engine(url)
    schema = "test_r06_bulk_real_" + str(iteration) + "_" + uuid4().hex
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = url.update_query_dict({
        "options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=5000"
    })
    run_migrations(isolated.render_as_string(hide_password=False), "0016")
    engine = create_engine(isolated)
    store_path = Path("D:/dianzi-local-evidence/r06-bulk-source-evidence") / schema
    store = ContentStore(store_path)
    now = lambda: datetime.now(UTC)
    with Session(engine) as session, session.begin():
        job_id = enqueue_source_page(session, SourcePageRequest(
            source_kind="ollama_releases", window_end=now() - timedelta(seconds=1),
            remaining_pages=1,
        ), now())
    fetches = 0

    def read(url):
        nonlocal fetches
        assert url.startswith("https://api.github.com/repos/ollama/ollama/releases?")
        fetches += 1
        return FetchResult(url, 200, "application/json", raw, {})

    handler = source_jobs.build_source_page_handler(store, fetcher=read, clock=now)
    sql_calls = 0
    executemany_calls = 0
    batch_sizes = []

    def count_sql(connection, cursor, statement, parameters, context, executemany):
        nonlocal sql_calls, executemany_calls
        sql_calls += 1
        if executemany:
            executemany_calls += 1
            batch_sizes.append(len(parameters))

    event.listen(engine, "before_cursor_execute", count_sql)
    persist = source_jobs.persist_catalog_documents
    persist_seconds = []

    def measured_persist(*args, **kwargs):
        start = time.perf_counter()
        try:
            return persist(*args, **kwargs)
        finally:
            persist_seconds.append(time.perf_counter() - start)

    source_jobs.persist_catalog_documents = measured_persist
    handler_seconds = []

    def measured_handler(*args):
        start = time.perf_counter()
        try:
            return handler(*args)
        finally:
            handler_seconds.append(time.perf_counter() - start)

    started_at = now().isoformat()
    start_wall, start_cpu = time.perf_counter(), time.process_time()
    outcome = execute_job(engine, job_id, "fixture-real-raw-worker", {
        SOURCE_JOB_TYPE: measured_handler,
    }, clock=now)
    execute_seconds = time.perf_counter() - start_wall
    cpu_seconds = time.process_time() - start_cpu
    event.remove(engine, "before_cursor_execute", count_sql)
    (RUN / f"fixed_real_release_{iteration}_handler.json").write_text(json.dumps({
        "iteration": iteration, "schema": schema, "started_at": started_at,
        "ended_at": now().isoformat(), "outcome": outcome,
        "handler_seconds": handler_seconds[0], "execute_seconds": execute_seconds,
        "persist_seconds": persist_seconds[0], "cpu_seconds": cpu_seconds,
        "sql_calls": sql_calls, "executemany_calls": executemany_calls,
    }, indent=2))
    assert outcome == "succeeded" and fetches == 1
    assert handler_seconds[0] < 35 and execute_seconds < 35
    assert batch_sizes and max(batch_sizes) <= 500
    count_by_table = {}
    hashes = []
    with Session(engine) as session:
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0016_source_response_receipts"
        )
        for table in (documents, document_revisions, text_blocks, evidence,
                      source_page_receipts, source_response_receipts, source_cursors):
            count_by_table[table.name] = session.scalar(select(func.count()).select_from(table))
        assert list(count_by_table.values()) == [20, 20, 11827, 11827, 1, 1, 1]
        revisions = session.execute(select(document_revisions)).mappings().all()
        by_locator = {row["source_json_pointer"]: row for row in revisions}
        for index, (member, expected) in enumerate(zip(members, expectations, strict=True)):
            revision = by_locator["/" + str(index)]
            member_bytes = json.dumps(member, ensure_ascii=False, separators=(",", ":")).encode()
            expected_hash = hashlib.sha256(member_bytes).hexdigest()
            assert revision["content_hash"] == expected_hash
            assert revision["source_response_hash"] == RAW_SHA
            assert revision["is_current"] is True and revision["visibility"] == "public"
            assert revision["tenant_id"] is None
            assert store.read_verified(expected_hash) == member_bytes
            rows = session.execute(select(text_blocks, evidence).join(
                evidence, evidence.c.block_id == text_blocks.c.block_id
            ).where(text_blocks.c.revision_id == revision["revision_id"]).order_by(
                text_blocks.c.ordinal
            )).mappings().all()
            assert len(rows) == len(expected)
            for row, (ordinal, start, end, pointer, quote) in zip(rows, expected, strict=True):
                digest = hashlib.sha256(quote.encode()).hexdigest()
                assert (row["ordinal"], row["start_offset"], row["end_offset"],
                        row["json_pointer"], row["block_text"]) == (ordinal, start, end, pointer, quote)
                assert row["text_sha256"] == row["quote_sha256"] == digest
                assert row["quote"] == quote and row["locator"] == pointer
                assert row["start_offset_1"] == start and row["end_offset_1"] == end
                assert row["revision_id_1"] == revision["revision_id"]
                assert row["supports_claim"] is False and row["visibility"] == "public"
                assert row["tenant_id"] is None and row["coordinate_version"] == "fulltext_unicode_v1"
                assert row["block_type"] == "json_field" and row["page_number"] is None
                assert row["verified_at"] == row["created_at"] == revision["ingested_at"]
            hashes.append({"source_locator": "/" + str(index), "content_sha256": expected_hash,
                           "block_count": len(expected)})
        cursor = session.execute(select(source_cursors)).mappings().one()
        assert cursor["cursor_json"]["window_complete"] is True and cursor["lease_owner"] is None
        receipt = session.execute(select(source_response_receipts)).mappings().one()
        assert receipt["response_content_hash"] == RAW_SHA
        assert store.read_verified(RAW_SHA) == raw
    record = {
        "iteration": iteration, "mode": "fixture_offline_public_raw_load",
        "started_at": started_at, "ended_at": now().isoformat(), "schema": schema,
        "raw_path": str(RAW), "raw_sha256": RAW_SHA, "raw_bytes": len(raw),
        "handler_seconds": handler_seconds[0], "execute_seconds": execute_seconds,
        "persist_seconds": persist_seconds[0], "cpu_seconds": cpu_seconds,
        "sql_calls": sql_calls, "executemany_calls": executemany_calls,
        "batch_sizes": batch_sizes, "counts": count_by_table,
        "independently_verified_blocks": 11827, "members": hashes,
        "http_requests": 0, "model_requests": 0, "asset_requests": 0,
        "fixture_fetches": fetches, "headers": {}, "pagination_live": "not_run",
        "outcome": outcome, "cas_path": str(store_path), "lease_seconds_unchanged": 60,
    }
    (RUN / f"fixed_real_release_{iteration}.json").write_text(json.dumps(record, indent=2))
    print(json.dumps({key: record[key] for key in (
        "iteration", "handler_seconds", "execute_seconds", "persist_seconds", "cpu_seconds",
        "sql_calls", "executemany_calls", "counts", "outcome",
    )}))
    engine.dispose()
    base.dispose()


if __name__ == "__main__":
    main()
