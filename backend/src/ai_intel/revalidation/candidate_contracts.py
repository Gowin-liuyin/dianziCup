"""Internal candidate receipts describe discovery, never a completed reassessment."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ai_intel.assessment.conditions import ConditionContract, Label

CandidateReason = Literal[
    "old_dependency",
    "scope_watch",
    "new_package_association",
    "empty_rule_scope",
    "partition_fallback",
    "missing_scope_watch",
]
ScopeKey = Annotated[str, Field(min_length=1, max_length=207)]


class AssessmentChangeCandidate(ConditionContract):
    asset_id: Label
    asset_snapshot_id: Label
    assessment_id: Label | None = None
    previous_asset_snapshot_id: Label | None = None
    watch_assessment_id: Label | None = None
    reasons: tuple[CandidateReason, ...] = Field(min_length=1, max_length=6)


class CandidateContinuation(ConditionContract):
    schema_version: Literal["r16-candidate-cursor-1"] = "r16-candidate-cursor-1"
    change_id: Label
    scope_key: ScopeKey
    actor_user_id: Label
    tenant_id: Label
    actor_role: Label
    permission_version: int = Field(ge=1, strict=True)
    requested_epoch: int = Field(ge=0, strict=True)
    scope_epoch_map: dict[str, int | None]
    query_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    partition_fingerprint: str = Field(pattern=r"^[0-9a-f]{32}$")
    limit: int = Field(ge=1, le=100, strict=True)
    after_asset_id: Label
    after_kind: Literal["asset", "assessment"]
    after_reference_id: Label


class CandidatePage(ConditionContract):
    schema_version: Literal["r16-assessment-candidates-1"] = "r16-assessment-candidates-1"
    change_id: Label
    scope_key: ScopeKey
    requested_epoch: int = Field(ge=0, strict=True)
    target_epoch: int = Field(ge=0, strict=True)
    scope_epoch_map: dict[str, int | None]
    candidates: tuple[AssessmentChangeCandidate, ...] = Field(max_length=100)
    status: Literal["complete", "partial"]
    continuation: str | None = Field(default=None, max_length=4096)
    scanned_count: int = Field(ge=0, le=500, strict=True)
    fallback_reason: str | None = None

    @model_validator(mode="after")
    def require_explicit_continuation(self) -> "CandidatePage":
        if (self.status == "partial") != (self.continuation is not None):
            raise ValueError("partial discovery requires continuation")
        keys = [(item.asset_id, item.assessment_id) for item in self.candidates]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate candidate identity")
        return self
