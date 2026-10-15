"""Internal immutable receipts; current facts and permissions always come from PostgreSQL."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ai_intel.assessment.conditions import ConditionContract, EvidenceReference, Label
from ai_intel.assessment.rules import ConditionRule, RuleEvaluation, RuleValidationResult
from ai_intel.assets.inventory_contracts import AssetSnapshotResponse
from ai_intel.assets.manifest_parser import MAX_COMPONENTS, MAX_STRING_LENGTH
from ai_intel.domain.enums import AssessmentStatus, FreshnessStatus
from ai_intel.domain.values import UtcTimestamp, VisibilityScope

PackageScopeKey = Annotated[str, Field(min_length=1, max_length=2 * MAX_STRING_LENGTH + 1)]
ASSESSMENT_POLICY_VERSION: Literal["r11-pg-assessment-1"] = "r11-pg-assessment-1"


class RuleSupportBinding(ConditionContract):
    node_id: Label
    claim_id: Label
    evidence_id: Label


class SourceInput(ConditionContract):
    source_id: Label
    document_id: Label
    revision_id: Label
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    revision_number: int
    is_current: bool
    parse_status: str
    source_scope: VisibilityScope
    document_scope: VisibilityScope
    revision_scope: VisibilityScope
    source_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class CheckedSupport(ConditionContract):
    binding: RuleSupportBinding
    condition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    claim_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    review_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence: EvidenceReference
    semantic_status: Literal["supports", "refutes", "pending"]
    range_completeness_confirmed: bool


class RuleInputSnapshot(ConditionContract):
    rule: ConditionRule
    author_user_id: Label
    event_version: int
    event_status: str
    sources: tuple[SourceInput, ...] = Field(max_length=20)
    active_revision_ids: tuple[Label, ...] = Field(max_length=20)
    supports: tuple[CheckedSupport, ...] = Field(max_length=64)
    scope_epoch_map: dict[str, int | None]
    validation: RuleValidationResult
    input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class AssessmentScopeWatch(ConditionContract):
    tenant_id: Label
    event_ids: tuple[Label, ...] = Field(min_length=1, max_length=20)
    package_keys: tuple[PackageScopeKey, ...] = Field(max_length=MAX_COMPONENTS + 64)
    rule_id: Label
    rule_version: int = Field(ge=1, strict=True)
    rule_kind: str
    scope_epoch_map: dict[str, int | None]
    selected_rule_ids: tuple[Label, ...] = Field(max_length=64)
    no_published_rule: bool

    @model_validator(mode="after")
    def require_scope_snapshot(self) -> AssessmentScopeWatch:
        if not self.scope_epoch_map or any(
            value is not None and value < 0 for value in self.scope_epoch_map.values()
        ):
            raise ValueError("scope watch requires explicit epochs")
        if self.no_published_rule != (not self.selected_rule_ids):
            raise ValueError("empty rule scope must be explicit")
        return self


class PreparedAssessment(ConditionContract):
    preparation_receipt_id: Label
    actor_user_id: Label
    actor_role: str
    permission_version: int
    asset_snapshot: AssetSnapshotResponse
    asset_active: bool
    asset_current_snapshot_id: Label
    asset_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    inputs: RuleInputSnapshot
    scope_watch: AssessmentScopeWatch
    input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class AssessmentReceipt(ConditionContract):
    schema_version: Literal["r11-pg-assessment-1"] = ASSESSMENT_POLICY_VERSION
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
    prepared: PreparedAssessment
    input_digest: str
    created_at: UtcTimestamp
    reused: bool = False
