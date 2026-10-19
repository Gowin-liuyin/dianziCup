"""Independent RFC6901 leaf traversal and complete persisted-row verification."""

import hashlib
import json

from sqlalchemy import text


def expected_leaves(value):
    leaves = []
    pending = [("", value)]
    while pending:
        pointer, item = pending.pop()
        if isinstance(item, dict) and item:
            pairs = [(pointer + "/" + str(key).replace("~", "~0").replace("/", "~1"), child) for key, child in item.items()]
            pending.extend(reversed(pairs))
        elif isinstance(item, list) and item:
            pending.extend(reversed([(pointer + "/" + str(index), child) for index, child in enumerate(item)]))
        else:
            rendered = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False, allow_nan=False)
            leaves.append((pointer, pointer + ": " + rendered))
    return leaves


def verify(connection, store, raw, raw_digest):
    items = json.loads(raw)
    assert len(items) == 20
    revisions = list(connection.execute(text("SELECT d.document_id,d.source_id,d.kind,d.visibility document_visibility,d.tenant_id document_tenant,r.* FROM documents d JOIN document_revisions r USING(document_id)")).mappings())
    assert len(revisions) == 20
    by_locator = {row["source_json_pointer"]: row for row in revisions}
    assert set(by_locator) == {"/" + str(index) for index in range(20)}
    records, total = [], 0
    for index, item in enumerate(items):
        revision = by_locator["/" + str(index)]
        canonical = json.dumps(item, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
        digest = hashlib.sha256(canonical).hexdigest()
        assert revision["content_hash"] == digest
        assert store.read_verified(digest) == canonical
        assert revision["source_response_hash"] == raw_digest
        assert revision["document_visibility"] == revision["visibility"] == "public"
        assert revision["document_tenant"] is None and revision["tenant_id"] is None
        assert revision["kind"] == "repository_record" and revision["is_current"] is True
        assert revision["canonical_uri"] == item["html_url"]
        assert revision["source_metadata"]["canonical_uri"] == item["html_url"]
        assert revision["source_metadata"]["prerelease"] == item["prerelease"]
        assert revision["source_metadata"]["draft"] == item["draft"]
        leaves = expected_leaves(item)
        rows = list(connection.execute(text("SELECT b.*,e.evidence_id,e.revision_id evidence_revision,e.start_offset evidence_start,e.end_offset evidence_end,e.locator,e.quote,e.supports_claim,e.visibility,e.tenant_id,e.created_at,e.quote_sha256,e.verified_at,e.coordinate_version FROM text_blocks b JOIN evidence e ON e.block_id=b.block_id WHERE b.revision_id=:revision ORDER BY b.ordinal"), {"revision": revision["revision_id"]}).mappings())
        assert len(rows) == len(leaves)
        offset = 0
        block_ids, evidence_ids = set(), set()
        for ordinal, (row, (pointer, quote)) in enumerate(zip(rows, leaves, strict=True)):
            quote_digest = hashlib.sha256(quote.encode()).hexdigest()
            assert row["ordinal"] == ordinal
            assert row["block_text"] == row["quote"] == quote
            assert row["json_pointer"] == row["locator"] == pointer
            assert row["page_number"] is None and row["block_type"] == "json_field"
            assert row["start_offset"] == row["evidence_start"] == offset
            offset += len(quote)
            assert row["end_offset"] == row["evidence_end"] == offset
            assert row["text_sha256"] == row["quote_sha256"] == quote_digest
            assert row["revision_id"] == row["evidence_revision"] == revision["revision_id"]
            assert row["visibility"] == "public" and row["tenant_id"] is None
            assert row["supports_claim"] is False
            assert row["verified_at"] == row["created_at"] == revision["ingested_at"]
            assert row["coordinate_version"] == "fulltext_unicode_v1"
            block_ids.add(row["block_id"])
            evidence_ids.add(row["evidence_id"])
        assert len(block_ids) == len(evidence_ids) == len(leaves)
        total += len(leaves)
        records.append({"source_locator": "/" + str(index), "member_sha256": digest, "member_bytes": len(canonical), "independently_verified_leaf_count": len(leaves)})
    assert total == 11827
    assert store.read_verified(raw_digest) == raw
    return {"documents": len(revisions), "verified_blocks": total, "verified_evidence": total, "members": records, "comparison": "independent standard JSON iterative leaf traversal, original bytes and RFC6901 coordinates; all rows"}
