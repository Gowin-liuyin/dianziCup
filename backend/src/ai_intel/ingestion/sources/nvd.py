"""NVD CVE API 2.0实际wrapper与cvssData映射；网络重试仅由PG任务层负责。"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlsplit

NVD_CONNECTOR_NAME = "nvd-cve-api"
NVD_CONNECTOR_VERSION = "nvd-2.0.0"
NVD_SOURCE_SCHEMA_VERSION = "NVD_CVE:2.0"
SOURCE_TIMESTAMP_PATTERN = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-5][0-9]:[0-5][0-9]"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])?"
)


class NvdUnavailableError(RuntimeError):
    """上游状态由固定码传给唯一任务重试层，不回显错误正文。"""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__("nvd upstream request failed")


@dataclass(frozen=True)
class NvdMetric:
    """同类多机构评分并列，JSON路径定位到实际数值而非标题。"""

    metric_name: str
    score: float
    authority: str | None
    vector: str | None
    version: str | None
    json_pointer: str


@dataclass(frozen=True)
class NvdRecord:
    """原始响应另行版本保存；这里不推断无证据的机构、时间或分数。"""

    cve_id: str
    published_at: str | None
    last_modified_at: str | None
    description: str | None
    scores: tuple[tuple[str, float], ...] = field(default_factory=tuple)
    weaknesses: tuple[str, ...] = field(default_factory=tuple)
    source_schema_version: str = NVD_SOURCE_SCHEMA_VERSION
    metrics: tuple[NvdMetric, ...] = ()
    references: tuple[str, ...] = ()
    status: str | None = None
    raw_published_at: str | None = None
    raw_last_modified_at: str | None = None


@dataclass(frozen=True)
class NvdPage:
    records: tuple[NvdRecord, ...]
    start_index: int
    total_results: int
    next_start_index: int | None


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"invalid NVD {field_name}")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ValueError(f"invalid NVD {field_name}") from None
    if "\x00" in value:
        raise ValueError(f"invalid NVD {field_name}")
    return value if value.strip() else None


def _source_timestamp(value: object, field_name: str) -> str | None:
    """只输出有明示时区的时间；无时区原值另存，不当作宿主时区或抓取时间。"""
    text = _optional_text(value, field_name)
    if text is None:
        return None
    try:
        if SOURCE_TIMESTAMP_PATTERN.fullmatch(text) is None or text.endswith("-00:00"):
            raise ValueError
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(f"invalid NVD {field_name} timestamp") from None
    return parsed.astimezone(UTC).isoformat() if parsed.tzinfo is not None else None


def _parse_metrics(value: object, prefix: str) -> tuple[NvdMetric, ...]:
    if not isinstance(value, dict):
        raise ValueError("invalid NVD metrics")
    metrics: list[NvdMetric] = []
    for name, entries in value.items():
        if name not in ("cvssMetricV2", "cvssMetricV30", "cvssMetricV31", "cvssMetricV40"):
            continue
        if not isinstance(entries, list):
            raise ValueError("invalid NVD CVSS entries")
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict) or not isinstance(entry.get("cvssData"), dict):
                raise ValueError("missing NVD cvssData")
            details = entry["cvssData"]
            score = details.get("baseScore")
            if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 10:
                raise ValueError("invalid NVD CVSS score")
            metrics.append(
                NvdMetric(
                    metric_name=name,
                    score=float(score),
                    authority=_optional_text(entry.get("source"), "scoring source"),
                    vector=_optional_text(details.get("vectorString"), "CVSS vector"),
                    version=_optional_text(details.get("version"), "CVSS version"),
                    json_pointer=f"{prefix}/cve/metrics/{name}/{index}/cvssData/baseScore",
                )
            )
    return tuple(metrics)


def normalize_nvd_record(payload: dict[str, object], *, json_pointer: str = "") -> NvdRecord:
    """接受真实vulnerabilities数组中的{cve:...}项，不兼容伪造vulnerability wrapper。"""
    item = payload.get("cve")
    if not isinstance(item, dict):
        raise ValueError("missing NVD cve body")
    cve_id = item.get("id")
    if not isinstance(cve_id, str) or re.fullmatch(r"CVE-[0-9]{4}-[0-9]{4,}", cve_id) is None:
        raise ValueError("invalid NVD cve id")
    descriptions = item.get("descriptions", [])
    if not isinstance(descriptions, list):
        raise ValueError("invalid NVD descriptions")
    description = next(
        (
            entry["value"]
            for entry in descriptions
            if isinstance(entry, dict)
            and entry.get("lang") == "en"
            and isinstance(entry.get("value"), str)
            and entry["value"].strip()
        ),
        None,
    )
    metrics = _parse_metrics(item.get("metrics", {}), json_pointer)
    weaknesses: list[str] = []
    weakness_entries = item.get("weaknesses", [])
    if not isinstance(weakness_entries, list):
        raise ValueError("invalid NVD weaknesses")
    for entry in weakness_entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("description", []), list):
            raise ValueError("invalid NVD weakness description")
        for text in entry.get("description", []):
            if isinstance(text, dict) and isinstance(text.get("value"), str):
                weakness = _optional_text(text["value"], "weakness")
                if weakness is not None:
                    weaknesses.append(weakness)
    references: list[str] = []
    reference_entries = item.get("references", [])
    if not isinstance(reference_entries, list):
        raise ValueError("invalid NVD references")
    for entry in reference_entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("url"), str):
            raise ValueError("invalid NVD reference")
        link = _optional_text(entry["url"], "reference URL")
        if link is None or any(ord(character) <= 32 for character in link):
            raise ValueError("invalid NVD reference URL")
        try:
            parts = urlsplit(link)
            if (
                parts.scheme not in ("https", "http")
                or not parts.hostname
                or parts.username is not None
            ):
                raise ValueError("invalid NVD reference URL")
        except ValueError:
            raise ValueError("invalid NVD reference URL") from None
        references.append(link)
    return NvdRecord(
        cve_id=cve_id,
        published_at=_source_timestamp(item.get("published"), "published"),
        last_modified_at=_source_timestamp(item.get("lastModified"), "lastModified"),
        description=_optional_text(description, "description"),
        metrics=metrics,
        scores=tuple((metric.metric_name, metric.score) for metric in metrics),
        weaknesses=tuple(dict.fromkeys(weaknesses)),
        references=tuple(dict.fromkeys(references)),
        status=_optional_text(item.get("vulnStatus"), "vulnStatus"),
        raw_published_at=_optional_text(item.get("published"), "published"),
        raw_last_modified_at=_optional_text(item.get("lastModified"), "lastModified"),
    )


def normalize_nvd_page(payload: dict[str, object]) -> NvdPage:
    """真实分页元数据决定下一偏移；中途空页必须失败，不能静默宣称完成。"""
    entries = payload.get("vulnerabilities")
    start, total, size = (
        payload.get("startIndex"),
        payload.get("totalResults"),
        payload.get("resultsPerPage"),
    )
    if not isinstance(entries, list) or any(
        type(number) is not int or number < 0 for number in (start, total, size)
    ):
        raise ValueError("invalid NVD API page")
    if not isinstance(start, int) or not isinstance(total, int) or not isinstance(size, int):
        raise ValueError("invalid NVD pagination metadata")
    if size != len(entries) or len(entries) > 2000 or (not entries and start < total):
        raise ValueError("incomplete or unbounded NVD API page")
    if payload.get("format") != "NVD_CVE" or payload.get("version") != "2.0":
        raise ValueError("unsupported NVD API schema")
    records: list[NvdRecord] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError("invalid NVD vulnerability entry")
        records.append(normalize_nvd_record(entry, json_pointer=f"/vulnerabilities/{index}"))
    following = start + len(entries)
    if entries and following > total:
        raise ValueError("inconsistent NVD total count")
    return NvdPage(tuple(records), start, total, following if following < total else None)


def fetch_with_rate_limit_guard(fetch_once: Callable[[], dict[str, object]]) -> dict[str, object]:
    """一次调用后保留HTTP状态；429退避由PG调度，不再嵌套立即重试。"""
    response = fetch_once()
    if not isinstance(response, dict) or type(response.get("status_code")) is not int:
        raise ValueError("invalid NVD response envelope")
    status = response["status_code"]
    if not isinstance(status, int):
        raise ValueError("invalid NVD status")
    if status != 200:
        raise NvdUnavailableError(status)
    return response
