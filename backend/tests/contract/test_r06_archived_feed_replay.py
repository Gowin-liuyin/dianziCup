"""Real archived source responses are explicitly offline contract replay, never live proof."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ai_intel.ingestion.sources.arxiv_atom import parse_arxiv_atom
from ai_intel.ingestion.sources.trailofbits_rss import parse_trailofbits_rss

RUN = Path(__file__).resolve().parents[3] / "reports/runs/recovery_r06_feed_parsers_20261015"


def archived_payload(prefix: str) -> bytes:
    payload = (RUN / f"{prefix}.body").read_bytes()
    imports = json.loads((RUN / "sample_import.json").read_text(encoding="utf-8"))
    matching = [item for item in imports["files"] if item["destination"] == f"{prefix}.body"]
    assert len(matching) == 1
    assert matching[0]["sha256"] == hashlib.sha256(payload).hexdigest()
    assert matching[0]["bytes"] == len(payload)
    return payload


def test_offline_arxiv_atom_matches_original_two_papers_r06_c01() -> None:
    page = parse_arxiv_atom(archived_payload("doh_06_arxiv_ai_security"))
    assert (page.total_results, page.start_index, page.items_per_page) == (1065, 0, 2)
    assert len(page.records) == 2
    assert page.records[0].paper_id == "arxiv:2609.05903"
    assert page.records[0].version_label == "v2"
    assert page.records[0].published_at == "2026-09-05T05:56:41Z"
    assert page.records[0].modified_at == "2026-10-14T08:52:25Z"
    assert page.records[0].authors[0] == "Nanxi Li"
    assert page.records[0].full_text_fetched is False
    assert page.records[1].paper_id == "arxiv:2610.19452"
    assert page.records[1].version_label == "v1"
    assert page.records[1].title == (
        "Are You Reading the Right Thing? Rethinking Internal Signals "
        "for Prompt-Injection Detection"
    )


def test_curated_trailofbits_metadata_excerpt_is_not_original_response_r06_c01() -> None:
    payload = (RUN / "trailofbits_metadata_excerpt.xml").read_bytes()
    receipt = json.loads((RUN / "sample_storage_receipt.json").read_text(encoding="utf-8"))
    assert receipt["classification"] == "curated_metadata_only_excerpt_not_original_response"
    assert hashlib.sha256(payload).hexdigest() == receipt["excerpt_sha256"]
    assert receipt["excerpt_records"] == 20
    records = parse_trailofbits_rss(payload)
    assert len(records) == 20
    first = records[0]
    assert first.canonical_uri == (
        "https://blog.trailofbits.com/2026/10/14/package-managers-have-an-integrity-problem/"
    )
    assert first.title == "Package managers have an integrity problem"
    assert first.published_at == "2026-10-14T11:00:00Z"
    assert first.modified_at is None
    assert first.body_text == "I tested 25 of the most popular package managers"
    assert all(record.body_text is None for record in records[1:])
    assert all("article_body" in record.missing_fields for record in records)
    assert len({record.source_record_id for record in records}) == len(records)
