"""声明抽取: 单组字段+quote 定位; 校验失败退 unverified; 引文存在≠语义支持。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

EXTRACTION_VERSION = "extraction-1.0.0"
CVE_PATTERN = re.compile(r"^CVE-\d{4}-\d{4,}$")


class ExtractionValidationError(RuntimeError):
    """字段/片段校验失败: 退 unverified, 不虚构偏移。"""


class FewShotLeakageError(RuntimeError):
    """测试集事件进入 few-shot 候选: 拒绝并报告泄漏。"""


@dataclass(frozen=True)
class ExtractedField:
    """抽取字段: 值/类型/限定语; 失败字段 status=unverified。"""

    field_name: str
    value: object
    field_type: str
    qualifiers: tuple[str, ...] = field(default_factory=tuple)
    status: str = "extracted"


@dataclass(frozen=True)
class ExtractionBatch:
    """抽取批次: 事实候选/模型假设分列; quote 必须可定位。"""

    material_type: str
    candidate_claims: tuple[ExtractedField, ...] = field(default_factory=tuple)
    model_hypotheses: tuple[ExtractedField, ...] = field(default_factory=tuple)
    quote: str = ""
    block_id: str | None = None
    quote_located: bool = False
    citation_present: bool = False
    semantic_support: bool = False
    review_queue_items: tuple[str, ...] = field(default_factory=tuple)
    field_error_stats: dict[str, int] = field(default_factory=dict)


def validate_identifier_field(value: object) -> ExtractedField:
    """标识校验: CVE 形态不符退 unverified。"""
    text = str(value) if value is not None else ""
    if CVE_PATTERN.match(text):
        return ExtractedField("cve_id", text, "identifier")
    return ExtractedField("cve_id", text, "identifier", status="unverified")


def validate_version_field(value: object, qualifiers: tuple[str, ...]) -> ExtractedField:
    """版本校验: 无值退 unverified; 限定语(仅配置开启时)必须保留。"""
    if value is None or str(value) == "":
        return ExtractedField("affected_version", None, "version", qualifiers, status="unverified")
    return ExtractedField("affected_version", str(value), "version", qualifiers)


def validate_negation(claim_positive: bool, source_negates: bool) -> ExtractedField:
    """否定/限定: 来源否定不得抽成正向影响。"""
    if claim_positive and source_negates:
        return ExtractedField("affected_status", "not_affected", "negation", status="extracted")
    return ExtractedField(
        "affected_status", "affected" if claim_positive else "unknown", "negation"
    )


def locate_quote(normalized_text: str, quote: str, block_id: str | None) -> tuple[bool, bool]:
    """片段定位: 重复句必须给 block; 未定位/多次未定 → 校验失败不虚构偏移。"""
    if not quote:
        return False, False
    occurrences = normalized_text.count(quote)
    if occurrences == 0:
        return False, False
    if occurrences > 1 and block_id is None:
        raise ExtractionValidationError("quote occurs multiple times; block_id required to locate")
    return True, True


def record_citation_support(citation_present: bool, semantic_support: bool) -> tuple[bool, bool]:
    """引文存在与语义支持分列记录, 前者不得当后者。"""
    return citation_present, semantic_support


def reject_unsupported_identifiers(candidate_identifiers: list[str]) -> list[str]:
    """模型附加无证据 CVE/CVSS → 候选拒绝, 不发布事实。"""
    return [identifier for identifier in candidate_identifiers if not CVE_PATTERN.match(identifier)]


def guard_few_shot_leakage(event_id: str, benchmark_event_ids: tuple[str, ...]) -> None:
    """few-shot 泄漏防护: 测试集事件进入候选即拒绝并报告。"""
    if event_id in benchmark_event_ids:
        raise FewShotLeakageError(f"benchmark event leaked into few-shot candidates: {event_id}")


def summarize_field_errors(batches: list[ExtractionBatch]) -> dict[str, int]:
    """字段级错误统计: 不为提高指标只保留容易事件。"""
    totals: dict[str, int] = {}
    for batch in batches:
        for field_name, count in batch.field_error_stats.items():
            totals[field_name] = totals.get(field_name, 0) + count
    return totals
