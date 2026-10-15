"""Explicit fixture contract checks; synthetic candidates are not semantic live evidence."""

from datetime import UTC, datetime

import pytest

from ai_intel.retrieval.hybrid import reciprocal_rank_fusion
from ai_intel.retrieval.hybrid_contracts import HybridQuery


def test_rrf_uses_frozen_k60_and_deduplicates_each_branch() -> None:
    result = reciprocal_rank_fusion((("a", "a", "b"), ("b", "c")))
    assert result[0][0] == "b"
    assert dict(result)["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert dict(result)["a"] == pytest.approx(1 / 61)


@pytest.mark.parametrize("text", ["", "  ", "bad\x00query", "bad\ud800", "x" * 501])
def test_query_rejects_unsafe_text(text: str) -> None:
    with pytest.raises(ValueError):
        HybridQuery(text)


def test_time_filter_requires_aware_ordered_bounds() -> None:
    with pytest.raises(ValueError):
        HybridQuery("risk", available_before=datetime(2026, 1, 1))
    with pytest.raises(ValueError):
        HybridQuery(
            "risk",
            available_after=datetime(2026, 2, 1, tzinfo=UTC),
            available_before=datetime(2026, 1, 1, tzinfo=UTC),
        )
