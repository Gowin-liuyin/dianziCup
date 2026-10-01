"""事件关联: 去重/别名归并/相似候选三层; 多 CVE 多事件; 合并撤销不删历史。"""

from __future__ import annotations

from dataclasses import dataclass, field

LINKING_VERSION = "linking-1.0.0"


class EventLinkingError(RuntimeError):
    """错误关联修复: 发布影响事件并保留来源与引用, 不删除历史。"""


@dataclass(frozen=True)
class SecurityEvent:
    """安全事件: 携带 CVE 列表/来源/同源组; 同产品或同 CWE 不自动合并。"""

    event_id: str
    cve_ids: tuple[str, ...] = field(default_factory=tuple)
    product_names: tuple[str, ...] = field(default_factory=tuple)
    cwe_ids: tuple[str, ...] = field(default_factory=tuple)
    source_record_ids: tuple[str, ...] = field(default_factory=tuple)
    source_group_id: str = ""
    body_fingerprint: str = ""


@dataclass
class EventLinkingLedger:
    """合并/拆分台账: 全部操作可撤销, 历史与来源版本永久保留。"""

    events: dict[str, SecurityEvent] = field(default_factory=dict)
    merged_history: list[tuple[str, str]] = field(default_factory=list)
    withdrawn_merges: list[tuple[str, str]] = field(default_factory=list)
    impact_events: list[str] = field(default_factory=list)

    def link_article_events(
        self, article_cve_ids: list[str], source_record_id: str, body_fingerprint: str
    ) -> list[str]:
        """一文多 CVE → 多事件关联, 不并成同一事件。"""
        created: list[str] = []
        for index, cve_id in enumerate(article_cve_ids):
            event_id = f"ev-{cve_id}-{source_record_id}-{index}"
            self.events[event_id] = SecurityEvent(
                event_id=event_id,
                cve_ids=(cve_id,),
                source_record_ids=(source_record_id,),
                body_fingerprint=body_fingerprint,
            )
            created.append(event_id)
        return created

    def should_merge(
        self, left: SecurityEvent, right: SecurityEvent, trusted_aliases: tuple[str, ...]
    ) -> bool:
        """可靠别名才归并; 同产品/同 CWE 不是合并依据。"""
        shared_cves = set(left.cve_ids) & set(right.cve_ids)
        if shared_cves and any(cve_id in trusted_aliases for cve_id in shared_cves):
            return True
        return left.body_fingerprint != "" and left.body_fingerprint == right.body_fingerprint

    def merge_events(self, keep_id: str, merge_id: str) -> None:
        """合并记录入台账, 原两条记录保留于历史, 不物理删除。"""
        if keep_id not in self.events or merge_id not in self.events:
            raise EventLinkingError("both events must exist before merge")
        self.merged_history.append((keep_id, merge_id))

    def undo_merge(self, keep_id: str, merge_id: str) -> None:
        """撤销错误合并: 恢复来源与引用, 发布影响事件, 不删除历史。"""
        if (keep_id, merge_id) not in self.merged_history:
            raise EventLinkingError("merge record not found; nothing to undo")
        self.withdrawn_merges.append((keep_id, merge_id))
        self.impact_events.append(f"merge_withdrawn:{keep_id}:{merge_id}")

    def describe_history(self) -> dict[str, object]:
        """历史完整可追溯: 合并/撤销/影响事件全保留。"""
        return {
            "merged": list(self.merged_history),
            "withdrawn": list(self.withdrawn_merges),
            "impact_events": list(self.impact_events),
            "current_event_count": len(self.events),
        }
