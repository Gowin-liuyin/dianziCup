"""Offline node boundaries preserve original reports and one absolute read deadline."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from test_r07_source_report_reader import read_case as read_case

from ai_intel.domain.access import CrossTenantAccessError
from ai_intel.domain.enums import ClaimStatus
from ai_intel.investigation import source_report_node as node
from ai_intel.investigation.graph_contracts import InvestigationRequest, json_object
from ai_intel.investigation.tool_contracts import CompareVersionsArguments, ReadEvidenceArguments
from ai_intel.knowledge.structured_fact_proofs import (
    StructuredFactProofChangedError,
    StructuredFactProofRead,
    StructuredFactProofReader,
    StructuredFactProofRequest,
)


@pytest.fixture
def clock(monkeypatch):
    value = SimpleNamespace(now=100.0)
    monkeypatch.setattr(node.time, "monotonic", lambda: value.now)
    return value


def investigation_request(count=1):
    event_id = uuid4()
    return InvestigationRequest(
        question="Read saved source reports only.",
        event_id=event_id,
        evidence_refs=tuple(
            ReadEvidenceArguments(event_id=event_id, evidence_id=uuid4(), revision_id=uuid4())
            for _ in range(count)
        ),
    )


def no_result(reference):
    return StructuredFactProofRead(
        request=StructuredFactProofRequest(**reference.model_dump()),
        status="not_found",
        input_sha256="0" * 64,
        data_mode="fixture",
    )


def fixture_request(read_case, count=1):
    references = tuple(
        ReadEvidenceArguments(
            event_id=read_case.request.event_id,
            evidence_id=UUID(link["evidence_id"]),
            revision_id=read_case.request.revision_id,
        )
        for link in read_case.snapshot.links[:count]
    )
    return InvestigationRequest(
        question="Read the explicitly isolated fixture source.",
        event_id=read_case.request.event_id,
        evidence_refs=references,
    )


@pytest.mark.parametrize("count", (0, 1, 8))
def test_one_read_per_valid_reference_preserves_order_and_shared_deadline(clock, count):
    request = investigation_request(count)
    reports = tuple(no_result(reference) for reference in request.evidence_refs)
    reader = Mock(spec=StructuredFactProofReader)
    reader.read.side_effect = reports
    returned = node.read_enrichment_source_reports(reader, request, 105.0)
    assert returned == reports
    assert all(actual is original for actual, original in zip(returned, reports, strict=True))
    assert reader.read.call_count == count
    for call, reference in zip(reader.read.call_args_list, request.evidence_refs, strict=True):
        assert call.args == (StructuredFactProofRequest(**reference.model_dump()), 105.0)


def test_shared_revision_is_read_for_each_distinct_evidence_without_dedup(clock):
    request = investigation_request(2)
    second = request.evidence_refs[1].model_copy(
        update={"revision_id": request.evidence_refs[0].revision_id}
    )
    request = request.model_copy(update={"evidence_refs": (request.evidence_refs[0], second)})
    reader = Mock(spec=StructuredFactProofReader)
    reader.read.side_effect = tuple(no_result(reference) for reference in request.evidence_refs)
    returned = node.read_enrichment_source_reports(reader, request, 105.0)
    assert len(returned) == 2 and reader.read.call_count == 2
    assert returned[0].request.revision_id == returned[1].request.revision_id
    assert returned[0].request.evidence_id != returned[1].request.evidence_id


@pytest.mark.parametrize(
    "bad",
    ("nine_refs", "cross_event", "duplicate", "blank_question", "unpaired_asset", "bad_version"),
)
def test_full_request_is_revalidated_before_any_read(clock, bad):
    request = investigation_request(2)
    if bad == "nine_refs":
        extra = tuple(
            ReadEvidenceArguments(
                event_id=request.event_id, evidence_id=uuid4(), revision_id=uuid4()
            )
            for _ in range(7)
        )
        request = request.model_copy(update={"evidence_refs": (*request.evidence_refs, *extra)})
    elif bad == "cross_event":
        changed = request.evidence_refs[1].model_copy(update={"event_id": uuid4()})
        request = request.model_copy(update={"evidence_refs": (request.evidence_refs[0], changed)})
    elif bad == "duplicate":
        request = request.model_copy(update={"evidence_refs": (request.evidence_refs[0],) * 2})
    elif bad == "blank_question":
        request = request.model_copy(update={"question": " "})
    elif bad == "unpaired_asset":
        request = request.model_copy(update={"asset_id": uuid4(), "asset_snapshot_id": None})
    else:
        invalid_comparison = CompareVersionsArguments.model_construct(
            left_version="1.0", right_version="2.0", scheme="sql", ecosystem="pypi"
        )
        request = request.model_copy(update={"version_comparison": invalid_comparison})
    reader = Mock(spec=StructuredFactProofReader)
    with pytest.raises(ValidationError):
        node.read_enrichment_source_reports(reader, request, 105.0)
    reader.read.assert_not_called()


def test_later_invalid_uuid_is_rejected_before_first_reference_io(clock):
    request = investigation_request(2)
    malformed = ReadEvidenceArguments.model_construct(
        event_id=request.event_id, evidence_id=None, revision_id=uuid4()
    )
    request = request.model_copy(update={"evidence_refs": (request.evidence_refs[0], malformed)})
    reader = Mock(spec=StructuredFactProofReader)
    with pytest.raises(ValidationError):
        node.read_enrichment_source_reports(reader, request, 105.0)
    reader.read.assert_not_called()


@pytest.mark.parametrize("deadline", (float("nan"), float("inf"), float("-inf"), 105.01))
def test_nonfinite_or_expanded_deadline_is_rejected_even_with_empty_refs(clock, deadline):
    reader = Mock(spec=StructuredFactProofReader)
    with pytest.raises(ValueError):
        node.read_enrichment_source_reports(reader, investigation_request(0), deadline)
    reader.read.assert_not_called()


@pytest.mark.parametrize("deadline", (99.0, 100.0))
def test_expired_deadline_is_timeout_without_reader_io(clock, deadline):
    reader = Mock(spec=StructuredFactProofReader)
    with pytest.raises(TimeoutError):
        node.read_enrichment_source_reports(reader, investigation_request(), deadline)
    reader.read.assert_not_called()


def test_remaining_deadline_is_shared_instead_of_reset_for_later_reference(clock):
    request = investigation_request(2)
    reader = Mock(spec=StructuredFactProofReader)

    def read(reference, deadline):
        assert deadline == 105.0
        clock.now = 104.0
        return no_result(reference)

    reader.read.side_effect = read
    assert len(node.read_enrichment_source_reports(reader, request, 105.0)) == 2
    assert [call.args[1] for call in reader.read.call_args_list] == [105.0, 105.0]


def test_read_between_references_cannot_overrun_shared_deadline(clock):
    request = investigation_request(2)
    reader = Mock(spec=StructuredFactProofReader)

    def read(reference, deadline):
        clock.now = 105.1
        return no_result(reference)

    reader.read.side_effect = read
    with pytest.raises(TimeoutError):
        node.read_enrichment_source_reports(reader, request, 105.0)
    assert reader.read.call_count == 1


@pytest.mark.parametrize("index", (0, 1))
@pytest.mark.parametrize(
    "failure",
    (
        OSError("fixture_io"),
        CrossTenantAccessError("fixture_acl"),
        StructuredFactProofChangedError("fixture_epoch"),
        TimeoutError("fixture_deadline"),
        ValueError("fixture_read"),
    ),
)
def test_first_or_later_read_error_propagates_unchanged(clock, index, failure):
    request = investigation_request(2)
    reader = Mock(spec=StructuredFactProofReader)
    reader.read.side_effect = [*([no_result(request.evidence_refs[0])] if index else []), failure]
    with pytest.raises(type(failure)) as captured:
        node.read_enrichment_source_reports(reader, request, 105.0)
    assert captured.value is failure
    assert reader.read.call_count == index + 1


def test_real_factory_reader_produces_reported_unknown_fact(clock, read_case):
    result = node.read_enrichment_source_reports(
        read_case.reader, fixture_request(read_case), 105.0
    )
    assert len(result) == 1 and result[0].status == "reported"
    fact = result[0].facts[0]
    assert fact.record.object_value.base_score == 9.8
    assert fact.record.condition_value.value == "unknown"
    assert fact.record.freshness.value == "unknown"
    assert fact.primary_assertion_path == "/cve/id"
    output = json_object(result[0])
    assert output["facts"][0]["record"]["condition_value"] == "unknown"


def test_real_missing_object_partial_is_preserved_instead_of_empty_success(clock, read_case):
    read_case.store.read_verified.side_effect = FileNotFoundError("explicit fixture missing object")
    result = node.read_enrichment_source_reports(
        read_case.reader, fixture_request(read_case), 105.0
    )
    assert len(result) == 1 and result[0].status == "partial"
    assert "source_object_missing" in result[0].missing_requirements
    assert result[0].facts[0].record.object_value.base_score == 9.8
    assert result[0].facts[0].report_support == "unverified"


def test_real_acl_error_is_not_returned_as_a_missing_report(clock, read_case):
    read_case.auth.side_effect = CrossTenantAccessError("fixture_acl")
    with pytest.raises(CrossTenantAccessError):
        node.read_enrichment_source_reports(read_case.reader, fixture_request(read_case), 105.0)


def test_mixed_original_reports_keep_conflicts_missing_and_json_identity(
    clock, read_case, monkeypatch
):
    request = fixture_request(read_case, count=3)
    monkeypatch.setattr(
        read_case.reader, "_read_inputs", lambda session, reference: read_case.snapshot
    )
    reported = read_case.reader.read(
        StructuredFactProofRequest(**request.evidence_refs[0].model_dump()), 105.0
    )
    read_case.record = read_case.record.model_copy(update={"claim_status": ClaimStatus.DISPUTED})
    read_case.snapshot = replace(
        read_case.snapshot,
        claim_rows=({**read_case.snapshot.claim_rows[0], "claim_status": "disputed"},),
    )
    partial = read_case.reader.read(
        StructuredFactProofRequest(**request.evidence_refs[1].model_dump()), 105.0
    )
    read_case.snapshot = replace(read_case.snapshot, claim_rows=())
    missing = read_case.reader.read(
        StructuredFactProofRequest(**request.evidence_refs[2].model_dump()), 105.0
    )
    reader = Mock(spec=StructuredFactProofReader)
    reader.read.side_effect = (reported, partial, missing)
    output = node.read_enrichment_source_reports(reader, request, 105.0)
    assert output[0] is reported and output[1] is partial and output[2] is missing
    assert [page.status for page in output] == ["reported", "partial", "not_found"]
    assert output[1].conflicts == (UUID(read_case.record.claim_id.value),)
    assert "claim_disputed" in output[1].missing_requirements
    assert output[1].facts[0].record.condition_value.value == "unknown"
    assert json_object(output[1]) == json_object(partial)


def test_empty_valid_refs_leave_factory_reader_and_store_idle(clock, read_case):
    request = InvestigationRequest(
        question="No evidence supplied.", event_id=uuid4(), evidence_refs=()
    )
    assert node.read_enrichment_source_reports(read_case.reader, request, 105.0) == ()
    assert not read_case.store.mock_calls
    assert not read_case.auth.mock_calls
    assert not read_case.connection.mock_calls


def test_all_original_eight_fact_pages_are_kept_without_an_aggregate_cap(clock, read_case):
    read_case.store.read_verified.side_effect = FileNotFoundError("explicit fixture missing object")
    partial = read_case.reader.read(read_case.request, 105.0)
    request = InvestigationRequest(
        question="Read bounded explicit fixture pages.",
        event_id=read_case.request.event_id,
        evidence_refs=tuple(
            ReadEvidenceArguments(
                event_id=read_case.request.event_id,
                evidence_id=uuid4(),
                revision_id=read_case.request.revision_id,
            )
            for _ in range(8)
        ),
    )
    pages = tuple(
        StructuredFactProofRead(
            request=StructuredFactProofRequest(**reference.model_dump()),
            status="partial",
            facts=partial.facts * 8,
            missing_requirements=partial.missing_requirements,
            input_sha256="0" * 64,
            data_mode="fixture",
        )
        for reference in request.evidence_refs
    )
    reader = Mock(spec=StructuredFactProofReader)
    reader.read.side_effect = pages
    output = node.read_enrichment_source_reports(reader, request, 105.0)
    assert all(actual is original for actual, original in zip(output, pages, strict=True))
    assert len(output) == 8 and sum(len(page.facts) for page in output) == 64
