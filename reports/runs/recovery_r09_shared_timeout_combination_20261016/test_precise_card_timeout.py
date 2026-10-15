"""Verify the exact fixture card failure contract before gateway dispatch."""

import pytest

from ai_intel.enrichment.card_extraction import CardExtractionFailure, extract_knowledge_card
from ai_intel.infrastructure.models.generation import GenerationLimits
from r09_card_fixtures import PUBLIC_SCOPE, candidate_field, prepared_client, source_document


def test_card_pre_dispatch_timeout_has_exact_failure_and_zero_calls(monkeypatch):
    """An expired deadline yields the shared timeout code without an attempt."""
    source = source_document()
    client, calls = prepared_client(monkeypatch, {"fields": [candidate_field(source)]})
    client.limits = GenerationLimits(total_timeout_seconds=1.0)
    clock_values = iter((100.0, 103.0))
    monkeypatch.setattr(
        "ai_intel.infrastructure.models.generation.time.monotonic",
        lambda: next(clock_values, 103.0),
    )
    with pytest.raises(CardExtractionFailure) as caught:
        extract_knowledge_card(client, source, PUBLIC_SCOPE)
    assert type(caught.value) is CardExtractionFailure
    assert caught.value.code == "model_network_timeout"
    assert caught.value.attempts == ()
    assert calls == []
