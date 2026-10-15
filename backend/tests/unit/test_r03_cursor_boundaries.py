"""来源游标输入边界与显式 fixture 失败页回归；不连接数据库。"""

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from ai_intel.domain.access import AccessScope, Role
from ai_intel.ingestion.cursor_repository import (
    SourceCursorLease,
    SourceCursorRepository,
    make_page_key,
    page_request_digest,
)
from ai_intel.ingestion.scheduler import (
    CursorCommitError,
    FetchPageResult,
    StreamState,
    commit_page_persisted,
    describe_collection_gaps,
    record_fetch_failure,
)

NOW = datetime(2026, 10, 15, tzinfo=UTC)
SCOPE = AccessScope.for_authenticated_user("scheduler", None, Role.SYSTEM_ADMIN)


def lease() -> SourceCursorLease:
    return SourceCursorLease(
        "source", "live", "worker", 1, {}, None, NOW, None, 0, NOW + timedelta(seconds=60)
    )


def test_page_key_is_stable_for_json_order_and_separates_windows_and_streams() -> None:
    from dataclasses import replace

    first = make_page_key(lease(), {"a": 1, "b": "two"})
    assert len(first) == 64
    assert first == make_page_key(lease(), {"b": "two", "a": 1})
    assert first != make_page_key(replace(lease(), stream_kind="backfill"), {"a": 1, "b": "two"})
    assert first != make_page_key(
        replace(lease(), window_end=NOW - timedelta(days=1)), {"a": 1, "b": "two"}
    )


@pytest.mark.parametrize(
    "invalid",
    [float("nan"), float("inf"), object(), "x" * 65537],
    ids=["nan", "infinity", "non_json", "oversized"],
)
def test_page_key_rejects_invalid_or_unbounded_json_cursor(invalid: object) -> None:
    with pytest.raises(ValueError):
        make_page_key(lease(), {"position": invalid})


@pytest.mark.parametrize("seconds", [0, -1, 3601, True, 1.5])
def test_claim_rejects_unbounded_lease_before_database_access(seconds: object) -> None:
    with Session() as session:
        repository = SourceCursorRepository(session, SCOPE, "source", clock=lambda: NOW)
        with pytest.raises(ValueError):
            repository.claim(
                stream_kind="live",
                lease_owner="owner",
                window_start=None,
                window_end=NOW,
                lease_seconds=seconds,
            )


@pytest.mark.parametrize(
    "start,end",
    [
        (None, NOW.replace(tzinfo=None)),
        (NOW, NOW - timedelta(seconds=1)),
        (None, NOW + timedelta(seconds=1)),
    ],
)
def test_claim_rejects_naive_unordered_or_future_window_before_database_access(start, end) -> None:
    with Session() as session:
        repository = SourceCursorRepository(session, SCOPE, "source", clock=lambda: NOW)
        with pytest.raises(ValueError):
            repository.claim(
                stream_kind="live", lease_owner="owner", window_start=start, window_end=end
            )


@pytest.mark.parametrize(
    "action",
    [
        lambda state: commit_page_persisted(
            state, FetchPageResult((), None, True), lambda entry: True
        ),
        lambda state: record_fetch_failure(state, 401),
        describe_collection_gaps,
    ],
)
def test_in_memory_scheduler_requires_explicit_fixture_mode(action) -> None:
    with pytest.raises(ValueError, match="explicit fixture_mode"):
        action(StreamState("source", "stream"))


@pytest.mark.parametrize("entries", [({},), ({"entry_id": None},), ({"entry_id": " "},)])
def test_fixture_missing_entry_identity_does_not_mutate_page_or_invoke_callback(entries) -> None:
    state = StreamState("source", "stream", fixture_mode=True, live_cursor="before")
    original = asdict(state)
    called = []
    with pytest.raises(CursorCommitError):
        commit_page_persisted(
            state,
            FetchPageResult(entries, "after", False),
            lambda entry: called.append(entry) or True,
        )
    assert asdict(state) == original
    assert called == []


@pytest.mark.parametrize("failure", [False, "exception"])
def test_fixture_failed_second_entry_keeps_entire_page_state(failure) -> None:
    state = StreamState("source", "stream", fixture_mode=True, live_cursor="before")
    original = asdict(state)

    def persist(entry: dict[str, object]) -> bool:
        if entry["entry_id"] == "second":
            if failure == "exception":
                raise RuntimeError("fixture persistence interrupted")
            return False
        return True

    page = FetchPageResult(
        ({"entry_id": "first", "published_at": "2026-01-01"}, {"entry_id": "second"}),
        "after",
        False,
    )
    with pytest.raises((CursorCommitError, RuntimeError)):
        commit_page_persisted(state, page, persist)
    assert asdict(state) == original


def test_fixture_successful_watermark_waits_for_final_page() -> None:
    state = StreamState("source", "stream", fixture_mode=True)
    commit_page_persisted(
        state,
        FetchPageResult(({"entry_id": "first", "published_at": "2026-10-12"},), "next", False),
        lambda entry: True,
    )
    assert state.watermark_published_at is None
    assert state.pending_watermark_published_at == "2026-10-12"
    commit_page_persisted(state, FetchPageResult((), None, True), lambda entry: True)
    assert state.watermark_published_at == "2026-10-12"
    assert state.pending_watermark_published_at is None


def test_request_digest_normalizes_key_order_and_utc_but_retains_all_entry_fields() -> None:
    from datetime import timezone

    first = page_request_digest(
        lease(),
        {},
        {"next": 1},
        ({"entry_id": "entry", "unknown": {"b": 2, "a": "中文"}},),
        True,
        NOW,
    )
    equivalent = page_request_digest(
        lease(),
        {},
        {"next": 1},
        ({"unknown": {"a": "中文", "b": 2}, "entry_id": "entry"},),
        True,
        NOW.astimezone(timezone(timedelta(hours=8))),
    )
    changed = page_request_digest(
        lease(),
        {},
        {"next": 1},
        ({"entry_id": "entry", "unknown": {"b": 3, "a": "中文"}},),
        True,
        NOW,
    )
    assert first == equivalent and first != changed and len(first) == 64


@pytest.mark.parametrize(
    "invalid",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        NOW,
        Decimal("1.2"),
        object(),
        {1: "non-string-key"},
        ("not-json-list",),
        b"bytes",
    ],
)
def test_request_digest_rejects_non_json_fields_without_discarding_them(invalid) -> None:
    with pytest.raises(ValueError):
        page_request_digest(
            lease(), {}, {}, ({"entry_id": "entry", "unknown": invalid},), False, None
        )


@pytest.mark.parametrize("kind", ["depth", "nodes", "bytes", "cycle"])
def test_request_digest_rejects_unbounded_or_cyclic_input(kind: str) -> None:
    value: object = "leaf"
    if kind == "depth":
        for _ in range(17):
            value = [value]
    elif kind == "nodes":
        value = [0] * 10001
    elif kind == "bytes":
        value = "x" * 1048577
    else:
        cyclic = []
        cyclic.append(cyclic)
        value = cyclic
    with pytest.raises(ValueError):
        page_request_digest(
            lease(), {}, {}, ({"entry_id": "entry", "unknown": value},), False, None
        )


def test_entry_order_and_completion_and_watermark_are_independent_request_inputs() -> None:
    entries = ({"entry_id": "a"}, {"entry_id": "b"})
    fingerprints = {
        page_request_digest(lease(), {}, {}, entries, False, None),
        page_request_digest(lease(), {}, {}, entries[::-1], False, None),
        page_request_digest(lease(), {}, {}, entries, True, None),
        page_request_digest(lease(), {}, {}, entries, False, NOW),
    }
    assert len(fingerprints) == 4
