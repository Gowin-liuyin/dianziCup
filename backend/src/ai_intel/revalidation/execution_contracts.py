"""Internal bounded plans distinguish candidate discovery from committed reassessment."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ai_intel.assessment.conditions import ConditionContract, Label
from ai_intel.assessment.persistence_contracts import AssessmentReceipt
from ai_intel.domain.values import UtcTimestamp

ScopeEpoch = Annotated[int, Field(ge=0, strict=True)]


class ReassessmentTarget(ConditionContract):
    asset_id: Label
    asset_snapshot_id: Label
    rule_id: Label
    rule_version: int = Field(ge=1, strict=True)


class RevalidationPlan(ConditionContract):
    schema_version: Literal["r16-assessment-plan-1"] = "r16-assessment-plan-1"
    change_id: Label
    actor_user_id: Label
    tenant_id: Label
    permission_version: int = Field(ge=1, strict=True)
    permissions_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    requested_epoch: int = Field(ge=0, strict=True)
    target_epoch: int = Field(ge=0, strict=True)
    scope_epoch_map: dict[str, ScopeEpoch | None]
    rule_scope_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    assessment_created_before: UtcTimestamp
    continuation: str | None = Field(default=None, max_length=4096)
    next_rule_after_id: Label | None = None
    targets: tuple[ReassessmentTarget, ...] = Field(max_length=1000)
    candidate_count: int = Field(ge=0, le=1000, strict=True)
    planning_status: Literal["complete", "partial"]
    incomplete_reasons: tuple[str, ...] = Field(max_length=8)

    @model_validator(mode="after")
    def require_explicit_plan_limits(self) -> "RevalidationPlan":
        if (self.planning_status == "partial") != bool(self.incomplete_reasons):
            raise ValueError("partial planning requires explicit incomplete reasons")
        identities = [(item.asset_id, item.rule_id) for item in self.targets]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate reassessment target")
        if self.target_epoch < self.requested_epoch:
            raise ValueError("plan target cannot precede requested epoch")
        if set(self.scope_epoch_map) != {"public", "tenant:" + self.tenant_id}:
            raise ValueError("plan requires exact authorized scope epochs")
        if any(
            value is not None and (type(value) is not int or value < 0)
            for value in self.scope_epoch_map.values()
        ):
            raise ValueError("plan scope epoch is invalid")
        return self


class ReassessmentOutcome(ConditionContract):
    assessment: AssessmentReceipt
    execution_status: Literal["succeeded", "partial"]
    incomplete_reasons: tuple[str, ...] = Field(max_length=8)

    @model_validator(mode="after")
    def require_explicit_execution_limits(self) -> "ReassessmentOutcome":
        if (self.execution_status == "partial") != bool(self.incomplete_reasons):
            raise ValueError("partial reassessment requires explicit incomplete reasons")
        return self


class ReassessmentRequest(ConditionContract):
    schema_version: Literal["r16-assessment-job-1"] = "r16-assessment-job-1"
    change_id: Label
    target_epoch: int = Field(ge=0, strict=True)
    asset_id: Label
    asset_snapshot_id: Label
    rule_id: Label
    rule_version: int = Field(ge=1, strict=True)


class RevalidationChangeRequest(ConditionContract):
    schema_version: Literal["r16-change-job-1"] = "r16-change-job-1"
    change_id: Label
    target_epoch: int = Field(ge=0, strict=True)
    assessment_created_before: UtcTimestamp
    continuation: str | None = Field(default=None, max_length=4096)
    rule_after_id: Label | None = None
    frozen_scope_epoch_map: dict[str, ScopeEpoch | None] | None = None
    frozen_rule_scope_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    remaining_pages: int = Field(default=100, ge=1, le=100, strict=True)
    remaining_children: int = Field(default=1000, ge=1, le=1000, strict=True)

    @model_validator(mode="after")
    def require_paired_continuation_context(self) -> "RevalidationChangeRequest":
        if (self.frozen_scope_epoch_map is None) != (self.frozen_rule_scope_fingerprint is None):
            raise ValueError("frozen continuation context requires epochs and rule scope")
        if self.frozen_scope_epoch_map is not None and not self.frozen_scope_epoch_map:
            raise ValueError("frozen continuation epochs cannot be empty")
        return self
