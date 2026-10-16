"""Internal PG service inputs contain no client-supplied tenant, user or validation grants."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from ai_intel.assessment.conditions import ConditionContract, Label
from ai_intel.domain.access import Role
from ai_intel.domain.values import UtcTimestamp
from ai_intel.recommendations.contracts import (
    MAX_CANDIDATES,
    MAX_INPUT_EVENTS,
    RecommendationBatch,
    RecommendationCandidate,
    RecommendationKey,
    RecommendationSubscription,
    ReportCandidate,
)

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Version = Annotated[int, Field(strict=True, ge=1)]
ItemBudget = Annotated[int, Field(strict=True, ge=1, le=MAX_CANDIDATES)]
Epoch = Annotated[int, Field(strict=True, ge=0)]
CurrentStatus = Literal["current", "stale", "withdrawn", "unknown"]


def canonical_json_bytes(value: object) -> bytes:
    """Stored content is finite JSON, with stable keys and no repr/default conversion."""

    def require_json_keys(item: object) -> None:
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError("canonical_json_requires_string_keys")
            for child in item.values():
                require_json_keys(child)
        elif isinstance(item, list | tuple):
            for child in item:
                require_json_keys(child)

    require_json_keys(value)
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def content_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


class SubscriptionSpec(ConditionContract):
    """Internal spec; public minimum_priority mapping is owned by the API adapter."""

    product_keys: tuple[Label, ...] = Field(default=(), max_length=100)
    asset_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    risk_topics: tuple[Label, ...] = Field(default=(), max_length=100)
    maximum_priority_bucket: int = Field(default=3, strict=True, ge=0, le=3)
    enabled: bool = Field(default=True, strict=True)

    @model_validator(mode="after")
    def require_explicit_distinct_interests(self) -> SubscriptionSpec:
        if not (self.product_keys or self.asset_ids or self.risk_topics):
            raise ValueError("subscription_requires_explicit_interest")
        for values in (self.product_keys, self.asset_ids, self.risk_topics):
            if len(values) != len(set(values)):
                raise ValueError("duplicate_subscription_interest")
        return self


class SubscriptionRecord(ConditionContract):
    schema_version: Literal["r15-subscription-1"] = "r15-subscription-1"
    subscription_id: UUID
    tenant_id: Label
    user_id: Label
    version: Version
    spec: SubscriptionSpec
    spec_sha256: Digest
    created_at: UtcTimestamp
    updated_at: UtcTimestamp

    @model_validator(mode="after")
    def require_spec_receipt_hash(self) -> SubscriptionRecord:
        if self.spec_sha256 != content_sha256(self.spec.model_dump(mode="json")):
            raise ValueError("subscription_spec_receipt_hash_mismatch")
        if self.updated_at < self.created_at:
            raise ValueError("subscription_time_order_invalid")
        return self

    def policy_subscription(self) -> RecommendationSubscription:
        return RecommendationSubscription(
            subscription_id=str(self.subscription_id),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            product_keys=self.spec.product_keys,
            asset_ids=tuple(str(value) for value in self.spec.asset_ids),
            risk_topics=self.spec.risk_topics,
            maximum_priority_bucket=self.spec.maximum_priority_bucket,
            enabled=self.spec.enabled,
        )


class CandidateGap(ConditionContract):
    event_id: UUID | None = None
    asset_id: UUID | None = None
    code: Literal[
        "no_current_semantic_support",
        "selector_evidence_budget_exceeded",
        "claim_not_current",
        "source_time_unavailable",
        "assessment_not_current",
        "assessment_unavailable",
        "graph_partial",
        "source_withdrawn",
        "event_not_active",
        "unsupported_topic",
        "input_scope_partial",
        "consequence_selector_unavailable",
    ]


class PreparedGeneration(ConditionContract):
    """Server-only receipt; commit rebuilds its facts and output instead of trusting a body."""

    subscription_id: UUID
    subscription_version: Version
    subscription_sha256: Digest
    actor_user_id: Label
    actor_tenant_id: Label
    actor_role: Role
    permission_version: Version
    cutoff_at: UtcTimestamp
    event_ids: tuple[UUID, ...] = Field(max_length=MAX_INPUT_EVENTS)
    max_candidates: ItemBudget
    scope_epochs: dict[str, Epoch | None]
    input_sha256: Digest
    existing_keys: tuple[RecommendationKey, ...] = Field(max_length=MAX_INPUT_EVENTS)


class GenerationContent(ConditionContract):
    schema_version: Literal["r15-generation-1"] = "r15-generation-1"
    subscription: SubscriptionRecord
    batch: RecommendationBatch
    report_batch: RecommendationBatch
    gaps: tuple[CandidateGap, ...]
    event_ids: tuple[UUID, ...] = Field(max_length=MAX_INPUT_EVENTS)
    scope_epochs: dict[str, Epoch | None]
    input_sha256: Digest
    material_versions: dict[str, str]
    partial: bool = Field(strict=True)
    data_mode: Literal["live", "fixture"]

    @model_validator(mode="after")
    def require_generation_bindings(self) -> GenerationContent:
        expected = self.subscription.policy_subscription()
        if (
            self.batch.subscription != expected
            or self.report_batch.subscription != expected
            or self.batch.cutoff_at != self.report_batch.cutoff_at
        ):
            raise ValueError("generation_subscription_binding_mismatch")
        roster = {str(value) for value in self.event_ids}
        if len(roster) != len(self.event_ids) or set(self.material_versions) - roster:
            raise ValueError("generation_event_roster_mismatch")
        for version in self.material_versions.values():
            if len(version) != 64 or any(
                character not in "0123456789abcdef" for character in version
            ):
                raise ValueError("generation_material_hash_invalid")
        for batch in (self.batch, self.report_batch):
            for candidate in batch.candidates:
                if (candidate.tenant_id, candidate.user_id, candidate.validity_as_of) != (
                    expected.tenant_id,
                    expected.user_id,
                    batch.cutoff_at,
                ) or self.material_versions.get(
                    candidate.key.event_id
                ) != candidate.key.material_version:
                    raise ValueError("generation_candidate_binding_mismatch")
        if (self.batch.partial or self.report_batch.partial) and not self.partial:
            raise ValueError("generation_partial_mismatch")
        return self


class GenerationReceipt(ConditionContract):
    generation_id: UUID
    content_sha256: Digest
    content: GenerationContent
    recommendation_ids: tuple[UUID, ...] = Field(max_length=MAX_CANDIDATES)
    reused: bool = Field(default=False, strict=True)


class RecommendationRecord(ConditionContract):
    recommendation_id: UUID
    generation_id: UUID
    content_sha256: Digest
    content: RecommendationCandidate
    created_at: UtcTimestamp
    read_at: UtcTimestamp | None
    current_status: CurrentStatus
    current_reason: Label
    current_checked_at: UtcTimestamp


class StoredReportContent(ConditionContract):
    schema_version: Literal["r15-report-1"] = "r15-report-1"
    report: ReportCandidate
    generation_id: UUID
    event_ids: tuple[UUID, ...] = Field(max_length=MAX_INPUT_EVENTS)
    data_mode: Literal["live", "fixture"]
    gaps: tuple[CandidateGap, ...] = ()
    max_items: ItemBudget

    @model_validator(mode="after")
    def require_report_bindings(self) -> StoredReportContent:
        candidates = (
            self.report.supported_risks
            + self.report.verification_items
            + self.report.excluded_items
            + self.report.intelligence_updates
        )
        roster = {str(value) for value in self.event_ids}
        if len(roster) != len(self.event_ids) or len(candidates) > self.max_items:
            raise ValueError("stored_report_roster_or_budget_mismatch")
        for candidate in candidates:
            if (
                candidate.tenant_id,
                candidate.user_id,
                candidate.key.subscription_id,
                candidate.validity_as_of,
            ) != (
                self.report.tenant_id,
                self.report.user_id,
                self.report.subscription_id,
                self.report.cutoff_at,
            ) or candidate.key.event_id not in roster:
                raise ValueError("stored_report_candidate_binding_mismatch")
        return self


class ReportReceipt(ConditionContract):
    report_id: UUID
    content_sha256: Digest
    content: StoredReportContent
    current_status: CurrentStatus
    current_reason: Label
    current_checked_at: UtcTimestamp
    reused: bool = Field(default=False, strict=True)


class SubscriptionPage(ConditionContract):
    items: tuple[SubscriptionRecord, ...] = Field(max_length=MAX_CANDIDATES)
    next_cursor: UUID | None = None


class RecommendationPage(ConditionContract):
    items: tuple[RecommendationRecord, ...] = Field(max_length=MAX_CANDIDATES)
    next_cursor: UUID | None = None


class ReportPage(ConditionContract):
    items: tuple[ReportReceipt, ...] = Field(max_length=MAX_CANDIDATES)
    next_cursor: UUID | None = None


class RecommendationConflictError(ValueError):
    """Fixed CAS/conflict reasons never include private target contents."""


class RecommendationIntegrityError(ValueError):
    """Stored canonical payload disagrees with its immutable receipt."""
