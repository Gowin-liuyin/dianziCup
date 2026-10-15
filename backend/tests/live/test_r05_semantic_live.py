"""Opt-in real local weights; absent resources fail explicitly, with no fixture or skip."""

import json
import math
import os
import time
from pathlib import Path

import pytest

from ai_intel.infrastructure.models.semantic import LocalSemanticModels, SemanticInputError

PASSAGES = (
    "Prompt injection can make a language model follow malicious instructions in a document.",
    "Steam the rice with water until the grains are soft and ready to eat.",
    "提示注入会让语言模型遵循文档中嵌入的恶意指令。",
)


@pytest.fixture
def local_models() -> LocalSemanticModels:
    cache = os.environ.get("R05_SEMANTIC_CACHE")
    if not cache:
        pytest.fail(
            "blocked_live: R05_SEMANTIC_CACHE must point to verified official local weights"
        )
    return LocalSemanticModels(Path(cache))


def test_real_chinese_english_embeddings(local_models: LocalSemanticModels) -> None:
    start = time.monotonic()
    chinese_query = local_models.embed_query("什么是提示注入攻击？")
    chinese_seconds = time.monotonic() - start
    start = time.monotonic()
    english_query = local_models.embed_query("What is prompt injection?")
    english_seconds = time.monotonic() - start
    start = time.monotonic()
    passages = local_models.embed_passages(PASSAGES)
    passage_seconds = time.monotonic() - start
    assert chinese_query.dimension == english_query.dimension == passages.dimension == 384
    for vector in (*chinese_query.vectors, *english_query.vectors, *passages.vectors):
        assert all(type(value) is float and math.isfinite(value) for value in vector)
        assert math.isclose(sum(value * value for value in vector), 1.0, abs_tol=1e-5)
    assert passages.vectors[0] != passages.vectors[1]
    cosine_scores = [
        sum(left * right for left, right in zip(chinese_query.vectors[0], passage, strict=True))
        for passage in passages.vectors
    ]
    print(
        json.dumps(
            {
                "kind": "real_embedding_smoke",
                "model_version": passages.model_version,
                "chinese_query_seconds": chinese_seconds,
                "english_query_seconds": english_seconds,
                "passage_batch_seconds": passage_seconds,
                "chinese_query_cosines": cosine_scores,
                "quality_threshold": None,
            }
        )
    )


def test_real_cross_encoder_keeps_duplicate_indexes(local_models: LocalSemanticModels) -> None:
    start = time.monotonic()
    result = local_models.rerank(
        "什么是提示注入攻击？", (PASSAGES[0], PASSAGES[1], PASSAGES[0], PASSAGES[2])
    )
    elapsed = time.monotonic() - start
    assert sorted(item.index for item in result.items) == [0, 1, 2, 3]
    assert all(type(item.score) is float and math.isfinite(item.score) for item in result.items)
    assert all(
        left.score >= right.score
        for left, right in zip(result.items, result.items[1:], strict=False)
    )
    scores = {item.index: item.score for item in result.items}
    assert scores[0] == scores[2]
    assert [item.index for item in result.items].index(0) < [
        item.index for item in result.items
    ].index(2)
    print(
        json.dumps(
            {
                "kind": "real_reranker_smoke",
                "model_version": result.model_version,
                "total_seconds": elapsed,
                "ranked": [{"index": item.index, "score": item.score} for item in result.items],
                "quality_threshold": None,
            }
        )
    )


def test_real_token_limit_is_rejected_without_truncation(local_models: LocalSemanticModels) -> None:
    with pytest.raises(SemanticInputError, match="512 token"):
        local_models.embed_query("word " * 600)
    with pytest.raises(SemanticInputError, match="512 token"):
        local_models.rerank("query", ("word " * 600,))
