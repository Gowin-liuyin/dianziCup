"""Minimal independent synthetic checks for token location and retained stdlib interpretation."""

from __future__ import annotations

import pytest
from test_independent_r06_feed_boundaries import item, rss

from ai_intel.ingestion.sources.feed import FeedParseError
from ai_intel.ingestion.sources.trailofbits_rss import parse_trailofbits_rss


@pytest.mark.parametrize(
    "date",
    ["Wed, 14 Oct +1260 7:0:0 2026", "Wed, Oct 14 2026 7:0:0+1260"],
    ids=["year-zone-order", "month-day-attached-offset"],
)
def test_actual_invalid_timezone_token_is_rejected(date: str) -> None:
    with pytest.raises(FeedParseError):
        parse_trailofbits_rss(rss(item(extra=f"<pubDate>{date}</pubDate>")))


@pytest.mark.parametrize(
    "date",
    ["Wed, 14 Oct -0400 7:0:0 2026", "Wed, Oct 14 2026 7:0:0-0400"],
    ids=["year-zone-order", "month-day-attached-offset"],
)
def test_valid_matching_layout_keeps_original_utc_result(date: str) -> None:
    record = parse_trailofbits_rss(rss(item(extra=f"<pubDate>{date}</pubDate>")))[0]
    assert record.published_at == "2026-10-14T11:00:00Z"


def test_unknown_negative_zero_offset_is_not_promoted_to_utc() -> None:
    with pytest.raises(FeedParseError):
        parse_trailofbits_rss(rss(item(extra="<pubDate>Wed, 14 Oct 2026 7:0:0 -0000</pubDate>")))
