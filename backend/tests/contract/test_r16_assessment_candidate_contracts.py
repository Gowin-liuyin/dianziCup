"""Internal discovery contracts are isolated fixtures, not live/public API results."""

import pytest
from pydantic import ValidationError

from ai_intel.revalidation.candidate_contracts import AssessmentChangeCandidate, CandidatePage


def page_payload():
    return dict(
        change_id="fixture-change",
        scope_key="public",
        requested_epoch=1,
        target_epoch=2,
        scope_epoch_map={"public": 2, "tenant:fixture-tenant": None},
        candidates=(),
        status="complete",
        scanned_count=0,
    )


def test_complete_empty_page_preserves_discovery_and_unknown_scope():
    page = CandidatePage.model_validate(page_payload())
    assert page.candidates == () and page.continuation is None and page.target_epoch == 2
    assert page.scope_epoch_map["tenant:fixture-tenant"] is None


@pytest.mark.parametrize(
    "updates",
    [
        dict(status="partial"),
        dict(continuation="opaque"),
        dict(scanned_count=501),
        dict(status="reassessed"),
        dict(tenant_id="spoofed"),
        dict(target_epoch=True),
    ],
)
def test_invalid_or_spoofed_page_fields_are_rejected(updates):
    with pytest.raises(ValidationError):
        CandidatePage.model_validate({**page_payload(), **updates})


def test_duplicate_candidate_identity_is_rejected():
    candidate = AssessmentChangeCandidate(
        asset_id="fixture-asset",
        asset_snapshot_id="fixture-snapshot",
        reasons=("partition_fallback",),
    )
    with pytest.raises(ValidationError, match="duplicate"):
        CandidatePage.model_validate({**page_payload(), "candidates": (candidate, candidate)})


def test_partial_page_exposes_its_continuation_and_no_evaluation_status():
    page = CandidatePage.model_validate(
        {
            **page_payload(),
            "status": "partial",
            "continuation": "opaque",
            "fallback_reason": "unknown_or_incomplete_change_scope",
        }
    )
    assert page.status == "partial" and "assessment_status" not in page.model_dump()
