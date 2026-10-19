"""相关性分级: 产品/生态/风险词表+高召回规则; 模糊材料受限模型分类或 uncertain。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

RELEVANCE_VERSION = "relevance-1.0.0"
AI_PRODUCT_TERMS = ("llm", "gpt", "large language model", "rag", "model", "ai")
ECOSYSTEM_TERMS = ("ml", "ai", "huggingface", "pytorch", "tensorflow")
RISK_TERMS = ("vulnerability", "cve-", "rce", "injection", "jailbreak", "advisory", "exploit")
KNOWN_AI_DEPENDENCIES = ("libdemo", "transformers", "onnxruntime")


@dataclass(frozen=True)
class RelevanceDecision:
    """分级结果: direct/dependency/background/irrelevant/uncertain + 证据句。"""

    classification: str
    evidence_sentences: tuple[str, ...] = field(default_factory=tuple)
    rule_version: str = RELEVANCE_VERSION


def _sentence_evidence(text: str, markers: tuple[str, ...]) -> tuple[str, ...]:
    """抽取含标记词的句级证据; 无命中为空。"""
    sentences = [part.strip() for part in text.replace("。", ".").split(".") if part.strip()]
    return tuple(
        sentence for sentence in sentences if any(marker in sentence.lower() for marker in markers)
    )


def classify_relevance(
    title: str,
    body_text: str,
    model_classifier: Callable[[str], str] | None = None,
) -> RelevanceDecision:
    """高召回规则优先; 模糊材料走受限模型分类, 模型不可用返回 uncertain 而非丢弃。"""
    combined = f"{title} {body_text}".lower()
    risk_hits = _sentence_evidence(combined, RISK_TERMS)
    product_hits = _sentence_evidence(combined, AI_PRODUCT_TERMS)
    dependency_hit = any(term in combined for term in KNOWN_AI_DEPENDENCIES)
    if product_hits and risk_hits:
        return RelevanceDecision("direct", tuple(dict.fromkeys(product_hits + risk_hits)))
    if dependency_hit and risk_hits:
        return RelevanceDecision("dependency_relevant", risk_hits)
    if risk_hits and any(term in combined for term in ECOSYSTEM_TERMS):
        return RelevanceDecision("dependency_relevant", risk_hits)
    if not risk_hits and product_hits:
        return RelevanceDecision("background", product_hits)
    if risk_hits and not product_hits and not dependency_hit:
        if model_classifier is None:
            return RelevanceDecision("uncertain", risk_hits)
        verdict = model_classifier(combined)
        if verdict == "direct":
            return RelevanceDecision("direct", risk_hits)
        return RelevanceDecision("uncertain", risk_hits)
    return RelevanceDecision("irrelevant", ())
