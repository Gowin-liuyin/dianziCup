"""组合树的精确卡错误协议：零派发、空attempt、无卡输出。"""

import pytest
from ai_intel.enrichment.card_extraction import CardExtractionFailure, extract_knowledge_card
from r09_card_fixtures import PUBLIC_SCOPE, candidate_field, prepared_client, source_document

from ai_intel.infrastructure.models import generation
from ai_intel.infrastructure.models.generation import GenerationLimits


def test_shared_timeout_is_exact_card_failure_without_dispatch(monkeypatch):
    source = source_document()
    client, calls = prepared_client(monkeypatch, {"fields": [candidate_field(source)]})
    client.limits = GenerationLimits(total_timeout_seconds=1.0)
    readings = iter((100.0, 103.0))
    monkeypatch.setattr(generation.time, "monotonic", lambda: next(readings, 103.0))
    with pytest.raises(CardExtractionFailure) as observed:
        extract_knowledge_card(client, source, PUBLIC_SCOPE)
    assert observed.value.code == "model_network_timeout"
    assert observed.value.attempts == ()
    assert calls == []
    assert client._slots.acquire(blocking=False)
    client._slots.release()
