"""Inspect the repaired numeric timezone guard with only synthetic related date inputs."""

from __future__ import annotations

import json

from test_independent_r06_feed_boundaries import item, rss

from ai_intel.ingestion.sources.feed import FeedParseError
from ai_intel.ingestion.sources.trailofbits_rss import parse_trailofbits_rss


def main() -> None:
    records = []
    for clock in ("07:00:00", "07:00:0", "7:0:0", "007:00:00"):
        date = f"Wed, 14 Oct 2026 {clock} +1260"
        try:
            value = parse_trailofbits_rss(rss(item(extra=f"<pubDate>{date}</pubDate>")))[0]
            records.append({"input": date, "actual_published_at": value.published_at})
        except FeedParseError as error:
            records.append({"input": date, "actual_error": str(error)})
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
