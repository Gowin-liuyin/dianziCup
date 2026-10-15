"""完整原句的关系支持校验；仅合成固定输入，不调用真实模型或来源。"""

import hashlib

import pytest
from test_r07_model_fields import (
    PREREQUISITE,
    document,
    execute,
    fixture_documents,
    fixture_outputs,
    quote,
)

from ai_intel.domain.enums import ClaimOrigin, DimensionStatus
from ai_intel.enrichment.contracts import CandidateEvidence, EvidenceBoundCandidate
from ai_intel.enrichment.field_sources import FieldEvidenceError, validate_field_candidate


def bound_quote(source, text):
    return CandidateEvidence(
        **quote(source, text), quote_sha256=hashlib.sha256(text.encode()).hexdigest()
    )


@pytest.mark.parametrize(
    "mechanism,supported",
    [
        ("Untrusted instructions do not enter a model input.", False),
        ("Untrusted instructions cannot reach the model input.", False),
        ("The attack mechanism is unconfirmed; the input path is unknown.", False),
        ("没有外部指令进入模型输入。", False),
        ("不可信指令不会进入模型输入。", False),
        ("该攻击机制尚未确认，输入路径未知。", False),
        ("Untrusted instructions are not sanitized and enter a model input.", True),
        (
            "Untrusted instructions not only enter a model input but also override instructions.",
            True,
        ),
        (
            "The service fails to filter untrusted instructions "
            "and incorporates them into model input.",
            True,
        ),
        ("未经过滤的外部指令进入模型输入。", True),
        ("不受信任的指令进入模型输入。", True),
        ("不同来源的不可信指令进入模型输入并覆盖不同角色的提示。", True),
        ("外部指令不仅进入模型输入，而且覆盖已有指令。", True),
    ],
)
def test_atlas_relation_polarity_uses_the_attack_predicate(mechanism, supported):
    originals = fixture_documents()
    source = document(1, mechanism + "\n" + PREREQUISITE, "https://example.invalid/advisory")
    value = {
        **fixture_outputs(originals)["atlas"]["candidates"][0]["value"],
        "kind": "atlas_mapping",
        "mechanism": mechanism,
    }
    candidate = EvidenceBoundCandidate(
        dimension="atlas",
        origin=ClaimOrigin.MODEL_HYPOTHESIS,
        value=value,
        evidence=(
            bound_quote(source, mechanism),
            bound_quote(source, PREREQUISITE),
            bound_quote(originals[1], originals[1].blocks[0].text),
        ),
    )
    if supported:
        assert (
            validate_field_candidate(candidate, (source, originals[1])).value.mechanism == mechanism
        )
    else:
        with pytest.raises(FieldEvidenceError, match="field_relation_negative_or_unknown"):
            validate_field_candidate(candidate, (source, originals[1]))


@pytest.mark.parametrize(
    "relation,summary,supported",
    [
        (
            "analysis",
            "This paper does not analyze the vulnerability; it analyzes another package.",
            False,
        ),
        (
            "analysis",
            "Analysis of this vulnerability is unconfirmed; the mechanism is unknown.",
            False,
        ),
        ("analysis", "本文没有分析该漏洞，仅分析另一个组件。", False),
        ("analysis", "该论文与本事件的分析关系尚未确认。", False),
        ("analysis", "This paper analyzes the vulnerability but does not execute the PoC.", True),
        (
            "analysis",
            "This paper not only analyzes the vulnerability but also documents the conditions.",
            True,
        ),
        ("analysis", "This paper analyzes the vulnerability observed in May.", True),
        ("analysis", "本文分析该漏洞，但没有执行概念验证程序。", True),
        ("analysis", "本文不仅分析该漏洞，也保留攻击前提。", True),
        ("defense", "This paper does not provide a defense for this vulnerability.", False),
        ("defense", "本文没有提供针对该漏洞的防御方法。", False),
        ("defense", "This paper provides a defense and does not execute exploit code.", True),
        ("defense", "本文提供针对该漏洞的防御方法，但不运行利用代码。", True),
        ("experimental", "This paper does not experimentally test the mechanism.", False),
        ("experimental", "本文未开展该机制的实验。", False),
        (
            "experimental",
            "This paper experimentally tests the mechanism but does not scan assets.",
            True,
        ),
        ("experimental", "本文实验验证该机制，但不扫描资产。", True),
        (
            "analysis",
            "This paper analyzes this vulnerability; the analysis is not supported by evidence.",
            False,
        ),
    ],
)
def test_literature_relation_polarity_preserves_unrelated_safety_constraints(
    relation, summary, supported
):
    originals = fixture_documents()
    title_line = "Fixture Paper https://example.invalid/paper"
    source = document(1, summary + "\n" + title_line, "https://example.invalid/advisory")
    value = {
        **fixture_outputs(originals)["literature"]["candidates"][0]["value"],
        "kind": "literature_reference",
        "relation": relation,
        "support_summary": summary,
    }
    candidate = EvidenceBoundCandidate(
        dimension="literature",
        origin=ClaimOrigin.MODEL_HYPOTHESIS,
        value=value,
        evidence=(bound_quote(source, summary), bound_quote(source, title_line)),
    )
    if supported:
        result = validate_field_candidate(candidate, (source, originals[2]))
        assert result.value.relation == relation and result.value.support_summary == summary
        assert result.origin == ClaimOrigin.MODEL_HYPOTHESIS
    else:
        with pytest.raises(FieldEvidenceError, match="field_relation_negative_or_unknown"):
            validate_field_candidate(candidate, (source, originals[2]))


def test_four_model_fields_keep_budget_and_pending_hypotheses_after_shared_guard(monkeypatch):
    originals = fixture_documents()
    mechanism = "Untrusted instructions are not sanitized and enter a model input."
    changed_text = (
        originals[0]
        .blocks[0]
        .text.replace("Untrusted instructions enter a model input.", mechanism)
    )
    source = document(1, changed_text, "https://example.invalid/advisory")
    documents = (source, *originals[1:])
    outputs = fixture_outputs(originals)
    for field in outputs.values():
        for candidate in field["candidates"]:
            candidate["evidence"] = [
                quote(
                    source,
                    mechanism
                    if item["quote_text"] == "Untrusted instructions enter a model input."
                    else item["quote_text"],
                )
                if item["revision_id"] == str(source.revision_id)
                else item
                for item in candidate["evidence"]
            ]
    outputs["atlas"]["candidates"][0]["value"]["mechanism"] = mechanism
    outputs["atlas"]["candidates"][0]["evidence"] = [
        quote(source, mechanism),
        quote(source, PREREQUISITE),
        quote(originals[1], originals[1].blocks[0].text),
    ]
    result, calls = execute(monkeypatch, outputs, documents)
    assert len(calls) == 4
    assert all(attempt.status == DimensionStatus.PENDING for attempt in result.attempts)
    assert all(
        candidate.origin == ClaimOrigin.MODEL_HYPOTHESIS
        for attempt in result.attempts
        for candidate in attempt.candidates
    )
