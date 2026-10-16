"""Mode is an additive server argument; clients cannot attest source provenance."""

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ai_intel.ingestion.source_documents import SourceResponse
from ai_intel.ingestion.source_jobs import SourcePageRequest


def test_existing_response_constructor_preserves_unknown_mode():
    response = SourceResponse("vllm_vendor", b"[]", "https://example.invalid", datetime.now(UTC))
    assert response.data_mode is None
    assert response.body == b"[]"


@pytest.mark.parametrize("mode", [None, "fixture", "live", "invalid"])
def test_source_job_body_cannot_supply_mode(mode):
    payload = {
        "source_kind": "nvd_ollama",
        "window_end": "2026-10-16T00:00:00Z",
        "data_mode": mode,
    }
    with pytest.raises(ValidationError) as captured:
        SourcePageRequest.model_validate_json(json.dumps(payload))
    assert any(
        error["type"] == "extra_forbidden" and error["loc"] == ("data_mode",)
        for error in captured.value.errors()
    )
