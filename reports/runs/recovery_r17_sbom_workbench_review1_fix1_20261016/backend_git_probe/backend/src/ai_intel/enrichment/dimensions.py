"""维度矩阵: 按 DocumentKind 适用性分域; 论文/标准/政策不强制 CVE/CVSS。"""

from __future__ import annotations

from dataclasses import dataclass

DIMENSIONS_VERSION = "dimensions-1.0.0"
ALL_DIMENSIONS = (
    "cve_id",
    "cvss_score",
    "affected_product",
    "paper_mechanism",
    "policy_clause",
    "fix_status",
)
KIND_DIMENSION_MATRIX: dict[str, tuple[str, ...]] = {
    "vulnerability_advisory": ("cve_id", "cvss_score", "affected_product", "fix_status"),
    "research_paper": ("paper_mechanism", "affected_product"),
    "standard_document": ("policy_clause",),
    "policy_document": ("policy_clause",),
}


@dataclass(frozen=True)
class DimensionValue:
    """单维度结果: 独立状态机, available/not_found/not_applicable/conflict/blocked/failed。"""

    dimension: str
    status: str
    raw_value: object = None
    source_record_id: str = ""
    json_path: str = ""
    scoring_authority: str = ""
    evidence_text: str = ""


VALID_STATUSES = ("available", "not_found", "not_applicable", "conflict", "blocked", "failed")


def dimension_status_for_kind(dimension: str, document_kind: str) -> str:
    """维度适用性: kind 不适用即 not_applicable, 不强制补 CVE/CVSS。"""
    applicable = KIND_DIMENSION_MATRIX.get(document_kind, ())
    return "available" if dimension in applicable else "not_applicable"
