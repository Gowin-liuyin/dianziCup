"""The numeric timezone guard must cover every clock shape accepted by its downstream parser."""

from __future__ import annotations

import pytest
from test_independent_r06_feed_boundaries import item, rss

from ai_intel.ingestion.sources.feed import FeedParseError
from ai_intel.ingestion.sources.trailofbits_rss import parse_trailofbits_rss


@pytest.mark.parametrize("clock", ["07:00:0", "7:0:0"])
def test_invalid_timezone_does_not_bypass_guard_with_short_clock_fields(clock: str) -> None:
    payload = rss(item(extra=f"<pubDate>Wed, 14 Oct 2026 {clock} +1260</pubDate>"))
    with pytest.raises(FeedParseError):
        parse_trailofbits_rss(payload)
