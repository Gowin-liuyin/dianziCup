"""Candidate boundaries preserve uncertainty and never grant fact publication authority."""

import hashlib
from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from pydantic import TypeAdapter, ValidationError

from ai_intel.domain.enrichment_values import EnrichmentValue, ExposureAggregateValue
from ai_intel.enrichment.contracts import (
    CandidateEvidence,
    DimensionAttempt,
    EnrichmentBlock,
    EnrichmentDocument,
    EvidenceBoundCandidate,
)

IDENTITY = UUID("12345678-1234-5678-1234-567812345678")
NOW = datetime(2026, 10, 15, 14, 45, tzinfo=UTC)
SIGNALS = (
    {
        "kind": "cvss_signal",
        "standard_version": "3.1",
        "base_score": 9.8,
        "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        "authority": "fixture-CNA",
    },
    {
        "kind": "epss_signal",
        "cve_id": "CVE-2024-37032",
        "probability": 0.0,
        "percentile": 0.0,
        "data_date": date(2026, 10, 15),
    },
    {
        "kind": "kev_signal",
        "cve_id": "CVE-2024-37032",
        "catalog_version": "fixture-v1",
        "date_added": date(2026, 10, 15),
        "required_action": "Apply source-described remediation",
    },
    {
        "kind": "weakness",
        "cwe_id": "CWE-78",
        "taxonomy_version": "fixture-v1",
        "name": "OS Command Injection",
    },
    {
        "kind": "atlas_mapping",
        "technique_id": "AML.T0051",
        "taxonomy_version": "fixture-v1",
        "mechanism": "Untrusted instructions enter a model input",
    },
    {
        "kind": "version_assertion",
        "package_key": "fixture-product",
        "ecosystem": "pypi",
        "scheme": "pep440",
        "raw_expression": "<1.2",
        "intervals": [{"fixed": "1.2"}],
    },
    {
        "kind": "literature_reference",
        "uri": "https://example.invalid/paper",
        "title": "Fixture",
        "reference_kind": "paper",
        "relation": "background",
        "support_summary": "Topic context only",
    },
    {
        "kind": "artifact_reference",
        "uri": "https://example.invalid/poc",
        "title": "Fixture",
        "artifact_kind": "poc",
        "static_status": "candidate_found",
    },
    {
        "kind": "exposure_aggregate",
        "provider": "hunter",
        "query_id": "fixture-product",
        "query_version": "fixture-v1",
        "service_count": 0,
        "retrieved_at": NOW,
        "ttl_seconds": 3600,
        "limitations": ["Service count is not affected asset count"],
    },
)
DIMENSIONS = ("cvss", "epss", "kev", "cwe", "atlas", "versions", "literature", "poc", "exposure")


def evidence():
    return CandidateEvidence(
        revision_id=IDENTITY,
        block_id=IDENTITY,
        start_offset=1,
        end_offset=3,
        quote_text="原文",
        quote_sha256=hashlib.sha256("原文".encode()).hexdigest(),
    )


@pytest.mark.parametrize("dimension,value", zip(DIMENSIONS, SIGNALS, strict=True))
def test_nine_typed_candidates_roundtrip_without_support_or_human_confirmation(dimension, value):
    candidate = EvidenceBoundCandidate(
        dimension=dimension, value=value, evidence=(evidence(),), origin="structured_source"
    )
    restored = EvidenceBoundCandidate.model_validate_json(candidate.model_dump_json())
    assert restored == candidate
    assert "supports_claim" not in candidate.model_dump()
    with pytest.raises(ValidationError):
        EvidenceBoundCandidate.model_validate({**candidate.model_dump(), "supports_claim": True})
    with pytest.raises(ValidationError):
        EvidenceBoundCandidate.model_validate(
            {**candidate.model_dump(), "origin": "human_confirmed"}
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("probability", -0.1),
        ("percentile", 1.01),
        ("probability", True),
        ("probability", float("nan")),
    ],
)
def test_probability_is_bounded_and_not_bool_or_nan(field, value):
    with pytest.raises(ValidationError):
        TypeAdapter(EnrichmentValue).validate_python({**SIGNALS[1], field: value})


def test_true_zero_aggregate_is_preserved_but_unknown_time_and_asset_details_are_distinct():
    value = ExposureAggregateValue.model_validate(SIGNALS[-1])
    assert value.service_count == 0 and value.observed_at is None
    for extra in ({"hosts": ["192.0.2.1"]}, {"affected_asset_count": 0}, {"service_count": True}):
        with pytest.raises(ValidationError):
            ExposureAggregateValue.model_validate({**SIGNALS[-1], **extra})


def test_quote_lengths_and_hashes_are_structural_checks_not_support_decisions():
    original = evidence().model_dump()
    for changed in ({"end_offset": 4}, {"start_offset": True}, {"quote_sha256": "0" * 64}):
        with pytest.raises(ValidationError):
            CandidateEvidence.model_validate({**original, **changed})
    assert evidence().quote_text == "原文"


def test_attempt_failure_and_no_result_cannot_be_inferred_from_empty_candidates():
    assert DimensionAttempt(dimension="epss", status="pending").freshness.value == "unknown"
    for fields in (
        {"status": "available"},
        {"status": "not_found"},
        {"status": "failed"},
        {"status": "blocked"},
        {"status": "pending", "freshness": "current"},
    ):
        with pytest.raises(ValidationError):
            DimensionAttempt(dimension="epss", **fields)
    result = DimensionAttempt(
        dimension="epss", status="not_found", searched_at=NOW, source_ids=(IDENTITY,)
    )
    assert result.candidates == () and result.status.value == "not_found"


def test_repeating_the_same_candidate_does_not_create_a_conflict():
    candidate = EvidenceBoundCandidate(
        dimension="cvss", value=SIGNALS[0], evidence=(evidence(),), origin="structured_source"
    )
    with pytest.raises(ValidationError):
        DimensionAttempt(dimension="cvss", status="conflict", candidates=(candidate, candidate))


def test_value_dimension_mismatch_and_unexecuted_poc_cannot_be_upgraded():
    with pytest.raises(ValidationError):
        EvidenceBoundCandidate(
            dimension="kev", value=SIGNALS[1], evidence=(evidence(),), origin="structured_source"
        )
    with pytest.raises(ValidationError):
        TypeAdapter(EnrichmentValue).validate_python(
            {**SIGNALS[-2], "static_status": "lab_verified"}
        )


def test_document_hash_duplicate_blocks_and_partial_coverage_remain_explicit():
    payload = b'{"field":"source"}'
    block = EnrichmentBlock(
        block_id=IDENTITY,
        start_offset=0,
        text="source",
        text_sha256=hashlib.sha256(b"source").hexdigest(),
    )
    fields = dict(
        revision_id=IDENTITY,
        document_id=IDENTITY,
        source_id=IDENTITY,
        document_kind="advisory",
        source_category="vendor_advisory",
        canonical_uri="https://example.invalid/advisory",
        source_record_id="fixture",
        content_sha256=hashlib.sha256(payload).hexdigest(),
        blocks=(block,),
        blocks_complete=False,
        content_coverage="excerpt",
        json_payload=payload,
    )
    document = EnrichmentDocument(**fields)
    assert document.blocks_complete is False and document.content_coverage == "excerpt"
    for change in ({"json_payload": b"changed"}, {"blocks": (block, block)}):
        with pytest.raises(ValidationError):
            EnrichmentDocument(**{**fields, **change})
