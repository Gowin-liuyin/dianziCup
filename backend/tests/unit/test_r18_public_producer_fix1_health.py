"""Timestamp order and ties determine current health while history remains independent."""

from datetime import UTC, datetime, timedelta

import pytest

from ai_intel.api.public_extension_reads import derive_source_health

NOW = datetime(2026, 10, 16, 15, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("observations", "expected"),
    [
        ((), "never_polled"),
        (((NOW, "unknown"),), "unknown"),
        (((NOW, "failed"), (NOW + timedelta(seconds=1), "healthy")), "healthy"),
        (((NOW, "healthy"), (NOW + timedelta(seconds=1), "failed")), "failed"),
        (((NOW, "healthy"), (NOW + timedelta(seconds=1), "partial")), "partial"),
        (((NOW, "healthy"), (NOW, "failed")), "partial"),
        (((NOW, "failed"), (NOW, "failed")), "failed"),
    ],
)
def test_source_health_uses_latest_observation_and_conservative_ties(observations, expected):
    assert derive_source_health(observations) == expected
