"""新资料公开DTO边界与历史/精度不变量，不调用外部服务。"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from ai_intel.api.document_contracts import DocumentDetailResponse, DocumentSummary


def summary_values():
    return {
        "document_id": str(uuid4()),
        "source_id": str(uuid4()),
        "revision_id": str(uuid4()),
        "source_name": "Synthetic official publication",
        "source_category": "academic_paper",
        "document_kind": "paper",
        "title": "Synthetic paper title",
        "canonical_uri": "https://arxiv.org/abs/2601.00001v1",
        "revision_number": 1,
        "is_current": False,
        "source_published_at": None,
        "source_modified_at": None,
        "first_observed_at": "2026-10-15T10:00:00Z",
        "ingested_at": "2026-10-15T10:00:01Z",
        "parse_status": "partial",
        "content_coverage": "abstract",
        "published_at_raw": "2026-01-01",
        "published_precision": "calendar_date",
    }


def test_calendar_only_historical_abstract_is_not_full_text_or_instant():
    value = DocumentSummary.model_validate(summary_values())
    assert value.source_published_at is None
    assert value.is_current is False and value.content_coverage == "abstract"
    assert value.published_at_raw == "2026-01-01"


@pytest.mark.parametrize(
    "uri",
    [
        "http://arxiv.org/abs/2601.00001",
        "https://account:credential@arxiv.org/abs/2601.00001",
        "https://arxiv.org/abs/2601.00001?access_token=synthetic",
        "https://arxiv.org/abs/2601.00001#fragment",
        "https://arxiv.org/" + "x" * 2083,
    ],
)
def test_document_projection_rejects_unsafe_or_unbounded_source_uri(uri):
    with pytest.raises(ValidationError):
        DocumentSummary.model_validate({**summary_values(), "canonical_uri": uri})


@pytest.mark.parametrize(
    "change",
    [
        {"source_name": "x" * 301},
        {"title": "x" * 501},
        {"published_at_raw": "x" * 257},
        {"published_precision": "instant"},
        {"source_published_at": "2026-01-01T00:00:00Z"},
        {"published_precision": "calendar_date", "published_at_raw": None},
        {"source_modified_at": "2026-01-01T00:00:00"},
        {"document_kind": "asset_inventory"},
        {"content_coverage": "confirmed_safe"},
        {"untrusted_extra": True},
    ],
)
def test_document_projection_rejects_unsupported_precision_scope_and_fields(change):
    with pytest.raises(ValidationError):
        DocumentSummary.model_validate({**summary_values(), **change})


@pytest.mark.parametrize("different", ["revision", "mode", "count"])
def test_detail_does_not_mix_evidence_revision_mode_or_total(different):
    document = summary_values()
    evidence = {
        "schema_version": 2,
        "span_id": str(uuid4()),
        "revision_id": str(uuid4()) if different == "revision" else document["revision_id"],
        "block_id": None,
        "start_offset": 0,
        "end_offset": 4,
        "quote_text": "text",
        "quote_sha256": "0" * 64,
        "locator_kind": "text",
        "page_number": None,
        "json_pointer": None,
        "verified_at": "2026-10-15T10:00:01Z",
        "source_uri": document["canonical_uri"],
        "source_published_at": None,
        "source_modified_at": None,
        "first_observed_at": document["first_observed_at"],
        "ingested_at": document["ingested_at"],
        "data_mode": "fixture" if different == "mode" else "live",
    }
    with pytest.raises(ValidationError):
        DocumentDetailResponse.model_validate(
            {
                "document": document,
                "evidence": [evidence],
                "evidence_total": 0 if different == "count" else 1,
                "next_evidence_offset": None,
                "license_identifier": None,
                "license_uri": None,
                "source_notes": [],
                "data_mode": "live",
            }
        )
