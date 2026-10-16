"""Public fixed-snapshot assessment projection; internal preparation inputs stay private."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from ai_intel.assessment.conditions import ConditionContract, Label
from ai_intel.assessment.persistence_contracts import AssessmentReceipt
from ai_intel.assessment.rules import RuleEvaluation
from ai_intel.domain.enums import AssessmentStatus, FreshnessStatus
from ai_intel.domain.values import UtcTimestamp

MAX_ASSESSMENT_BODY_BYTES = 4096


class AssessmentRequest(ConditionContract):
    asset_id: UUID
    asset_snapshot_id: UUID
    rule_id: Label
    rule_version: int = Field(ge=1, le=2147483647, strict=True)


class AssessmentResponse(ConditionContract):
    schema_version: Literal["r11-assessment-http-1"] = "r11-assessment-http-1"
    assessment_id: Label
    tenant_id: Label
    asset_id: Label
    asset_snapshot_id: Label
    event_id: Label
    rule_id: Label
    rule_version: int
    knowledge_epoch: int | None
    scope_epoch_map: dict[str, int | None]
    rule_result: RuleEvaluation | None
    status: AssessmentStatus
    freshness: FreshnessStatus
    missing_requirements: tuple[str, ...]
    conflicts: tuple[str, ...]
    limitations: tuple[str, ...]
    exposure_result: Literal["not_evaluated", "observed_path_only"]
    exploit_evidence_status: Literal["not_verified"] = "not_verified"
    input_digest: str
    created_at: UtcTimestamp
    reused: bool = False

    @classmethod
    def from_receipt(cls, receipt: AssessmentReceipt) -> "AssessmentResponse":
        return cls.model_validate(
            receipt.model_dump(mode="python", exclude={"prepared", "schema_version"})
        )
