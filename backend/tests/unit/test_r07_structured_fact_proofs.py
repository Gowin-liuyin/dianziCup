"""A saved source report never becomes a condition, currentness, or asset safety verdict."""

import json
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from test_r07_enrichment_contracts import SIGNALS
from test_r07_public_signals import CVE, context, document, epss_document, nvd_payload

from ai_intel.domain.records import ClaimRecord
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.enrichment.signal_sources import select_public_signal_document
from ai_intel.enrichment.signals import enrich_structured_fields
from ai_intel.knowledge.structured_fact_proofs import (
    StructuredFactProofReader,
    StructuredFactProofRequest,
    _FactInputs,
    _LinkedFactEvidence,
    _verify_source_report,
)

NOW = datetime(2026, 10, 16, tzinfo=UTC)


def kev_document():
    payload = {
        "catalogVersion": "2026.10.15",
        "dateReleased": "2026-10-15T10:00:00Z",
        "count": 1,
        "vulnerabilities": [
            {
                "cveID": CVE,
                "dateAdded": "2026-09-01",
                "requiredAction": "Apply source-described remediation",
                "knownRansomwareCampaignUse": "Unknown",
            }
        ],
    }
    selected = select_public_signal_document("kev", json.dumps(payload).encode(), CVE)
    return document(json.loads(selected.payload), selected.canonical_uri)


def claim_and_links(source, dimension="cvss"):
    candidate = next(
        attempt
        for attempt in enrich_structured_fields(context(source), (source,))
        if attempt.dimension == dimension
    ).candidates[0]
    record = ClaimRecord(
        schema_version=3,
        claim_id=Identifier(value=str(uuid4())),
        subject="event:" + str(context(source).event_id),
        predicate=candidate.value.kind,
        object_value=candidate.value,
        claim_status="supported",
        claim_origin="structured_source",
        condition_value="unknown",
        freshness="unknown",
        asserted_at=NOW,
        scope=VisibilityScope(visibility="public"),
    )
    links = tuple(
        _LinkedFactEvidence(
            evidence_id=uuid4(),
            evidence=span,
            support_kind="supports",
            validation_status="validated",
            supports_claim=True,
        )
        for span in candidate.evidence
    )
    primary_path = next(
        block.json_pointer
        for block in source.blocks
        if block.block_id == candidate.evidence[0].block_id
    )
    return record, links, primary_path


@pytest.mark.parametrize("extra", ("tenant_id", "owner_user_id", "claim_id", "sql", "url"))
def test_three_uuid_request_rejects_extra_authority_or_read_targets(extra):
    with pytest.raises(ValidationError):
        StructuredFactProofRequest(
            event_id=uuid4(), evidence_id=uuid4(), revision_id=uuid4(), **{extra: "injected"}
        )


def test_cvss_source_report_preserves_unknown_and_does_not_recompute_score():
    source = document(nvd_payload())
    record, links, primary_path = claim_and_links(source)
    verified, missing = _verify_source_report(record, source, links, (("cve", CVE),), primary_path)
    assert set(verified) == {link.evidence_id for link in links}
    assert not missing
    assert record.condition_value.value == "unknown"
    assert record.freshness.value == "unknown"
    assert record.object_value.base_score == 9.8


def test_zero_epss_is_a_reported_value_without_asset_conclusions():
    source = epss_document()
    record, links, primary_path = claim_and_links(source, "epss")
    verified, missing = _verify_source_report(record, source, links, (("cve", CVE),), primary_path)
    assert verified and not missing
    assert record.object_value.probability == 0
    assert record.condition_value.value == "unknown"


def test_owner_span_must_be_linked_to_this_claim_in_this_primary_revision():
    source = document(nvd_payload())
    record, links, primary_path = claim_and_links(source)
    owner = next(link for link in links if link.evidence.quote_text == CVE)
    without_owner = tuple(link for link in links if link is not owner)
    verified, missing = _verify_source_report(
        record, source, without_owner, (("cve", CVE),), primary_path
    )
    assert not verified and "owner_evidence_missing" in missing
    other_revision = owner.model_copy(
        update={"evidence": owner.evidence.model_copy(update={"revision_id": uuid4()})}
    )
    verified, missing = _verify_source_report(
        record, source, (*without_owner, other_revision), (("cve", CVE),), primary_path
    )
    assert not verified and "owner_evidence_missing" in missing


@pytest.mark.parametrize(
    "changes",
    ({"support_kind": "context"}, {"validation_status": "unverified"}, {"supports_claim": False}),
)
def test_a_matching_quote_without_its_validated_support_link_cannot_sign_report(changes):
    source = document(nvd_payload())
    record, links, primary_path = claim_and_links(source)
    changed = tuple(link.model_copy(update=changes) for link in links)
    verified, missing = _verify_source_report(
        record, source, changed, (("cve", CVE),), primary_path
    )
    assert not verified and missing


def test_identical_score_belongs_to_the_event_owner_in_the_actual_source_member():
    source = document(nvd_payload())
    record, links, primary_path = claim_and_links(source)
    verified, missing = _verify_source_report(
        record, source, links, (("cve", "CVE-2024-99999"),), primary_path
    )
    assert not verified and "source_owner_mismatch" in missing


def test_value_change_cannot_be_signed_by_unchanged_saved_source_spans():
    source = document(nvd_payload())
    record, links, primary_path = claim_and_links(source)
    altered = record.model_copy(
        update={"object_value": record.object_value.model_copy(update={"base_score": 1.0})}
    )
    verified, missing = _verify_source_report(altered, source, links, (("cve", CVE),), primary_path)
    assert not verified and "source_value_mismatch" in missing


@pytest.mark.parametrize("value", SIGNALS[3:], ids=lambda value: value["kind"])
def test_remaining_typed_facts_keep_their_explicit_proof_gap(value):
    source = document(nvd_payload())
    record, links, primary_path = claim_and_links(source)
    original = record.model_dump()
    original.update(predicate=value["kind"], object_value=value)
    typed_record = ClaimRecord.model_validate(original)
    verified, missing = _verify_source_report(
        typed_record, source, links, (("cve", CVE),), primary_path
    )
    expected = (
        "cwe_owner_evidence_missing" if value["kind"] == "weakness" else "unsupported_typed_fact"
    )
    assert not verified and missing == (expected,)
    assert typed_record.condition_value.value == "unknown"


@pytest.mark.parametrize("link_count", (8, 9))
def test_second_fence_bounds_link_lock_scan_and_rejects_lookahead(link_count):
    request = StructuredFactProofRequest(event_id=uuid4(), evidence_id=uuid4(), revision_id=uuid4())
    inputs = Mock(
        spec=_FactInputs,
        parents=(),
        claim_rows=({"claim_id": str(uuid4())},),
        links=(),
        blocks=(),
        assertions=(),
        dimensions=(),
        epochs=(),
    )
    session = Mock(spec=Session)
    session.execute.return_value.all.side_effect = [
        *([] for _ in range(10)),
        [tuple() for _ in range(link_count)],
        [],
    ]
    reader = Mock(spec=StructuredFactProofReader)
    if link_count > 8:
        with pytest.raises(ValueError, match="fact_proof_input_limit_exceeded"):
            StructuredFactProofReader._lock_inputs(reader, session, request, inputs)
    else:
        StructuredFactProofReader._lock_inputs(reader, session, request, inputs)
    sql = str(
        session.execute.call_args_list[10]
        .args[0]
        .compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )
    assert "LIMIT 9" in sql
    assert "ORDER BY claim_evidence.evidence_id" in sql
    assert "FOR SHARE" in sql


@pytest.mark.parametrize("dimension", ("cvss", "epss", "kev"))
def test_primary_assertion_is_the_actual_published_location_for_this_typed_value(dimension):
    source = {"cvss": lambda: document(nvd_payload()), "epss": epss_document, "kev": kev_document}[
        dimension
    ]()
    record, links, primary_path = claim_and_links(source, dimension)
    verified, missing = _verify_source_report(record, source, links, (("cve", CVE),), primary_path)
    assert verified and not missing
    if dimension == "kev":
        assert primary_path == "/response/catalogVersion"
    verified, missing = _verify_source_report(
        record, source, links, (("cve", CVE),), "/unrelated/other-owner/score"
    )
    assert not verified and missing == ("primary_assertion_path_mismatch",)
    assert record.condition_value.value == "unknown"


def test_event_revision_withdrawal_changes_the_entire_read_fence_fingerprint():
    association = {
        "event_id": str(uuid4()),
        "revision_id": str(uuid4()),
        "active": True,
        "associated_at": NOW,
        "superseded_at": None,
    }
    original = _FactInputs(
        event_row={},
        claim_rows=(),
        assertions=(),
        links=(),
        parents=(),
        associations=(association,),
        blocks=(),
        dimensions=(),
        identifiers=(),
        epochs=(),
        truncated=False,
    )
    withdrawn = replace(
        original, associations=({**association, "active": False, "superseded_at": NOW},)
    )
    assert withdrawn.fingerprint() != original.fingerprint()
