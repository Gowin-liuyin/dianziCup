"""读接口的输入/输出边界，异常信息不产生假统计或伪引用。"""

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ai_intel.api.knowledge_contracts import (
    EnrichmentProjection,
    EventSummary,
    EvidenceResponse,
)


def test_available_enrichment_requires_real_reference() -> None:
    with pytest.raises(ValidationError, match="citation"):
        EnrichmentProjection(
            dimension="cvss",
            status="available",
            claim_ids=(),
            citations=(),
            freshness="unknown",
            observed_at=None,
            source_version=None,
            error_code=None,
        )
    value = EnrichmentProjection(
        dimension="cvss",
        status="available",
        claim_ids=(uuid4(),),
        citations=(
            {
                "evidence_id": uuid4(),
                "revision_id": uuid4(),
                "quote": "explicit source field",
                "locator": "/score",
                "source_uri": "https://nvd.nist.gov/",
            },
        ),
        freshness="current",
        observed_at=datetime.now(UTC),
        source_version="explicit-source-1",
        error_code=None,
    )
    assert value.citations[0].quote == "explicit source field"


@pytest.mark.parametrize("invalid_count", [True, -1, 1.5, "4"])
def test_source_count_rejects_boolean_negative_fraction_or_string(invalid_count: object) -> None:
    with pytest.raises(ValidationError):
        EventSummary.model_validate(
            {
                "event_id": str(uuid4()),
                "event_type": "advisory",
                "title": "explicit source",
                "external_ids": [],
                "primary_product_ids": [],
                "first_seen_at": "2026-10-15T00:00:00Z",
                "status": "active",
                "source_count": invalid_count,
                "latest_revision_id": None,
                "freshness": "unknown",
            }
        )


@pytest.mark.parametrize("end_offset", [8, 13])
def test_evidence_projection_keeps_unicode_global_offsets_and_unknown_times(
    end_offset: int,
) -> None:
    payload = {
        "span_id": str(uuid4()),
        "revision_id": str(uuid4()),
        "block_id": None,
        "start_offset": 10,
        "end_offset": end_offset,
        "quote_text": "中文证",
        "quote_sha256": hashlib.sha256("中文证".encode()).hexdigest(),
        "locator_kind": "text",
        "page_number": None,
        "json_pointer": None,
        "verified_at": None,
        "source_uri": None,
        "source_published_at": None,
        "source_modified_at": None,
        "first_observed_at": None,
        "ingested_at": None,
        "data_mode": "fixture",
    }
    if end_offset < 10:
        with pytest.raises(ValidationError, match="inverted"):
            EvidenceResponse.model_validate(payload)
    else:
        result = EvidenceResponse.model_validate(payload)
        assert result.end_offset - result.start_offset == len(result.quote_text)
        assert result.source_uri is None and result.source_modified_at is None
