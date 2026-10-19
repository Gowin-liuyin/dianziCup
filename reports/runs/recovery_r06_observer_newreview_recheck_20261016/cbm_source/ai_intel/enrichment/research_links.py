"""研究关联: 标识/产品/机制受控查询; 关系类型分立; 无支持关系留 candidate/background。"""

from __future__ import annotations

from dataclasses import dataclass

RESEARCH_LINKS_VERSION = "research-links-1.0.0"
RELATION_TYPES = (
    "first_proposal",
    "analyzes_event",
    "validates_same_mechanism",
    "provides_defense",
    "background_related",
)
STRONG_RELATIONS = frozenset(
    {"first_proposal", "analyzes_event", "validates_same_mechanism", "provides_defense"}
)


class ResearchLinkingError(RuntimeError):
    """强关系无支持段落或关系类型未知: 明确失败。"""


@dataclass(frozen=True)
class ResearchRelation:
    """事件-文献关系: 强关系必须带支持段落; 无支持降 candidate/background。"""

    event_id: str
    document_id: str
    relation_type: str
    supporting_paragraph: str = ""
    link_state: str = "confirmed"


def build_controlled_query(
    identifiers: tuple[str, ...],
    product_terms: tuple[str, ...],
    mechanism_terms: tuple[str, ...],
) -> tuple[str, ...]:
    """受控查询生成: 标识/产品/机制分面, 不只按标题相似度连边。"""
    facets = (
        [f"identifier:{item}" for item in identifiers],
        [f"product:{item}" for item in product_terms],
        [f"mechanism:{item}" for item in mechanism_terms],
    )
    return tuple(term for group in facets for term in group)


def classify_relation(
    event_id: str,
    document_id: str,
    proposed_type: str,
    supporting_paragraph: str,
    shared_theme_only: bool = False,
) -> ResearchRelation:
    """关系分型: 仅共享主题→background; 强关系无段落支持→candidate。"""
    if proposed_type not in RELATION_TYPES:
        raise ResearchLinkingError(f"unknown relation type: {proposed_type}")
    if shared_theme_only:
        return ResearchRelation(
            event_id, document_id, "background_related", link_state="background"
        )
    if proposed_type in STRONG_RELATIONS and not supporting_paragraph.strip():
        return ResearchRelation(event_id, document_id, proposed_type, link_state="candidate")
    return ResearchRelation(event_id, document_id, proposed_type, supporting_paragraph)
