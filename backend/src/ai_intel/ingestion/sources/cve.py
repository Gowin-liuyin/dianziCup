"""CVE 连接器: discover/fetch/normalize, 保留标识/状态/日期/描述/评分/引用。"""

from __future__ import annotations

from dataclasses import dataclass, field

CVE_CONNECTOR_NAME = "cve-list"
CVE_CONNECTOR_VERSION = "cve-1.0.0"
CVE_SOURCE_SCHEMA_VERSION = "cve-schema-1"
MAX_PAGES = 50


class ConnectorContractError(RuntimeError):
    """契约失败: 字段不兼容或分页异常, 明确失败而非假成功。"""


@dataclass(frozen=True)
class CveRecord:
    """标准化 CVE 记录: 多来源评分并列保留, 不只留最高分。"""

    cve_id: str
    state: str
    published_at: str | None
    modified_at: str | None
    description: str | None
    scores: tuple[tuple[str, float], ...] = field(default_factory=tuple)
    references: tuple[str, ...] = field(default_factory=tuple)
    source_schema_version: str = CVE_SOURCE_SCHEMA_VERSION
    missing_fields: tuple[str, ...] = field(default_factory=tuple)


def normalize_cve_record(payload: dict[str, object]) -> CveRecord:
    """标准化单条 CVE: 缺字段明确记 missing, 不编造默认值; rejected 状态如实保留。"""
    metadata = payload.get("cveMetadata")
    if not isinstance(metadata, dict):
        raise ConnectorContractError("missing cveMetadata")
    cve_id = metadata.get("cveId")
    if not isinstance(cve_id, str) or not cve_id.startswith("CVE-"):
        raise ConnectorContractError("invalid cveId")
    state = str(metadata.get("state", "UNKNOWN"))
    missing: list[str] = []
    descriptions: list[str] = []
    scores: list[tuple[str, float]] = []
    references: list[str] = []
    containers = payload.get("containers")
    if isinstance(containers, dict):
        cna = containers.get("cna")
        if isinstance(cna, dict):
            for entry in cna.get("descriptions", []):
                if isinstance(entry, dict) and isinstance(entry.get("value"), str):
                    descriptions.append(str(entry["value"]))
            metrics = cna.get("metrics", [])
            if isinstance(metrics, list):
                for metric in metrics:
                    if not isinstance(metric, dict):
                        continue
                    for scoring_name, scoring in metric.items():
                        if isinstance(scoring, dict) and isinstance(
                            scoring.get("baseScore"), (int, float)
                        ):
                            scores.append((str(scoring_name), float(scoring["baseScore"])))
            for reference in cna.get("references", []):
                if isinstance(reference, dict) and isinstance(reference.get("url"), str):
                    references.append(str(reference["url"]))
        else:
            missing.append("containers.cna")
    else:
        missing.append("containers")
    if not descriptions:
        missing.append("description")
    if not scores:
        missing.append("metrics")
    published_at = metadata.get("datePublished")
    modified_at = metadata.get("dateUpdated")
    if published_at is None:
        missing.append("datePublished")
    if modified_at is None:
        missing.append("dateUpdated")
    return CveRecord(
        cve_id=cve_id,
        state=state,
        published_at=str(published_at) if published_at is not None else None,
        modified_at=str(modified_at) if modified_at is not None else None,
        description=descriptions[0] if descriptions else None,
        scores=tuple(scores),
        references=tuple(references),
        missing_fields=tuple(missing),
    )


def discover_cve_pages(fetch_page: object, max_pages: int = MAX_PAGES) -> list[dict[str, object]]:
    """有界分页发现: 末页/空页正确终止, 不漏页不循环, 页数超限报契约错误。"""
    records: list[dict[str, object]] = []
    for page_index in range(max_pages):
        page = fetch_page(page_index)  # type: ignore[operator]
        if not isinstance(page, dict):
            raise ConnectorContractError("page payload must be an object")
        if page.get("status_code") == 429:
            raise ConnectorContractError("rate limited by upstream (429)")
        items = page.get("items")
        if not isinstance(items, list):
            raise ConnectorContractError("page items must be a list")
        if not items:
            return records
        for item in items:
            if isinstance(item, dict):
                records.append(item)
        if page.get("is_last_page") is True:
            return records
    raise ConnectorContractError("pagination exceeded bounded page limit")
