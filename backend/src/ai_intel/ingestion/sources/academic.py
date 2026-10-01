"""学术元数据连接器: 版本关系/全文能力分标记/不判资产受影响。"""

from __future__ import annotations

from dataclasses import dataclass

ACADEMIC_CONNECTOR_VERSION = "academic-1.0.0"


class AcademicContractError(RuntimeError):
    """字段不兼容或分页异常: 明确失败, 不猜未确认参数。"""


@dataclass(frozen=True)
class AcademicRecord:
    """论文元数据: 同实体多版本; 全文能力独立标记; 攻击目标/模型名原文保留。"""

    paper_id: str
    version_label: str
    title: str
    authors: tuple[str, ...]
    abstract: str | None
    published_at: str | None
    modified_at: str | None
    full_text_link: str | None
    license_identifier: str | None
    full_text_fetched: bool = False
    extraction_status: str = "metadata_only"
    attack_target_text: str | None = None
    model_names_text: str | None = None
    withdrawn: bool = False
    source_schema_version: str = ACADEMIC_CONNECTOR_VERSION


def normalize_academic_record(payload: dict[str, object]) -> AcademicRecord:
    """归一论文元数据; 缺项明确 None/状态标记, 不虚构实验结果。"""
    paper_id = payload.get("paper_id")
    title = payload.get("title")
    if not isinstance(paper_id, str) or not isinstance(title, str):
        raise AcademicContractError("paper record missing id or title")
    raw_authors = payload.get("authors")
    authors = (
        tuple(str(item) for item in raw_authors if isinstance(item, str))
        if isinstance(raw_authors, list)
        else ()
    )
    version_label = str(payload.get("version", "v1"))
    abstract = payload.get("abstract")
    full_text_link = payload.get("full_text_link")
    full_text_fetched = payload.get("full_text_fetched") is True
    extraction_status = (
        "full_text_partial"
        if payload.get("pdf_text_incomplete") is True
        else ("full_text" if full_text_fetched else "metadata_only")
    )
    return AcademicRecord(
        paper_id=paper_id,
        version_label=version_label,
        title=title,
        authors=authors,
        abstract=str(abstract) if abstract is not None else None,
        published_at=str(payload["published_at"])
        if payload.get("published_at") is not None
        else None,
        modified_at=str(payload["modified_at"]) if payload.get("modified_at") is not None else None,
        full_text_link=str(full_text_link) if full_text_link is not None else None,
        license_identifier=str(payload["license"]) if payload.get("license") is not None else None,
        full_text_fetched=full_text_fetched,
        extraction_status=extraction_status,
        attack_target_text=str(payload["attack_target"])
        if payload.get("attack_target") is not None
        else None,
        model_names_text=str(payload["model_names"])
        if payload.get("model_names") is not None
        else None,
        withdrawn=payload.get("withdrawn") is True,
    )


def group_versions_by_paper(records: list[AcademicRecord]) -> dict[str, list[AcademicRecord]]:
    """同论文 v1/v2 归同一实体不同文档版本, 不重复统计研究数。"""
    grouped: dict[str, list[AcademicRecord]] = {}
    for record in records:
        grouped.setdefault(record.paper_id, []).append(record)
    return grouped


def count_distinct_research(records: list[AcademicRecord]) -> int:
    """按论文实体计数: 多版本合一, 不把版本当独立研究。"""
    return len(group_versions_by_paper(records))
