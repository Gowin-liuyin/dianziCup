"""Read-only recovery of the first replay's material checks; no handler or IO gateway."""

import hashlib
import json
import os
from pathlib import Path

from replay_real_release import RAW, RAW_SHA, RUN, independently_expected_blocks
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.ingestion.source_failure_models import source_response_receipts
from ai_intel.knowledge.models import (
    document_revisions, documents, evidence, source_cursors, source_page_receipts, text_blocks,
)

url = make_url(os.environ["TEST_DATABASE_URL"])
assert url.database == "test_dianzi_r06_catalog_bulk_20261016" and url.port == 25432
base = create_engine(url)
with base.connect() as connection:
    schemas = connection.execute(text(
        "SELECT nspname FROM pg_namespace WHERE nspname LIKE 'test_r06_bulk_real_1_%'"
    )).scalars().all()
assert len(schemas) == 1
schema = schemas[0]
isolated = url.update_query_dict({
    "options": f"-c search_path={schema} -c default_transaction_read_only=on"
})
engine = create_engine(isolated)
store = ContentStore(Path("D:/dianzi-local-evidence/r06-bulk-source-evidence") / schema)
raw = RAW.read_bytes()
assert len(raw) == 616865 and hashlib.sha256(raw).hexdigest() == RAW_SHA
members = json.loads(raw)
counts = {}
verified_blocks = 0
with Session(engine) as session:
    assert session.scalar(text("SHOW transaction_read_only")) == "on"
    assert session.scalar(text("SELECT version_num FROM alembic_version")) == (
        "0016_source_response_receipts"
    )
    for table in (documents, document_revisions, text_blocks, evidence,
                  source_page_receipts, source_response_receipts, source_cursors):
        counts[table.name] = session.scalar(select(func.count()).select_from(table))
    assert list(counts.values()) == [20, 20, 11827, 11827, 1, 1, 1]
    by_locator = {row["source_json_pointer"]: row for row in session.execute(
        select(document_revisions)
    ).mappings()}
    for index, member in enumerate(members):
        revision = by_locator["/" + str(index)]
        member_bytes = json.dumps(member, ensure_ascii=False, separators=(",", ":")).encode()
        digest = hashlib.sha256(member_bytes).hexdigest()
        assert revision["content_hash"] == digest and revision["source_response_hash"] == RAW_SHA
        assert store.read_verified(digest) == member_bytes
        assert revision["is_current"] is True and revision["visibility"] == "public"
        assert revision["tenant_id"] is None
        rows = session.execute(select(text_blocks, evidence).join(
            evidence, evidence.c.block_id == text_blocks.c.block_id
        ).where(text_blocks.c.revision_id == revision["revision_id"]).order_by(
            text_blocks.c.ordinal
        )).mappings().all()
        expected = independently_expected_blocks(member)
        assert len(rows) == len(expected)
        for row, (ordinal, start, end, pointer, quote) in zip(rows, expected, strict=True):
            quote_digest = hashlib.sha256(quote.encode()).hexdigest()
            assert (row["ordinal"], row["start_offset"], row["end_offset"], row["json_pointer"],
                    row["block_text"]) == (ordinal, start, end, pointer, quote)
            assert row["quote"] == quote and row["locator"] == pointer
            assert row["text_sha256"] == row["quote_sha256"] == quote_digest
            assert row["start_offset_1"] == start and row["end_offset_1"] == end
            assert row["revision_id_1"] == revision["revision_id"]
            assert row["supports_claim"] is False and row["visibility"] == "public"
            assert row["tenant_id"] is None and row["coordinate_version"] == "fulltext_unicode_v1"
            assert row["block_type"] == "json_field" and row["page_number"] is None
            assert row["verified_at"] == row["created_at"] == revision["ingested_at"]
        verified_blocks += len(rows)
    cursor = session.execute(select(source_cursors)).mappings().one()
    assert cursor["cursor_json"]["window_complete"] is True and cursor["lease_owner"] is None
    assert store.read_verified(RAW_SHA) == raw
record = {
    "mode": "read_only_post_failed_verifier", "schema": schema, "counts": counts,
    "independently_verified_blocks": verified_blocks, "handler_invocations": 0,
    "raw_sha256": RAW_SHA, "raw_bytes": len(raw), "handler_seconds": None,
    "time_measurement_limit": "first handler timing was not sealed before verifier assertion",
}
(RUN / "first_release_readonly_verified.json").write_text(json.dumps(record, indent=2))
print(json.dumps(record))
engine.dispose()
base.dispose()
