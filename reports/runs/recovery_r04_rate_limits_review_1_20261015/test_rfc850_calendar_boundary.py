"""RFC850的50年边界是完整时间戳，不能只比较年份。"""

from datetime import UTC, datetime
from test_reviewer_probes import classify


def test_rfc850_more_than_fifty_years_date_maps_to_past():
    now = datetime(2026, 10, 15, 12, 34, 56, tzinfo=UTC)
    failure = classify(429, {"Retry-After": "Saturday, 16-Oct-76 00:00:00 GMT"}, now)
    assert failure.retry_after_seconds == 7 and failure.blocked is False, {
        "blocked": failure.blocked, "retry": failure.retry_after_seconds,
        "expected_rfc850_instant": "1976-10-16T00:00:00+00:00",
    }
