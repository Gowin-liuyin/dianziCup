"""T17 相关性与事件关联单元验收测试: 覆盖 T17-C01—C06 + 困难负例。"""

from __future__ import annotations

import pytest

from ai_intel.enrichment.relevance import classify_relevance
from ai_intel.knowledge.event_linking import EventLinkingError, EventLinkingLedger, SecurityEvent


def test_direct_ai_security_advisory_with_evidence_t17_c01() -> None:
    """T17-C01: 明确 AI 产品安全公告 → direct 且证据句存在。"""
    decision = classify_relevance(
        "LLM gateway advisory",
        "A vulnerability in the LLM model gateway allows remote code execution.",
    )
    assert decision.classification == "direct"
    assert len(decision.evidence_sentences) >= 1
    assert any("vulnerability" in sentence.lower() for sentence in decision.evidence_sentences)


def test_dependency_in_known_ai_list_detected_without_ai_words_t17_c02() -> None:
    """T17-C02: 通用依赖进入已知 AI 清单 → dependency_relevant, 不因无 AI 词漏掉。"""
    decision = classify_relevance(
        "libdemo security release",
        "A vulnerability in libdemo parser permits injection when handling payloads.",
    )
    assert decision.classification == "dependency_relevant"
    assert decision.evidence_sentences


def test_plain_product_release_is_background_or_irrelevant_t17_c03() -> None:
    """T17-C03: 普通产品发布文章 → irrelevant/background, 不当漏洞。"""
    background = classify_relevance(
        "Our AI assistant gets new themes", "The model interface now supports dark mode."
    )
    assert background.classification == "background"
    plain = classify_relevance(
        "Office suite 5.2 released", "Performance improvements and bug fixes."
    )
    assert plain.classification == "irrelevant"


def test_same_cwe_different_cve_not_merged_t17_c04() -> None:
    """T17-C04: 同 CWE 不同 CVE → 不合并（同 CWE 不是合并依据）。"""
    ledger = EventLinkingLedger()
    left = SecurityEvent(
        "e1", cve_ids=("CVE-2021-0001",), cwe_ids=("CWE-79",), body_fingerprint="f1"
    )
    right = SecurityEvent(
        "e2", cve_ids=("CVE-2021-0002",), cwe_ids=("CWE-79",), body_fingerprint="f2"
    )
    assert ledger.should_merge(left, right, trusted_aliases=()) is False
    same_product = SecurityEvent(
        "e3", cve_ids=("CVE-2021-0003",), product_names=("libdemo",), body_fingerprint="f3"
    )
    assert ledger.should_merge(left, same_product, trusted_aliases=()) is False


def test_article_with_two_cves_links_two_events_t17_c05() -> None:
    """T17-C05: 一文两 CVE → 两事件关联而非并成同一事件。"""
    ledger = EventLinkingLedger()
    created = ledger.link_article_events(["CVE-2021-0001", "CVE-2021-0002"], "src-1", "fp-1")
    assert len(created) == 2 and created[0] != created[1]
    assert ledger.events[created[0]].cve_ids != ledger.events[created[1]].cve_ids
    assert len(ledger.events) == 2


def test_undo_wrong_merge_restores_sources_without_deleting_history_t17_c06() -> None:
    """T17-C06: 错误合并撤销 → 来源与引用可恢复, 不删除历史。"""
    ledger = EventLinkingLedger()
    ledger.link_article_events(["CVE-2021-0001"], "src-1", "fp-1")
    ledger.link_article_events(["CVE-2021-0001"], "src-2", "fp-1")
    keep_id, merge_id = list(ledger.events)
    ledger.merge_events(keep_id, merge_id)
    ledger.undo_merge(keep_id, merge_id)
    history = ledger.describe_history()
    assert history["merged"] == [(keep_id, merge_id)]
    assert history["withdrawn"] == [(keep_id, merge_id)]
    assert history["impact_events"] == [f"merge_withdrawn:{keep_id}:{merge_id}"]
    assert history["current_event_count"] == 2
    assert ledger.events[merge_id].source_record_ids == ("src-2",)
    with pytest.raises(EventLinkingError):
        ledger.undo_merge("nope-1", "nope-2")


def test_model_unavailable_on_ambiguous_material_returns_uncertain_t17_extra() -> None:
    """边界: 无 AI 词的风险材料 + 模型不可用 → uncertain 而非全丢弃。"""
    decision = classify_relevance("Parser crash", "A vulnerability in the parser component.")
    assert decision.classification == "uncertain" and decision.evidence_sentences
    forced = classify_relevance(
        "Parser crash",
        "A vulnerability in the parser component.",
        model_classifier=lambda text: "direct",
    )
    assert forced.classification == "direct"
