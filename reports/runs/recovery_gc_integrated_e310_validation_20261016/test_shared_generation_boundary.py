"""An offline integrated caller check uses the real frozen generation implementation."""

from itertools import count
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend/tests/unit"))
from test_r05_generation import prepared
from test_r07_model_fields import fixture_documents

from ai_intel.domain.enums import DimensionStatus
from ai_intel.enrichment.model_fields import (
    ExtractedVersionValue,
    GeneratedFieldBatch,
    _generate_field,
)
from ai_intel.infrastructure.models import generation
from ai_intel.infrastructure.models.generation import GenerationLimits


@pytest.mark.parametrize("provider", ["openai", "anthropic", "deepseek_openai", "deepseek_anthropic"])
def test_r07_real_shared_predispatch_expiry_is_failed_and_has_no_dispatch(monkeypatch, provider):
    client, calls = prepared(monkeypatch, provider=provider, limits=GenerationLimits(total_timeout_seconds=1.0))
    dns = Mock(side_effect=AssertionError("offline check must not resolve DNS"))
    transport = Mock(side_effect=AssertionError("offline check must not dispatch"))
    monkeypatch.setattr(client._gateway._transport, "resolve_addresses", dns)
    monkeypatch.setattr(client._gateway._transport, "request", transport)
    readings = count()
    monkeypatch.setattr(generation.time, "monotonic", lambda: 100.0 if next(readings) == 0 else 103.0)
    documents = fixture_documents()
    attempt, metadata = _generate_field(
        "versions", GeneratedFieldBatch[ExtractedVersionValue], client, documents,
        (documents[0].blocks[0].text,), 100, False, False,
    )
    assert attempt.status == DimensionStatus.FAILED
    assert attempt.error_code == "model_network_timeout"
    assert attempt.candidates == ()
    assert metadata == ()
    assert calls == []
    dns.assert_not_called()
    transport.assert_not_called()
    assert client._slots.acquire(blocking=False)
    client._slots.release()
