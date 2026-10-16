"""R15 internal candidate serialization contract; no public API or PG isolation claim."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from ai_intel.recommendations.contracts import (
    RecommendationBatch,
    RecommendationEventInput,
    RecommendationReason,
    RecommendationSubscription,
    ReportCandidate,
    SelectorEvidence,
)
from ai_intel.recommendations.policy import generate_recommendation_candidates
from ai_intel.recommendations.report_builder import build_report_candidate

CUTOFF = datetime(2026, 10, 16, 0, tzinfo=UTC)


def fixture_subscription():
    return RecommendationSubscription(
        subscription_id="fixture-sub",
        user_id="fixture-user",
        tenant_id="fixture-tenant",
        enabled=True,
        risk_topics=("prompt_injection",),
    )


def fixture_event():
    quote = "The described risk mechanism is prompt_injection."
    return RecommendationEventInput(
        event_id="fixture-event",
        material_version="fixture-version",
        observed_at=CUTOFF,
        valid_from=CUTOFF,
        status_at_cutoff="supported",
        freshness_at_cutoff="current",
        current_status="supported",
        current_freshness="current",
        current_state_checked_at=CUTOFF,
        selectors=(
            SelectorEvidence(
                selector_kind="risk_topic",
                selector_value="prompt_injection",
                claim_id="fixture-claim",
                claim_status="supported",
                claim_origin="source_explicit",
                support_kind="supports",
                validation_status="validated",
                citations=(
                    dict(
                        evidence_id=UUID(int=1),
                        revision_id=UUID(int=2),
                        quote=quote,
                        locator=f"text[0:{len(quote)}]",
                        source_uri="https://fixture.example/evidence",
                    ),
                ),
            ),
        ),
    )


def test_internal_report_roundtrip_preserves_identity_evidence_and_time_basis():
    batch = generate_recommendation_candidates(
        fixture_subscription(), (fixture_event(),), cutoff_at=CUTOFF
    )
    report = build_report_candidate(batch, frequency="day", cutoff_at=CUTOFF, generated_at=CUTOFF)
    restored = ReportCandidate.model_validate_json(report.model_dump_json())
    assert restored == report
    payload = restored.model_dump(mode="json")
    assert payload["policy_version"] == "r15-recommendation-policy-1"
    assert payload["temporal_mode"] == "as_of_cutoff"
    assert payload["window_basis"] == "first_material_observed_at"
    assert payload["intelligence_updates"][0]["reasons"][0]["citations"][0]["revision_id"] == str(
        UUID(int=2)
    )


@pytest.mark.parametrize(
    "updates",
    [
        dict(enabled=1),
        dict(maximum_priority_bucket=True),
        dict(maximum_priority_bucket=-1),
        dict(product_keys=("p", "p")),
        dict(risk_topics=()),
        dict(authorization="admin"),
    ],
)
def test_subscription_rejects_ambiguous_fields_and_empty_interest(updates):
    payload = fixture_subscription().model_dump(mode="python")
    payload.update(updates)
    with pytest.raises(ValidationError):
        RecommendationSubscription.model_validate(payload)


@pytest.mark.parametrize(
    "updates",
    [
        dict(observed_at="2026-10-16T00:00:00"),
        dict(valid_until=CUTOFF),
        dict(tenant_id="request-tenant"),
        dict(status_at_cutoff="safe"),
        dict(freshness_at_cutoff="live"),
    ],
)
def test_event_contract_rejects_naive_time_inverted_interval_and_auth_claims(updates):
    payload = fixture_event().model_dump(mode="python")
    payload.update(updates)
    with pytest.raises(ValidationError):
        RecommendationEventInput.model_validate(payload)


def test_unbounded_quote_or_missing_selector_citation_is_rejected():
    payload = fixture_event().selectors[0].model_dump(mode="python")
    for citations in ((), ({**payload["citations"][0], "quote": "x" * 2001},)):
        with pytest.raises(ValidationError):
            SelectorEvidence.model_validate({**payload, "citations": citations})


def test_internal_contract_exposes_original_assessment_receipt_type():
    schema = RecommendationEventInput.model_json_schema()
    assert schema["properties"]["assessments"]["items"]["$ref"] == "#/$defs/AssessmentReceipt"
    assert schema["$defs"]["AssessmentReceipt"]["properties"]["status"]["$ref"] == (
        "#/$defs/AssessmentStatus"
    )
    assert schema["$defs"]["AssessmentStatus"]["enum"] == [
        "supported_applicability",
        "excluded_with_evidence",
        "insufficient_evidence",
        "conflicting_evidence",
    ]


@pytest.mark.parametrize(
    "updates", [dict(eligible_count=2), dict(partial=True), dict(stop_reason="item_budget")]
)
def test_batch_contract_cannot_hide_partial_output_or_fabricate_complete_count(updates):
    batch = generate_recommendation_candidates(
        fixture_subscription(), (fixture_event(),), cutoff_at=CUTOFF
    )
    with pytest.raises(ValidationError):
        RecommendationBatch.model_validate({**batch.model_dump(mode="python"), **updates})


@pytest.mark.parametrize(
    "payload",
    [
        dict(code="product_match", matched_key="product"),
        dict(code="asset_assessment", matched_key="asset", claim_id="claim"),
        dict(
            code="high_consequence",
            matched_key="high",
            claim_id="claim",
            assessment_id="assessment",
        ),
    ],
)
def test_reason_contract_requires_the_right_support_object(payload):
    with pytest.raises(ValidationError):
        RecommendationReason.model_validate(payload)
