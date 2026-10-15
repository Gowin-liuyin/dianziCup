"""Publish only a labelled metadata excerpt; retain complete unknown-licence RSS privately."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
PRIVATE = Path(
    "D:/dianzi-runtime-cache/01a13a70-858c-7d92-8070-0b2693ad7fc4/r06-feed-replay/20261015/doh_05_trailofbits_feed.body"
)
EXPECTED_HASH = "86a1faac2d08bd01281efcb72ebb6c57a9a4213aa61ebf055b77ceb093e476f0"
SHORT_QUOTE = "I tested 25 of the most popular package managers"


def main() -> None:
    raw = PRIVATE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED_HASH:
        raise ValueError("private original RSS hash mismatch")
    original = ElementTree.fromstring(raw)
    channel = original.find("channel")
    assert channel is not None
    excerpt = ElementTree.Element("rss", version="2.0")
    excerpt_channel = ElementTree.SubElement(excerpt, "channel")
    ElementTree.SubElement(excerpt_channel, "title").text = "The Trail of Bits Blog"
    ElementTree.SubElement(
        excerpt_channel, "link"
    ).text = "https://blog.trailofbits.com/"
    ElementTree.SubElement(
        excerpt_channel, "description"
    ).text = "Explicit metadata-only excerpt for offline contract tests; not original RSS response."
    items = channel.findall("item")
    for index, original_item in enumerate(items):
        item = ElementTree.SubElement(excerpt_channel, "item")
        for field in ("title", "link", "pubDate", "guid"):
            source_field = original_item.find(field)
            if source_field is not None:
                ElementTree.SubElement(item, field).text = source_field.text
        if index == 0:
            assert SHORT_QUOTE in original_item.findtext("description", "")
            ElementTree.SubElement(item, "description").text = SHORT_QUOTE
    excerpt_bytes = ElementTree.tostring(
        excerpt, encoding="utf-8", xml_declaration=True
    )
    output = RUN / "trailofbits_metadata_excerpt.xml"
    if output.exists():
        raise FileExistsError(output)
    output.write_bytes(excerpt_bytes)
    receipt = {
        "recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(
            timespec="seconds"
        ),
        "original_private_path": str(PRIVATE),
        "original_sha256": EXPECTED_HASH,
        "original_bytes": len(raw),
        "original_licence": "unknown; not publicly packaged",
        "original_source_preparation_remains_unchanged": True,
        "excerpt_path": output.name,
        "excerpt_sha256": hashlib.sha256(excerpt_bytes).hexdigest(),
        "excerpt_bytes": len(excerpt_bytes),
        "excerpt_records": len(items),
        "classification": "curated_metadata_only_excerpt_not_original_response",
        "excerpt_fields": ["title", "link", "pubDate", "guid"],
        "excerpt_short_quote_words": len(SHORT_QUOTE.split()),
        "abstract_full_original_atom": "CC0 metadata from source preparation; no paper PDF",
    }
    (RUN / "sample_storage_receipt.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
