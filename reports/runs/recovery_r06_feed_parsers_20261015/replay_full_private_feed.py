"""Explicit private full-response replay; public contract tests use a labelled excerpt."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from ai_intel.ingestion.sources.trailofbits_rss import parse_trailofbits_rss


def main() -> None:
    payload = Path(sys.argv[1]).read_bytes()
    payload_hash = hashlib.sha256(payload).hexdigest()
    assert (
        payload_hash
        == "86a1faac2d08bd01281efcb72ebb6c57a9a4213aa61ebf055b77ceb093e476f0"
    )
    records = parse_trailofbits_rss(payload)
    assert len(records) == 20
    first = records[0]
    assert first.title == "Package managers have an integrity problem"
    assert first.published_at == "2026-10-14T11:00:00Z"
    assert first.modified_at is None
    assert first.body_text is not None and "I tested 25" in first.body_text
    assert all("article_body" in record.missing_fields for record in records)
    assert len({record.source_record_id for record in records}) == 20
    print(
        json.dumps(
            {
                "validation": "passed",
                "source_sha256": payload_hash,
                "source_bytes": len(payload),
                "records": len(records),
                "assertions": 8,
                "mode": "offline_private_original_not_live",
                "new_http_requests": 0,
                "article_fetches": 0,
                "licence": "unknown; full response not publicly packaged",
            }
        )
    )


if __name__ == "__main__":
    main()
