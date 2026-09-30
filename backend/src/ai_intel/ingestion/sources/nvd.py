"""NVD 连接器: 字段不兼容/429 明确失败或有限重试, 不假成功; 与 CVE 分别实现。"""

from __future__ import annotations

from dataclasses import dataclass, field

NVD_CONNECTOR_NAME = "nvd-cve-api"
NVD_CONNECTOR_VERSION = "nvd-1.0.0"
NVD_SOURCE_SCHEMA_VERSION = "nvd-schema-1"
MAX_RETRY_AFTER_429 = 2


class NvdUnavailableError(RuntimeError):
    """NVD 正文或权限不可得: 单独 blocked, 不影响 CVE 可用部分。"""


@dataclass(frozen=True)
class NvdRecord:
    """NVD 标准化记录: 评分多来源保留, 弱点枚举一并保留。"""

    cve_id: str
    published_at: str | None
    last_modified_at: str | None
    description: str | None
    scores: tuple[tuple[str, float], ...] = field(default_factory=tuple)
    weaknesses: tuple[str, ...] = field(default_factory=tuple)
    source_schema_version: str = NVD_SOURCE_SCHEMA_VERSION


def normalize_nvd_record(payload: dict[str, object]) -> NvdRecord:
    """标准化单条 NVD 漏洞; 缺 description 记 None 而非空串冒充。"""
    vulnerability = payload.get("vulnerability")
    if not isinstance(vulnerability, dict):
        raise ValueError("missing vulnerability wrapper")
    item = vulnerability.get("cve")
    if not isinstance(item, dict):
        raise ValueError("missing cve body")
    cve_id = item.get("id")
    if not isinstance(cve_id, str):
        raise ValueError("missing cve id")
    description = None
    descriptions = item.get("descriptions", [])
    if isinstance(descriptions, list):
        for entry in descriptions:
            if (
                isinstance(entry, dict)
                and entry.get("lang") == "en"
                and isinstance(entry.get("value"), str)
            ):
                description = str(entry["value"])
                break
    scores: list[tuple[str, float]] = []
    metrics = item.get("metrics", {})
    if isinstance(metrics, dict):
        for metric_name, entries in metrics.items():
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict) and isinstance(entry.get("baseScore"), (int, float)):
                        scores.append((str(metric_name), float(entry["baseScore"])))
    weaknesses: list[str] = []
    weaknesses_raw = item.get("weaknesses", [])
    if isinstance(weaknesses_raw, list):
        for weakness in weaknesses_raw:
            if isinstance(weakness, dict):
                for description_entry in weakness.get("description", []):
                    if isinstance(description_entry, dict) and isinstance(
                        description_entry.get("value"), str
                    ):
                        weaknesses.append(str(description_entry["value"]))
    return NvdRecord(
        cve_id=cve_id,
        published_at=str(item["published"]) if item.get("published") is not None else None,
        last_modified_at=str(item["lastModified"])
        if item.get("lastModified") is not None
        else None,
        description=description,
        scores=tuple(scores),
        weaknesses=tuple(weaknesses),
    )


def fetch_with_rate_limit_guard(fetch_once: object) -> dict[str, object]:
    """429 有限重试后明确失败; 字段不兼容不假成功。"""
    for _attempt in range(MAX_RETRY_AFTER_429 + 1):
        response = fetch_once()  # type: ignore[operator]
        if not isinstance(response, dict):
            raise ValueError("response must be an object")
        if response.get("status_code") == 429:
            continue
        if response.get("status_code") != 200:
            raise NvdUnavailableError(f"nvd unavailable: {response.get('status_code')}")
        return response
    raise NvdUnavailableError("nvd rate limited persistently (429)")
