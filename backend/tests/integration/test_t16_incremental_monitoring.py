"""T16 增量监测集成验收测试: 覆盖 T16-C01—C06（注入式抓取, 真库不依赖）。"""

from __future__ import annotations

import pytest

from ai_intel.ingestion.scheduler import (
    AuthenticationStalledError,
    CursorCommitError,
    FetchPageResult,
    StreamState,
    commit_page_persisted,
    describe_collection_gaps,
    record_fetch_failure,
)


def make_state() -> StreamState:
    """构造 source+stream 租约状态。"""
    return StreamState(source_id="src-1", stream_name="advisories")


def test_multi_page_window_records_every_entry_and_advances_watermark_t16_c01() -> None:
    """T16-C01: 多页窗口每条原文有记录且水位推进到最新发布时间。"""
    state = make_state()
    stored: list[str] = []
    page1 = FetchPageResult(
        entries=({"entry_id": "e1", "published_at": "2021-01-01"},),
        next_cursor="c1",
        is_last_page=False,
    )
    page2 = FetchPageResult(
        entries=({"entry_id": "e2", "published_at": "2021-02-01"},),
        next_cursor=None,
        is_last_page=True,
    )
    assert (
        commit_page_persisted(
            state, page1, lambda entry: stored.append(str(entry["entry_id"])) or True
        )
        == 1
    )
    assert (
        commit_page_persisted(
            state, page2, lambda entry: stored.append(str(entry["entry_id"])) or True
        )
        == 1
    )
    assert stored == ["e1", "e2"]
    assert state.watermark_published_at == "2021-02-01"
    assert state.live_cursor is None


def test_interruption_on_page_two_recovers_without_duplicating_page_one_t16_c02() -> None:
    """T16-C02: 第 2 页中断恢复后补齐, 且不重复第 1 页业务结果(游标幂等)。"""
    state = make_state()
    stored: list[str] = []
    page1 = FetchPageResult(entries=({"entry_id": "e1"},), next_cursor="c1", is_last_page=False)
    commit_page_persisted(state, page1, lambda entry: stored.append(str(entry["entry_id"])) or True)
    assert state.live_cursor == "c1"
    recovery = make_state()
    recovery.live_cursor = state.live_cursor
    recovery.collected_entry_ids = list(state.collected_entry_ids)
    page2 = FetchPageResult(entries=({"entry_id": "e2"},), next_cursor=None, is_last_page=True)
    assert (
        commit_page_persisted(
            recovery, page2, lambda entry: stored.append(str(entry["entry_id"])) or True
        )
        == 1
    )
    assert stored == ["e1", "e2"]
    replay = FetchPageResult(entries=({"entry_id": "e1"},), next_cursor="c1", is_last_page=False)
    assert commit_page_persisted(state, replay, lambda entry: True) == 0
    assert stored == ["e1", "e2"]


def test_backfill_does_not_advance_live_watermark_t16_c03() -> None:
    """T16-C03: live 与 backfill 并行, 历史回补不推进实时水位。"""
    state = make_state()
    live_page = FetchPageResult(
        entries=({"entry_id": "e2", "published_at": "2021-06-01"},),
        next_cursor=None,
        is_last_page=True,
    )
    commit_page_persisted(state, live_page, lambda entry: True)
    assert state.watermark_published_at == "2021-06-01"
    backfill_page = FetchPageResult(
        entries=({"entry_id": "e0", "published_at": "2020-01-01"},),
        next_cursor="b1",
        is_last_page=False,
    )
    commit_page_persisted(state, backfill_page, lambda entry: True, is_backfill=True)
    assert state.watermark_published_at == "2021-06-01"
    assert state.backfill_cursor == "b1" and state.live_cursor is None


def test_late_revision_in_lookback_window_rediscovered_with_version_kept_t16_c04() -> None:
    """T16-C04: 迟到修订落在回看窗口被再次发现并保留版本(回看重扫)。"""
    state = make_state()
    page = FetchPageResult(
        entries=({"entry_id": "e1", "published_at": "2021-01-01"}, {"entry_id": "e2"}),
        next_cursor="c1",
        is_last_page=False,
    )
    commit_page_persisted(state, page, lambda entry: True, lookback_items=2)
    assert state.live_cursor == "c1"
    revision_page = FetchPageResult(
        entries=({"entry_id": "e1", "published_at": "2021-01-01", "revision": 2},),
        next_cursor="c2",
        is_last_page=False,
    )
    assert commit_page_persisted(state, revision_page, lambda entry: True, lookback_items=2) == 0
    assert state.collected_entry_ids.count("e1") == 1
    assert state.live_cursor == "c2"


def test_auth_rate_limit_and_parse_failures_have_distinct_recovery_t16_c05() -> None:
    """T15-C05/T16-C05: 401 停止、429 退避、解析失败隔离补采, 策略互不相同。"""
    state = make_state()
    assert record_fetch_failure(state, 429) == "backoff_retry"
    assert state.circuit_open is False and state.auth_stalled is False
    assert record_fetch_failure(state, None) == "quarantine_and_replay"
    assert record_fetch_failure(state, 401) == "auth_stopped" and state.auth_stalled is True
    with pytest.raises(AuthenticationStalledError):
        commit_page_persisted(
            state,
            FetchPageResult(entries=(), next_cursor=None, is_last_page=True),
            lambda entry: True,
        )
    breaker = make_state()
    assert record_fetch_failure(breaker, 500) == "quarantine_and_replay"
    assert record_fetch_failure(breaker, 500) == "quarantine_and_replay"
    assert record_fetch_failure(breaker, 500) == "circuit_open" and breaker.circuit_open is True
    with pytest.raises(CursorCommitError):
        commit_page_persisted(
            breaker,
            FetchPageResult(entries=(), next_cursor=None, is_last_page=True),
            lambda entry: True,
        )


def test_missing_published_at_and_gaps_reported_not_excluded_t16_c06() -> None:
    """T16-C06: 缺发布时间/漏采出现在报告分母与限制中, 不被静默排除、不填虚构数据。"""
    state = make_state()
    page = FetchPageResult(
        entries=({"entry_id": "e1"}, {"entry_id": "e2", "published_at": "2021-01-01"}),
        next_cursor=None,
        is_last_page=True,
    )
    state.quarantined_entry_ids.append("bad-1")
    commit_page_persisted(state, page, lambda entry: True)
    gaps = describe_collection_gaps(state)
    assert gaps["missing_published_at_ids"] == ["e1"]
    assert gaps["collected_count"] == 2
    assert gaps["quarantined_ids"] == ["bad-1"]
    assert gaps["gaps_reported_not_excluded"] is True
    assert state.watermark_published_at == "2021-01-01"
