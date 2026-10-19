"""独立精确断言：共享超时自然包装成卡固定错误，不派发模型请求。"""

import pytest

from ai_intel.enrichment.card_extraction import CardExtractionFailure, extract_knowledge_card
from ai_intel.infrastructure.models.generation import GenerationLimits
from r09_card_fixtures import PUBLIC_SCOPE, candidate_field, prepared_client, source_document


def test_exact_pre_dispatch_failure_is_card_timeout_without_attempt_or_call(monkeypatch):
    source = source_document()
    client, calls = prepared_client(monkeypatch, {"fields": [candidate_field(source)]})
    client.limits = GenerationLimits(total_timeout_seconds=1.0)
    readings = iter((100.0, 103.0))
    monkeypatch.setattr("ai_intel.infrastructure.models.generation.time.monotonic", lambda: next(readings, 103.0))
    with pytest.raises(CardExtractionFailure) as caught:
        extract_knowledge_card(client, source, PUBLIC_SCOPE)
    assert type(caught.value) is CardExtractionFailure
    assert caught.value.code == "model_network_timeout"
    assert caught.value.attempts == ()
    assert calls == []
    assert caught.value.__cause__ is None
