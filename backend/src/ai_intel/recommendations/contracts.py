"""Internal R15 candidates over server-authorized snapshots; these DTOs grant no access."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ai_intel.api.knowledge_contracts import CitationProjection
from ai_intel.assessment.conditions import ConditionContract, EvidenceReference, Label
from ai_intel.assessment.persistence_contracts import AssessmentReceipt
from ai_intel.domain.enums import AssessmentStatus, ClaimOrigin, ClaimStatus, FreshnessStatus
from ai_intel.domain.values import UtcTimestamp

POLICY_VERSION: Literal["r15-recommendation-policy-1"] = "r15-recommendation-policy-1"
MAX_INPUT_EVENTS = 2000
MAX_CANDIDATES = 200
Priority = Annotated[int, Field(strict=True, ge=0, le=3)]
CandidateKind = Literal[
    "supported_risk", "prioritize_verification", "excluded_with_evidence", "intelligence_update"
]
ReportStopReason = Literal["disabled", "no_items_in_window", "complete", "item_budget"]


class RecommendationSubscription(ConditionContract):
    subscription_id: Label
    tenant_id: Label
    user_id: Label
    enabled: bool = Field(strict=True)
    product_keys: tuple[Label, ...] = Field(default=(), max_length=100)
    asset_ids: tuple[Label, ...] = Field(default=(), max_length=100)
    risk_topics: tuple[Label, ...] = Field(default=(), max_length=100)
    maximum_priority_bucket: Priority = 3

    @model_validator(mode="after")
    def require_explicit_interests(self) -> RecommendationSubscription:
        if not (self.product_keys or self.asset_ids or self.risk_topics):
            raise ValueError("subscription_requires_explicit_interest")
        for values in (self.product_keys, self.asset_ids, self.risk_topics):
            if len(values) != len(set(values)):
                raise ValueError("duplicate_subscription_interest")
        return self


class SelectorEvidence(ConditionContract):
    """PG caller verified the exact selector/claim/citation support, beyond quote existence."""

    selector_kind: Literal["product", "risk_topic", "consequence"]
    selector_value: Label
    claim_id: Label
    claim_status: ClaimStatus
    claim_origin: ClaimOrigin
    support_kind: Literal["supports", "refutes", "context"]
    validation_status: Literal["validated", "unverified"]
    citations: tuple[CitationProjection, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def bound_citation_size(self) -> SelectorEvidence:
        if any(len(citation.quote) > 2000 for citation in self.citations):
            raise ValueError("selector_quote_budget_exceeded")
        return self


class RecommendationEventInput(ConditionContract):
    """As-of state and current state are distinct; observed_at is first material observation.

    material_version must include changed assessments/rules/assets as well as event facts.
    A historical caller must supply receipts valid at cutoff, never relabel current receipts.
    """

    event_id: Label
    material_version: Label
    observed_at: UtcTimestamp
    source_changed_at: UtcTimestamp | None = None
    valid_from: UtcTimestamp
    valid_until: UtcTimestamp | None = None
    status_at_cutoff: ClaimStatus
    freshness_at_cutoff: FreshnessStatus
    current_status: ClaimStatus
    current_freshness: FreshnessStatus
    current_state_checked_at: UtcTimestamp
    selectors: tuple[SelectorEvidence, ...] = Field(default=(), max_length=32)
    assessments: tuple[AssessmentReceipt, ...] = Field(default=(), max_length=20)

    @model_validator(mode="after")
    def require_valid_interval(self) -> RecommendationEventInput:
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("event_valid_interval_inverted")
        if self.current_state_checked_at < self.observed_at:
            raise ValueError("current_check_precedes_observation")
        return self


class RecommendationKey(ConditionContract):
    subscription_id: Label
    event_id: Label
    material_version: Label


class RecommendationReason(ConditionContract):
    code: Literal["product_match", "risk_topic_match", "asset_assessment", "high_consequence"]
    matched_key: Label
    claim_id: Label | None = None
    citations: tuple[CitationProjection, ...] = ()
    assessment_id: Label | None = None

    @model_validator(mode="after")
    def require_reason_support(self) -> RecommendationReason:
        if self.code == "asset_assessment":
            if self.assessment_id is None or self.claim_id is not None or self.citations:
                raise ValueError("asset_reason_requires_receipt_reference")
        elif self.claim_id is None or not self.citations or self.assessment_id is not None:
            raise ValueError("selector_reason_requires_claim_and_citations")
        return self


class AssessmentReference(ConditionContract):
    """Original receipt result and evidence, retained without reevaluation."""

    assessment_id: Label
    asset_id: Label
    asset_snapshot_id: Label
    rule_id: Label
    rule_version: int = Field(strict=True, ge=1)
    status: AssessmentStatus
    knowledge_epoch: int | None
    scope_epoch_map: dict[str, int | None]
    input_digest: str
    evidence: tuple[EvidenceReference, ...]
    missing_requirements: tuple[str, ...]
    conflicts: tuple[str, ...]
    limitations: tuple[str, ...]


class RecommendationCandidate(ConditionContract):
    key: RecommendationKey
    tenant_id: Label
    user_id: Label
    policy_version: Literal["r15-recommendation-policy-1"] = POLICY_VERSION
    kind: CandidateKind
    priority_bucket: Priority
    reasons: tuple[RecommendationReason, ...]
    assessments: tuple[AssessmentReference, ...]
    observed_at: UtcTimestamp
    source_changed_at: UtcTimestamp | None
    valid_from: UtcTimestamp
    valid_until: UtcTimestamp | None
    validity_as_of: UtcTimestamp
    freshness_at_cutoff: FreshnessStatus
    current_status: ClaimStatus
    current_freshness: FreshnessStatus
    current_state_checked_at: UtcTimestamp
    limitations: tuple[str, ...]


class RecommendationBatch(ConditionContract):
    subscription: RecommendationSubscription
    cutoff_at: UtcTimestamp
    candidates: tuple[RecommendationCandidate, ...] = Field(max_length=MAX_CANDIDATES)
    eligible_count: int = Field(strict=True, ge=0, le=MAX_INPUT_EVENTS)
    partial: bool = Field(strict=True)
    continuation_keys: tuple[RecommendationKey, ...] = Field(max_length=MAX_INPUT_EVENTS)
    stop_reason: Literal["disabled", "no_supported_subscription_match", "complete", "item_budget"]

    @model_validator(mode="after")
    def require_explicit_completeness(self) -> RecommendationBatch:
        if self.partial != bool(self.continuation_keys) or self.eligible_count != (
            len(self.candidates) + len(self.continuation_keys)
        ):
            raise ValueError("batch_completeness_mismatch")
        keys = tuple(candidate.key for candidate in self.candidates) + self.continuation_keys
        identities = {(key.subscription_id, key.event_id, key.material_version) for key in keys}
        if len(identities) != len(keys) or any(
            key.subscription_id != self.subscription.subscription_id for key in keys
        ):
            raise ValueError("batch_key_binding_mismatch")
        expected_reason = (
            "disabled"
            if not self.subscription.enabled
            else (
                "item_budget"
                if self.partial
                else ("complete" if self.candidates else "no_supported_subscription_match")
            )
        )
        if self.stop_reason != expected_reason or (
            not self.subscription.enabled and self.eligible_count
        ):
            raise ValueError("batch_stop_reason_mismatch")
        return self


class ReportCandidate(ConditionContract):
    """An immutable report proposal, not a persisted report or a statement of current truth."""

    policy_version: Literal["r15-recommendation-policy-1"] = POLICY_VERSION
    subscription_id: Label
    tenant_id: Label
    user_id: Label
    frequency: Literal["day", "week"]
    window_start: UtcTimestamp
    cutoff_at: UtcTimestamp
    generated_at: UtcTimestamp
    temporal_mode: Literal["as_of_cutoff"] = "as_of_cutoff"
    window_basis: Literal["first_material_observed_at"] = "first_material_observed_at"
    supported_risks: tuple[RecommendationCandidate, ...]
    verification_items: tuple[RecommendationCandidate, ...]
    excluded_items: tuple[RecommendationCandidate, ...]
    intelligence_updates: tuple[RecommendationCandidate, ...]
    partial: bool = Field(strict=True)
    continuation_keys: tuple[RecommendationKey, ...]
    stop_reason: ReportStopReason
    limitations: tuple[str, ...]
