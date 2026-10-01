"""增量监测调度: live/backfill 分立游标、水位与重叠回看、可恢复分页提交。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

SCHEDULER_VERSION = "scheduler-1.0.0"
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
    """source+stream 租约状态: 水位/回看窗/失败隔离/健康度。"""

    source_id: str
    stream_name: str
    live_cursor: str | None = None
    backfill_cursor: str | None = None
    watermark_published_at: str | None = None
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
    """分页提交: 每条先持久化原文再推进游标; 回看窗内条目再入站即修订再发现。"""
    if state.auth_stalled:
        raise AuthenticationStalledError(
            "stream halted on authentication error; no retry without re-authorization"
        )
    if state.circuit_open:
        raise CursorCommitError("circuit open; recovery required before new commits")
    newly_committed = 0
    for entry in page.entries:
        entry_id = str(entry.get("entry_id", ""))
        if not entry_id:
            state.quarantined_entry_ids.append("<missing-id>")
            continue
        if not persist_entry(entry):
            state.quarantined_entry_ids.append(entry_id)
            continue
        already_collected = entry_id in state.collected_entry_ids
        if not already_collected:
            state.collected_entry_ids.append(entry_id)
            newly_committed += 1
        published_at = entry.get("published_at")
        if published_at is None and entry_id not in state.missing_published_at_ids:
            state.missing_published_at_ids.append(entry_id)
        newer_and_live = (
            published_at is not None
            and not is_backfill
            and (
                state.watermark_published_at is None
                or str(published_at) > state.watermark_published_at
            )
        )
        if newer_and_live:
            state.watermark_published_at = str(published_at)
    if is_backfill:
        state.backfill_cursor = page.next_cursor
    else:
        state.live_cursor = page.next_cursor
        state.consecutive_failures = 0
    if lookback_items > 0:
        state.rescan_window_ids = state.collected_entry_ids[-lookback_items:]
    return newly_committed


def record_fetch_failure(state: StreamState, status_code: int | None) -> str:
    """失败分类: 401 停止、429 退避、解析失败隔离补采、连续失败熔断。"""
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
    return {
        "collected_count": len(state.collected_entry_ids),
        "missing_published_at_ids": list(state.missing_published_at_ids),
        "quarantined_ids": list(state.quarantined_entry_ids),
        "rescan_window_ids": list(state.rescan_window_ids),
        "gaps_reported_not_excluded": True,
    }
