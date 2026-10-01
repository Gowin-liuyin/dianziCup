"""T22 研究关联与知识卡合同验收测试: 覆盖 T22-C01—C06。"""

from __future__ import annotations

import pytest

from ai_intel.enrichment.knowledge_cards import (
    KnowledgeCardError,
    PaperCard,
    PolicyCard,
    describe_policy_applicability,
    verification_label,
)
from ai_intel.enrichment.research_links import (
    ResearchLinkingError,
    build_controlled_query,
    classify_relation,
)


def test_paper_analyzes_event_with_type_and_evidence_t22_c01() -> None:
    """T22-C01: 论文明确分析某事件 → 关联类型和证据对应。"""
    relation = classify_relation(
        "ev-1", "paper-1", "analyzes_event", "Section 3 analyzes CVE-2021-44228 exploitation."
    )
    assert relation.relation_type == "analyzes_event" and relation.link_state == "confirmed"
    assert relation.supporting_paragraph.startswith("Section 3")
    query = build_controlled_query(("CVE-2021-44228",), ("log4j",), ("jndi injection",))
    assert (
        "identifier:CVE-2021-44228" in query
        and "product:log4j" in query
        and "mechanism:jndi injection" in query
    )


def test_shared_prompt_injection_theme_only_background_relation_t22_c02() -> None:
    """T22-C02: 只共享提示词注入主题 → 最多背景关联, 不写验证同一漏洞。"""
    relation = classify_relation(
        "ev-1", "paper-2", "validates_same_mechanism", "", shared_theme_only=True
    )
    assert relation.relation_type == "background_related" and relation.link_state == "background"
    assert relation.relation_type != "validates_same_mechanism"


def test_paper_tool_permission_prerequisite_preserved_t22_c03() -> None:
    """T22-C03: 论文需要写工具权限 → 前提字段保留, 不推广至只读环境。"""
    card = PaperCard(
        paper_id="p1", tool_permissions="write_filesystem", attacker_capability="poisoned_document"
    )
    assert card.tool_permissions == "write_filesystem"
    assert card.tool_permissions != "read_only"
    assert card.limitations_text == ""


def test_paper_without_cve_cvss_poc_marks_not_applicable_t22_c04() -> None:
    """T22-C04: 论文没有 CVE/CVSS/POC → 正确 not_applicable/not_found。"""
    card = PaperCard(paper_id="p2")
    assert card.cve_status() == "not_applicable" and card.has_exploit_artifact is False
    with_cve = PaperCard(paper_id="p3", cve_ids=("CVE-2021-44228",))
    assert with_cve.cve_status() == "available"


def test_policy_draft_and_final_distinct_status_time_t22_c05() -> None:
    """T22-C05: 政策草案与正式文件状态、时间不同, 不能替换。"""
    draft = PolicyCard(
        document_id="pol-1",
        issuer="ORG",
        document_number="P-1",
        version_label="draft-1",
        status="draft",
        published_at="2023-01-01",
        effective_at=None,
        scope_text="all systems",
        clause_reference="4.2",
        original_text="Draft text.",
        summary_text="Draft summary.",
    )
    final = PolicyCard(
        document_id="pol-2",
        issuer="ORG",
        document_number="P-1",
        version_label="1.0",
        status="effective",
        published_at="2023-06-01",
        effective_at="2024-01-01",
        scope_text="all systems",
        clause_reference="4.2",
        original_text="Final text.",
        summary_text="Final summary.",
    )
    assert draft.status != final.status and draft.effective_at != final.effective_at
    assert draft.original_text != final.original_text and draft.summary_text != final.summary_text
    assert draft.document_id != final.document_id


def test_unconfirmed_clause_scope_gives_quote_and_limit_not_ruling_t22_c06() -> None:
    """T22-C06: 无法确认条款适用范围 → 给原文和局限, 不生成合规裁决。"""
    card = PolicyCard(
        document_id="pol-3",
        issuer="ORG",
        document_number="P-2",
        version_label="1.0",
        status="effective",
        published_at="2023-01-01",
        effective_at="2023-01-01",
        scope_text="unknown",
        clause_reference="4.2",
        original_text="Operators shall restrict model access.",
        summary_text="Summary.",
    )
    message = describe_policy_applicability(card)
    assert "Operators shall restrict model access." in message
    assert "limitation recorded" in message and "no compliance ruling" in message
    assert "must" not in message.lower()
    assert verification_label(author_claimed=True, team_reproduced=False) == "author_reported"
    assert verification_label(author_claimed=True, team_reproduced=True) == "team_reproduced"
    assert (
        verification_label(author_claimed=False, team_reproduced=False) == "rule_inferred_for_asset"
    )
    strong_without_support = classify_relation("ev-1", "p-1", "provides_defense", "")
    assert strong_without_support.link_state == "candidate"
    with pytest.raises(ResearchLinkingError):
        classify_relation("ev-1", "p-1", "bogus_type", "text")
    with pytest.raises(KnowledgeCardError):
        verification_label(author_claimed=False, team_reproduced=True)
