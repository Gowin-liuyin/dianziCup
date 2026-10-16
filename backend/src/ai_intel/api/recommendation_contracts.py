"""Strict public v1 inputs and the minimal completed generation response."""

from __future__ import annotations

import re
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BeforeValidator, Field, model_validator

from ai_intel.assessment.conditions import ConditionContract
from ai_intel.recommendations.service_contracts import (
    CandidateGap,
    GenerationReceipt,
    SubscriptionSpec,
)

PublicLabel = Annotated[str, Field(strict=True, min_length=1, max_length=200)]
ExpectedVersion = Annotated[int, Field(strict=True, ge=1)]


def public_uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    if (
        not isinstance(value, str)
        or re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", value
        )
        is None
    ):
        raise ValueError("uuid_format_invalid")
    return UUID(value)


PublicUUID = Annotated[UUID, BeforeValidator(public_uuid)]


class PublicSubscriptionSpec(ConditionContract):
    product_keys: tuple[PublicLabel, ...] = Field(default=(), max_length=100)
    asset_ids: tuple[PublicUUID, ...] = Field(default=(), max_length=100)
    risk_topics: tuple[PublicLabel, ...] = Field(default=(), max_length=100)
    minimum_priority: int = Field(default=3, strict=True, ge=0, le=3)
    enabled: bool = Field(default=True, strict=True)

    @model_validator(mode="after")
    def validate_explicit_interests(self) -> PublicSubscriptionSpec:
        self.internal_spec()
        return self

    def internal_spec(self) -> SubscriptionSpec:
        return SubscriptionSpec(
            product_keys=self.product_keys,
            asset_ids=self.asset_ids,
            risk_topics=self.risk_topics,
            maximum_priority_bucket=self.minimum_priority,
            enabled=self.enabled,
        )


class CreateSubscription(ConditionContract):
    spec: PublicSubscriptionSpec


class ReplaceSubscription(ConditionContract):
    expected_version: ExpectedVersion
    spec: PublicSubscriptionSpec


class SetSubscriptionEnabled(ConditionContract):
    expected_version: ExpectedVersion
    enabled: bool = Field(strict=True)


SubscriptionPatch = ReplaceSubscription | SetSubscriptionEnabled


class GenerateRecommendations(ConditionContract):
    max_candidates: int = Field(default=200, strict=True, ge=1, le=200)


class CreateReport(ConditionContract):
    subscription_id: PublicUUID
    generation_id: PublicUUID
    frequency: Literal["day", "week"]
    max_items: int = Field(default=20, strict=True, ge=1, le=200)


class GenerationResponse(ConditionContract):
    generation_id: UUID
    recommendation_ids: tuple[UUID, ...] = Field(max_length=200)
    partial: bool = Field(strict=True)
    gaps: tuple[CandidateGap, ...] = Field(max_length=2000)
    reused: bool = Field(strict=True)
    data_mode: Literal["live", "fixture"]

    @classmethod
    def from_receipt(cls, receipt: GenerationReceipt) -> GenerationResponse:
        return cls(
            generation_id=receipt.generation_id,
            recommendation_ids=receipt.recommendation_ids,
            partial=receipt.content.partial,
            gaps=receipt.content.gaps,
            reused=receipt.reused,
            data_mode=receipt.content.data_mode,
        )
