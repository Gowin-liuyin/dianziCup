"""The internal projection retains original states and exposes no new public authority."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from test_r07_public_signals import document, nvd_payload
from test_r07_structured_fact_proofs import claim_and_links

from ai_intel.api.knowledge_contracts import EvidenceResponse
from ai_intel.knowledge.structured_fact_proofs import (
    SourceReportedFact,
    StructuredFactProofRead,
    StructuredFactProofRequest,
)


def fact_fields():
    source = document(nvd_payload())
    record, links, primary_path = claim_and_links(source)
    span = links[0].evidence
    block = next(block for block in source.blocks if block.block_id == span.block_id)
    evidence = EvidenceResponse(
        span_id=links[0].evidence_id,
        revision_id=source.revision_id,
        block_id=span.block_id,
        start_offset=block.start_offset + span.start_offset,
        end_offset=block.start_offset + span.end_offset,
        quote_text=span.quote_text,
        quote_sha256=span.quote_sha256,
        locator_kind="json_pointer",
        page_number=None,
        json_pointer=block.json_pointer,
        verified_at=datetime.now(UTC),
        source_uri=source.canonical_uri,
        source_published_at=None,
        source_modified_at=None,
        first_observed_at=source.observed_at,
        ingested_at=source.observed_at,
        data_mode="fixture",
    )
    return {
        "record": record,
        "event_id": UUID(record.subject.removeprefix("event:")),
        "source_id": source.source_id,
        "document_id": source.document_id,
        "revision_id": source.revision_id,
        "primary_assertion_id": uuid4(),
        "primary_assertion_path": primary_path,
        "content_sha256": source.content_sha256,
        "source_uri": source.canonical_uri,
        "source_version": None,
        "source_observed_at": source.observed_at,
        "provenance_status": "source_verified",
        "claim_is_current": True,
        "revision_is_current": True,
        "report_support": "verified",
        "supporting_evidence": (evidence,),
    }


def test_verified_source_report_roundtrip_keeps_unknown_condition_and_freshness():
    fact = SourceReportedFact.model_validate(fact_fields())
    restored = SourceReportedFact.model_validate_json(fact.model_dump_json())
    assert restored.record == fact.record
    assert restored.record.condition_value.value == "unknown"
    assert restored.record.freshness.value == "unknown"
    assert restored.record.schema_version == 3


@pytest.mark.parametrize(
    "change",
    (
        {"claim_is_current": False},
        {"revision_is_current": False},
        {"provenance_status": "legacy_unverified"},
        {"primary_assertion_id": None},
        {"supporting_evidence": ()},
    ),
)
def test_verified_report_requires_complete_source_state(change):
    fields = fact_fields()
    with pytest.raises(ValidationError):
        SourceReportedFact.model_validate({**fields, **change})


@pytest.mark.parametrize("value", (0, 1, "true", "false"))
def test_currentness_fields_are_strict_booleans(value):
    fields = fact_fields()
    with pytest.raises(ValidationError):
        SourceReportedFact.model_validate({**fields, "claim_is_current": value})


def test_empty_or_unverified_read_cannot_be_reported_success():
    fields = fact_fields()
    request = StructuredFactProofRequest(event_id=uuid4(), evidence_id=uuid4(), revision_id=uuid4())
    base = {
        "request": request,
        "status": "reported",
        "input_sha256": "0" * 64,
        "data_mode": "fixture",
    }
    with pytest.raises(ValidationError):
        StructuredFactProofRead(**base)
    unverified = SourceReportedFact.model_validate({**fields, "report_support": "unverified"})
    with pytest.raises(ValidationError):
        StructuredFactProofRead(**base, facts=(unverified,))


def test_read_fact_limit_is_eight_with_no_silent_truncation():
    fact = SourceReportedFact.model_validate(fact_fields())
    request = StructuredFactProofRequest(event_id=uuid4(), evidence_id=uuid4(), revision_id=uuid4())
    with pytest.raises(ValidationError):
        StructuredFactProofRead(
            request=request,
            status="reported",
            facts=(fact,) * 9,
            input_sha256="0" * 64,
            data_mode="fixture",
        )
