"""显式合成 HTTP 响应验证来源限流，不访问真实网络或冒充 live。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.infrastructure.network import FetchResult
from ai_intel.ingestion import source_jobs
from ai_intel.ingestion.cursor_repository import SourceCursorLease, SourceCursorRepository
from ai_intel.ingestion.source_jobs import (
    SourcePageRequest,
    _http_failure,
    build_source_page_handler,
)
from ai_intel.workers.executor import JobExecutionContext, JobExecutionError
from ai_intel.workers.jobs import retry_delay_seconds

NOW = datetime(2026, 10, 15, 0, 0, 0, 250000, tzinfo=UTC)
SOURCE_URL = "https://api.github.com/repos/vllm-project/vllm/security-advisories"


def response(status: int, headers: dict[str, str] | None = None) -> FetchResult:
    return FetchResult(
        SOURCE_URL, status, "application/json", b"synthetic diagnostics", headers or {}
    )


def limit_failure(
    status: int, headers: dict[str, str], *, now: datetime = NOW
) -> JobExecutionError:
    with pytest.raises(JobExecutionError) as caught:
        _http_failure(response(status, headers), clock=lambda: now)
    assert str(caught.value) == "source_rate_limited"
    assert caught.value.permanent is False
    return caught.value


def test_primary_quota_403_is_not_auth_denied() -> None:
    with pytest.raises(JobExecutionError) as caught:
        _http_failure(response(403, {"X-RateLimit-Remaining": "0"}))
    assert caught.value.error_code == "source_rate_limited"
    assert caught.value.blocked is True
    assert caught.value.retry_after_seconds is None


def test_long_retry_after_is_not_shortened_to_task_ceiling() -> None:
    with pytest.raises(JobExecutionError) as caught:
        _http_failure(response(429, {"Retry-After": "9000"}))
    assert caught.value.error_code == "source_rate_limited"
    assert caught.value.blocked is True
    assert caught.value.retry_after_seconds is None


def test_success_does_not_parse_headers_or_read_the_clock() -> None:
    clock = Mock(side_effect=AssertionError("successful response needs no retry deadline"))
    _http_failure(response(200, {"Retry-After": "synthetic-invalid-header"}), clock=clock)
    clock.assert_not_called()


@pytest.mark.parametrize(
    ("status", "headers"),
    [
        (401, {}),
        (401, {"Retry-After": "10", "x-ratelimit-remaining": "0"}),
        (403, {}),
        (403, {"x-ratelimit-remaining": "12"}),
        (403, {"x-ratelimit-remaining": "12", "x-ratelimit-reset": "invalid"}),
    ],
)
def test_auth_denial_remains_blocked_without_retry(status: int, headers: dict[str, str]) -> None:
    with pytest.raises(JobExecutionError) as caught:
        _http_failure(response(status, headers), clock=lambda: NOW)
    assert str(caught.value) == "source_auth_denied"
    assert caught.value.blocked is True
    assert caught.value.permanent is False
    assert caught.value.retry_after_seconds is None


@pytest.mark.parametrize("status", [403, 429])
@pytest.mark.parametrize(
    ("remaining", "reset", "expected_delay"),
    [("0", "1792022431", 31), ("00", "1792022401", 7), ("0", "1792022399", 7)],
)
def test_primary_limit_waits_until_reset_with_ceiling_and_poll_minimum(
    status: int, remaining: str, reset: str, expected_delay: int
) -> None:
    failed = limit_failure(status, {"X-RaTeLiMiT-ReMaInInG": remaining, "X-RateLimit-Reset": reset})
    assert failed.blocked is False
    assert failed.retry_after_seconds == expected_delay


@pytest.mark.parametrize("status", [403, 429])
@pytest.mark.parametrize(
    "headers",
    [
        {"x-ratelimit-remaining": "0"},
        {"x-ratelimit-remaining": "0", "Retry-After": "12"},
        {"x-ratelimit-remaining": "0", "x-ratelimit-reset": ""},
        {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "invalid"},
        {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "-1"},
        {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1.5"},
        {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1792022701"},
        {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "9" * 20},
        {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "9" * 5000},
        {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1792022430, 1792022431"},
        {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1792022430\r\nX-Other: value"},
        {"x-ratelimit-remaining": "0", "X-RateLimit-Remaining": "12"},
        {"x-ratelimit-remaining": "0", "X-RateLimit-Remaining": "0"},
        {
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": "1792022430",
            "X-RateLimit-Reset": "1792022431",
        },
        {"x-ratelimit-remaining": "0, 12", "x-ratelimit-reset": "1792022430"},
        {"x-ratelimit-remaining": "invalid", "Retry-After": "12"},
        {"x-ratelimit-remaining": "9" * 5000, "Retry-After": "12"},
    ],
    ids=lambda headers: "primary-headers-" + str(len(str(headers))),
)
def test_unknown_ambiguous_or_long_primary_limit_is_blocked(
    status: int, headers: dict[str, str]
) -> None:
    failed = limit_failure(status, headers)
    assert failed.blocked is True
    assert failed.retry_after_seconds is None


@pytest.mark.parametrize("status", [403, 429])
@pytest.mark.parametrize(
    ("header", "expected_delay"),
    [("0", 7), ("1", 7), ("7", 7), ("12", 12), ("0015", 15), ("300", 300), (" \t12\t ", 12)],
)
def test_delta_seconds_are_case_insensitive_and_keep_actual_wait(
    status: int, header: str, expected_delay: int
) -> None:
    failed = limit_failure(status, {"rEtRy-AfTeR": header})
    assert failed.blocked is False
    assert failed.retry_after_seconds == expected_delay


@pytest.mark.parametrize("status", [403, 429])
@pytest.mark.parametrize(
    ("header", "expected_delay"),
    [
        ("Thu, 15 Oct 2026 00:00:13 GMT", 13),
        ("Thursday, 15-Oct-26 00:00:13 GMT", 13),
        ("Thu Oct 15 00:00:13 2026", 13),
        ("Thu Oct  1 00:00:13 2026", 7),
        ("Thu, 15 Oct 2026 00:00:00 GMT", 7),
        ("Wed, 14 Oct 2026 23:59:59 GMT", 7),
        ("Thu, 15 Oct 2026 00:05:00 GMT", 300),
    ],
)
def test_http_date_waits_for_deadline_with_ceiling_and_poll_minimum(
    status: int, header: str, expected_delay: int
) -> None:
    failed = limit_failure(status, {"Retry-After": header})
    assert failed.blocked is False
    assert failed.retry_after_seconds == expected_delay


@pytest.mark.parametrize(
    "header",
    [
        "301",
        "9000",
        "9" * 20,
        "9" * 5000,
        " " * 129,
        "",
        "tomorrow",
        "NaN",
        "inf",
        "-1",
        "+1",
        "1.5",
        "１２",
        "12, 25",
        "12\r\nX-Other: value",
        "Thu, 15 Oct 2026 00:05:01 GMT",
        "Thu, 15 Oct 9999 00:00:00 GMT",
        "Wednesday, 15-Oct-70 00:00:13 GMT",
        "Thu, 99 Oct 2026 00:00:13 GMT",
        "Thu, 15 Oct 2026 00:00:13 UTC",
        "Thu, 15 Oct 2026 00:00:13 +0800",
        "Thu, 15 Oct 2026 00:00:13 GMT, 12",
        "Thu, 15 Oct 2026 00:00:13 GMT trailing",
        "synthetic-header-private-value",
    ],
    ids=lambda value: "invalid-retry-after-" + str(len(value)),
)
def test_invalid_ambiguous_or_long_retry_after_cannot_become_early_retry(header: str) -> None:
    failed = limit_failure(429, {"Retry-After": header})
    assert failed.blocked is True
    assert failed.retry_after_seconds is None


@pytest.mark.parametrize(
    "headers",
    [
        {"Retry-After": "12", "retry-after": "25"},
        {"Retry-After": "12", "retry-after": "12"},
        {"x" * 129: "ignored", "Retry-After": "12"},
        {**{f"x-synthetic-{index}": "ignored" for index in range(129)}, "Retry-After": "12"},
    ],
)
def test_duplicate_or_excessive_header_collection_is_bounded(headers: dict[str, str]) -> None:
    failed = limit_failure(429, headers)
    assert failed.blocked is True
    assert failed.retry_after_seconds is None


@pytest.mark.parametrize(
    ("reset", "retry_after", "expected_delay", "blocked"),
    [
        ("1792022425", "12", 25, False),
        ("1792022412", "25", 25, False),
        ("1792022701", "12", None, True),
        ("1792022412", "301", None, True),
    ],
)
def test_both_limit_deadlines_are_respected(
    reset: str, retry_after: str, expected_delay: int | None, blocked: bool
) -> None:
    failed = limit_failure(
        403,
        {"x-ratelimit-remaining": "0", "x-ratelimit-reset": reset, "Retry-After": retry_after},
    )
    assert failed.blocked is blocked
    assert failed.retry_after_seconds == expected_delay


def test_missing_retry_header_without_primary_quota_uses_existing_bounded_fallback() -> None:
    failed = limit_failure(429, {})
    assert failed.blocked is False
    assert failed.retry_after_seconds == 30


def test_http_date_compares_instants_across_clock_timezones() -> None:
    failed = limit_failure(
        429,
        {"Retry-After": "Thu, 15 Oct 2026 00:00:13 GMT"},
        now=NOW.astimezone(timezone(timedelta(hours=8))),
    )
    assert failed.retry_after_seconds == 13


def test_naive_clock_cannot_prove_a_safe_absolute_deadline() -> None:
    failed = limit_failure(
        429, {"Retry-After": "Thu, 15 Oct 2026 00:00:13 GMT"}, now=NOW.replace(tzinfo=None)
    )
    assert failed.blocked is True
    assert failed.retry_after_seconds is None


@pytest.mark.parametrize(
    ("status", "code", "permanent", "delay"),
    [
        (404, "source_client_error", True, None),
        (500, "source_server_error", False, 7),
        (503, "source_server_error", False, 7),
        (302, "source_unexpected_status", True, None),
    ],
)
def test_other_http_failures_keep_existing_safe_classification(
    status: int, code: str, permanent: bool, delay: int | None
) -> None:
    with pytest.raises(JobExecutionError) as caught:
        _http_failure(response(status), clock=lambda: NOW)
    assert str(caught.value) == code
    assert caught.value.blocked is False
    assert caught.value.permanent is permanent
    assert caught.value.retry_after_seconds == delay


def test_job_retry_delay_cannot_run_before_absolute_deadline() -> None:
    failed = limit_failure(429, {"Retry-After": "Thu, 15 Oct 2026 00:00:13 GMT"})
    delay = retry_delay_seconds(1, failed.retry_after_seconds)
    retry_at = NOW + timedelta(seconds=delay)
    assert retry_at >= datetime(2026, 10, 15, 0, 0, 13, tzinfo=UTC)
    assert delay == 13


def test_replayed_response_preserves_headers_and_absolute_deadline() -> None:
    headers = {"Retry-After": "Thu, 15 Oct 2026 00:00:13 GMT"}
    fetched = response(429, headers)
    delays = []
    for current in (NOW, NOW + timedelta(seconds=1)):
        with pytest.raises(JobExecutionError) as caught:
            _http_failure(fetched, clock=lambda current=current: current)
        delays.append(caught.value.retry_after_seconds)
    assert delays == [13, 12]
    assert fetched.redacted_headers == {"Retry-After": "Thu, 15 Oct 2026 00:00:13 GMT"}


def test_concurrent_classification_keeps_each_clock_and_response_independent() -> None:
    headers = {"Retry-After": "Thu, 15 Oct 2026 00:00:13 GMT"}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(limit_failure, 429, headers, now=NOW + timedelta(seconds=offset))
            for offset in (0, 1, 2, 3)
        ]
        failures = [future.result(timeout=5) for future in futures]
    assert [failed.retry_after_seconds for failed in failures] == [13, 12, 11, 10]
    assert all(not failed.blocked for failed in failures)
    assert headers == {"Retry-After": "Thu, 15 Oct 2026 00:00:13 GMT"}


@pytest.mark.parametrize("failure_kind", ["http-date", "quota-long", "storage"])
def test_source_handler_passes_clock_and_never_commits_a_failed_page(
    monkeypatch: pytest.MonkeyPatch, failure_kind: str
) -> None:
    lease = SourceCursorLease(
        "synthetic-source", "backfill", "synthetic-job", 1, {}, None, NOW, None, 0, NOW
    )
    repository = Mock(spec=SourceCursorRepository)
    repository.claim.return_value = lease
    monkeypatch.setattr(source_jobs, "SourceCursorRepository", Mock(return_value=repository))
    monkeypatch.setattr(
        source_jobs, "ensure_source_registration", Mock(return_value=lease.source_id)
    )
    persist = Mock(side_effect=OSError("synthetic storage unavailable"))
    enqueue = Mock(side_effect=AssertionError("failed page cannot enqueue continuation"))
    monkeypatch.setattr(source_jobs, "persist_source_response", persist)
    monkeypatch.setattr(source_jobs, "enqueue_source_page", enqueue)
    monkeypatch.setattr(source_jobs, "SourceResponseRecorder", Mock())
    if failure_kind == "http-date":
        fetched = response(429, {"Retry-After": "Thu, 15 Oct 2026 00:00:13 GMT"})
    elif failure_kind == "quota-long":
        fetched = response(403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1792022701"})
    else:
        fetched = response(200)
    fetcher = Mock(return_value=fetched)
    handler = build_source_page_handler(
        Mock(spec=ContentStorage), fetcher=fetcher, clock=lambda: NOW
    )
    request = SourcePageRequest(source_kind="vllm_vendor", window_end=NOW)
    context = JobExecutionContext("synthetic-job", "synthetic-worker", 1, None)
    with Session() as session:
        monkeypatch.setattr(session, "scalar", Mock(return_value=None))
        monkeypatch.setattr(session, "get_bind", Mock(return_value=Mock()))
        if failure_kind == "storage":
            with pytest.raises(OSError, match="synthetic storage unavailable"):
                handler(session, context, request.model_dump_json().encode())
            persist.assert_called_once()
        else:
            with pytest.raises(JobExecutionError) as caught:
                handler(session, context, request.model_dump_json().encode())
            assert caught.value.error_code == "source_rate_limited"
            assert caught.value.retry_after_seconds == (13 if failure_kind == "http-date" else None)
            assert caught.value.blocked is (failure_kind == "quota-long")
            persist.assert_not_called()
    fetcher.assert_called_once()
    repository.commit_page.assert_not_called()
    repository.release.assert_not_called()
    enqueue.assert_not_called()
