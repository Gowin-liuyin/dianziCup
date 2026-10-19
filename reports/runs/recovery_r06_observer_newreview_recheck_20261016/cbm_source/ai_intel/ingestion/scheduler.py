"""显式 fixture 的增量调度判断；产品游标由 PostgreSQL repository 保存。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

SCHEDULER_VERSION = "scheduler-1.1.0"
DEFAULT_OVERLAP_LOOKBACK_ITEMS = 2


class CursorCommitError(RuntimeError):
    """原文未持久化不得提交游标; 条目必须可追踪。"""


class AuthenticationStalledError(RuntimeError):
    """认证错误单独停止, 不进入退避重试。"""


@dataclass(frozen=True)
class FetchPageResult:
    """单页抓取结果: 条目与页游标; 空页即窗口结束。"""

    entries: tuple[dict[str, object], ...]
    next_cursor: str | None
    is_last_page: bool


@dataclass
class StreamState:
    """隔离测试状态；必须显式 fixture_mode，不可替代数据库租约或分页回执。"""

    source_id: str
    stream_name: str
    fixture_mode: bool = False
    live_cursor: str | None = None
    backfill_cursor: str | None = None
    watermark_published_at: str | None = None
    pending_watermark_published_at: str | None = None
    collected_entry_ids: list[str] = field(default_factory=list)
    rescan_window_ids: list[str] = field(default_factory=list)
    quarantined_entry_ids: list[str] = field(default_factory=list)
    consecutive_failures: int = 0
    circuit_open: bool = False
    missing_published_at_ids: list[str] = field(default_factory=list)
    auth_stalled: bool = False


def commit_page_persisted(
    state: StreamState,
    page: FetchPageResult,
    persist_entry: Callable[[dict[str, object]], bool],
    is_backfill: bool = False,
    lookback_items: int = DEFAULT_OVERLAP_LOOKBACK_ITEMS,
) -> int:
    """fixture 页面全部持久化后更新状态；失败不能隔离后继续推进游标。"""
    _require_fixture(state)
    if type(lookback_items) is not int or lookback_items < 0:
        raise ValueError("nonnegative lookback_items required")
    if state.auth_stalled:
        raise AuthenticationStalledError(
            "stream halted on authentication error; no retry without re-authorization"
        )
    if state.circuit_open:
        raise CursorCommitError("circuit open; recovery required before new commits")
    entry_ids = [entry.get("entry_id") for entry in page.entries]
    if any(not isinstance(entry_id, str) or not entry_id.strip() for entry_id in entry_ids):
        raise CursorCommitError("page entry requires a valid entry_id")
    newly_committed = 0
    collected_entry_ids = list(state.collected_entry_ids)
    missing_published_at_ids = list(state.missing_published_at_ids)
    watermark_published_at = state.watermark_published_at
    pending_watermark_published_at = state.pending_watermark_published_at
    for entry in page.entries:
        entry_id = str(entry["entry_id"])
        if persist_entry(entry) is not True:
            raise CursorCommitError("page entry was not persisted")
        already_collected = entry_id in collected_entry_ids
        if not already_collected:
            collected_entry_ids.append(entry_id)
            newly_committed += 1
        published_at = entry.get("published_at")
        if published_at is None and entry_id not in missing_published_at_ids:
            missing_published_at_ids.append(entry_id)
        newer_and_live = (
            published_at is not None
            and not is_backfill
            and (
                pending_watermark_published_at is None
                or str(published_at) > pending_watermark_published_at
            )
        )
        if newer_and_live:
            pending_watermark_published_at = str(published_at)
    if not is_backfill and page.is_last_page and pending_watermark_published_at is not None:
        watermark_published_at = max(
            pending_watermark_published_at, watermark_published_at or pending_watermark_published_at
        )
        pending_watermark_published_at = None
    state.collected_entry_ids = collected_entry_ids
    state.missing_published_at_ids = missing_published_at_ids
    state.watermark_published_at = watermark_published_at
    state.pending_watermark_published_at = pending_watermark_published_at
    if is_backfill:
        state.backfill_cursor = page.next_cursor
    else:
        state.live_cursor = page.next_cursor
        state.consecutive_failures = 0
    state.rescan_window_ids = state.collected_entry_ids[-lookback_items:] if lookback_items else []
    return newly_committed


def _require_fixture(state: StreamState) -> None:
    if state.fixture_mode is not True:
        raise ValueError("in-memory scheduler requires explicit fixture_mode")


def record_fetch_failure(state: StreamState, status_code: int | None) -> str:
    """失败分类: 401 停止、429 退避、解析失败隔离补采、连续失败熔断。"""
    _require_fixture(state)
    if status_code in (401, 403):
        state.auth_stalled = True
        return "auth_stopped"
    if status_code == 429:
        state.consecutive_failures += 1
        return "backoff_retry"
    state.consecutive_failures += 1
    if state.consecutive_failures >= 3:
        state.circuit_open = True
        return "circuit_open"
    return "quarantine_and_replay"


def describe_collection_gaps(state: StreamState) -> dict[str, object]:
    """缺时间/漏采单列进报告分母与限制, 不被静默排除、不填虚构数据。"""
    _require_fixture(state)
    return {
        "data_mode": "fixture",
        "collected_count": len(state.collected_entry_ids),
        "missing_published_at_ids": list(state.missing_published_at_ids),
        "quarantined_ids": list(state.quarantined_entry_ids),
        "rescan_window_ids": list(state.rescan_window_ids),
        "gaps_reported_not_excluded": True,
    }
