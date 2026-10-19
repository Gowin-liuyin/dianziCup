"""Read the private original RSS once; emit only its digest and metadata assertion outcomes."""

from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path
from unittest.mock import patch

from ai_intel.ingestion.sources.trailofbits_rss import parse_trailofbits_rss

PRIVATE_SOURCE = Path(
    "C:/Users/yinha/.codex/worktrees/r06-src/dianzi/reports/runs/recovery_r06_source_preparation_20261015/doh_05_trailofbits_feed.body"
)
EXCERPT = Path(
    "D:/wt/r06-feed-review-recheck2/reports/runs/recovery_r06_feed_parsers_20261015/trailofbits_metadata_excerpt.xml"
)


def forbid_network(*args: object, **kwargs: object) -> None:
    raise AssertionError("private replay must remain offline")


def main() -> None:
    payload = PRIVATE_SOURCE.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    assert len(payload) == 991606
    assert digest == "86a1faac2d08bd01281efcb72ebb6c57a9a4213aa61ebf055b77ceb093e476f0"
    with (
        patch.object(socket, "socket", forbid_network),
        patch.object(socket, "getaddrinfo", forbid_network),
        patch.object(socket, "create_connection", forbid_network),
    ):
        records = parse_trailofbits_rss(payload)
        excerpt_records = parse_trailofbits_rss(EXCERPT.read_bytes())
    assert len(records) == 20
    assert len({record.source_record_id for record in records}) == 20
    assert (
        records[0].canonical_uri
        == "https://blog.trailofbits.com/2026/10/14/package-managers-have-an-integrity-problem/"
    )
    assert records[0].title == "Package managers have an integrity problem"
    assert records[0].published_at == "2026-10-14T11:00:00Z"
    assert all(record.modified_at is None for record in records)
    assert all("article_body" in record.missing_fields for record in records)
    assert all(record.body_text is not None for record in records)
    assert [
        (record.source_record_id, record.canonical_uri, record.title, record.published_at)
        for record in records
    ] == [
        (record.source_record_id, record.canonical_uri, record.title, record.published_at)
        for record in excerpt_records
    ]
    assert all(
        record.canonical_uri.startswith("https://blog.trailofbits.com/") for record in records
    )
    print(
        json.dumps(
            {
                "mode": "private_original_offline_metadata_replay",
                "original_bytes": len(payload),
                "original_sha256": digest,
                "items": len(records),
                "metadata_assertions": 10,
                "integrity_assertions": 2,
                "network_calls": 0,
                "full_description_copied_or_logged": False,
                "licence_status": "unknown",
                "full_article_fetch": False,
            }
        )
    )


if __name__ == "__main__":
    main()
