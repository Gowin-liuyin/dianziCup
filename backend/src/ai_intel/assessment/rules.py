"""Pure eligibility checks; PostgreSQL owns publication and rechecks source ACL/coordinates."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ai_intel.assessment.conditions import (
    CONDITION_SCHEMA_VERSION,
    AllOf,
    AnyOf,
    ConditionContract,
    ConditionEvaluation,
    ConditionFact,
    ConditionNode,
    EvidenceReference,
    Label,
    RuleKind,
    VersionInRange,
    condition_digest,
    evaluate_condition_tree,
    iter_condition_nodes,
    parse_condition_tree,
)
from ai_intel.assets.inventory_contracts import AssetSnapshotResponse
from ai_intel.domain.access import READ_PUBLIC, AccessScope
from ai_intel.domain.enums import (
    AssessmentStatus,
    ClaimOrigin,
    ClaimStatus,
    ConditionValue,
    RuleStatus,
)
from ai_intel.domain.values import UtcTimestamp, VisibilityScope

VALIDATOR_VERSION = "r11-rule-validator-1"
DEFINED_PREDICATES = frozenset(
    {
        "component_matches",
        "version_in_range",
        "configuration_equals",
        "permission_includes",
        "input_channel_enabled",
        "network_reachable",
        "inventory_proves_absence",
        "mitigation_confirmed",
    }
)


class ConditionRule(ConditionContract):
    schema_version: Literal["r11-condition-1"] = CONDITION_SCHEMA_VERSION
    rule_id: Label
    version: int = Field(ge=1, strict=True)
    event_id: Label
    rule_kind: RuleKind
    condition_ast: ConditionNode
    supporting_claim_ids: tuple[Label, ...] = Field(max_length=64)
    source_span_ids: tuple[Label, ...] = Field(max_length=64)
    scope: VisibilityScope
    status: RuleStatus
    published_at: UtcTimestamp | None = None
    retired_at: UtcTimestamp | None = None

    @model_validator(mode="after")
    def require_lifecycle_consistency(self) -> ConditionRule:
        parse_condition_tree(self.condition_ast.model_dump(mode="python"))
        if (self.status in {RuleStatus.PUBLISHED, RuleStatus.RETIRED}) != (
            self.published_at is not None
        ):
            raise ValueError("published lifecycle timestamp mismatch")
        if (self.status == RuleStatus.RETIRED) != (self.retired_at is not None):
            raise ValueError("retired lifecycle timestamp mismatch")
        if self.retired_at and self.published_at and self.retired_at < self.published_at:
            raise ValueError("retirement cannot precede publication")
        for refs in (self.supporting_claim_ids, self.source_span_ids):
            if len(refs) != len(set(refs)):
                raise ValueError("duplicate rule reference")
        return self


class RuleLeafSupport(ConditionContract):
    """Exact leaf digest binds support; caller must confirm this relationship in PG."""

    node_id: Label
    condition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    claim_id: Label
    claim_status: ClaimStatus
    claim_origin: ClaimOrigin
    condition_scope: RuleKind
    source_id: Label
    document_id: Label
    source_revision_id: Label
    scope: VisibilityScope
    evidence: tuple[EvidenceReference, ...] = Field(max_length=64)
    necessary_condition_supported: bool = Field(strict=True)
    range_completeness_confirmed: bool = Field(default=False, strict=True)


class RuleValidationPolicy(ConditionContract):
    """Versioned server configuration; never supplied or widened by a model/request."""

    policy_version: Label
    approved_schema_version: Literal["r11-condition-1"] = CONDITION_SCHEMA_VERSION
    approved_predicates: frozenset[str]
    automatic_publication_enabled: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def require_known_predicates(self) -> RuleValidationPolicy:
        if not self.approved_predicates <= DEFINED_PREDICATES:
            raise ValueError("policy cannot authorize an undefined predicate")
        return self


class RuleValidationResult(ConditionContract):
    rule_id: Label
    rule_version: int
    schema_version: str
    validator_version: str = VALIDATOR_VERSION
    policy_version: str
    condition_sha256: str
    eligible: bool
    automatic_publication_eligible: bool
    resulting_status: RuleStatus
    missing_requirements: tuple[str, ...]
    conflicts: tuple[str, ...]
    pending_review: tuple[str, ...]
    supporting_claim_ids: tuple[str, ...]
    source_span_ids: tuple[str, ...]
    source_revision_ids: tuple[str, ...]
    source_supports: tuple[RuleLeafSupport, ...]
    scope: VisibilityScope
    limitations: tuple[str, ...] = ("pure_validation_requires_transactional_source_recheck",)


def _scope_contains(derived: VisibilityScope, source: VisibilityScope) -> bool:
    return source.visibility == "public" or (
        derived.visibility == "tenant" and source.tenant_id == derived.tenant_id
    )


def validate_rule(
    rule: ConditionRule,
    *,
    access_scope: AccessScope,
    policy: RuleValidationPolicy,
    supports: tuple[RuleLeafSupport, ...],
) -> RuleValidationResult:
    """Check every necessary condition; no state writes or invented human approval."""
    access_scope.requires(READ_PUBLIC)
    access_scope.enforce_visible(rule.scope.visibility, rule.scope.tenant_id)
    rule = ConditionRule.model_validate(rule.model_dump(mode="python"))
    policy = RuleValidationPolicy.model_validate(policy.model_dump(mode="python"))
    supports = tuple(
        RuleLeafSupport.model_validate(item.model_dump(mode="python")) for item in supports
    )
    leaves = tuple(
        node
        for node in iter_condition_nodes(rule.condition_ast)
        if not isinstance(node, AllOf | AnyOf)
    )
    leaf_map = {node.node_id: node for node in leaves}
    missing: list[str] = []
    conflicts: list[str] = []
    pending: list[str] = []
    valid_claims: set[str] = set()
    valid_spans: set[str] = set()
    valid_nodes: set[str] = set()
    if len(supports) > 64:
        raise ValueError("rule support budget exceeded")
    for support in supports:
        access_scope.enforce_visible(support.scope.visibility, support.scope.tenant_id)
        for span in support.evidence:
            access_scope.enforce_visible(span.scope.visibility, span.scope.tenant_id)
        node = leaf_map.get(support.node_id)
        if node is None or support.condition_sha256 != condition_digest(node):
            missing.append(f"detached_support:{support.node_id}")
            continue
        if not _scope_contains(rule.scope, support.scope) or any(
            not _scope_contains(rule.scope, span.scope) for span in support.evidence
        ):
            conflicts.append(f"scope_widening:{node.node_id}")
            continue
        if support.condition_scope != rule.rule_kind:
            conflicts.append(f"condition_scope_mismatch:{node.node_id}")
            continue
        if support.claim_status == ClaimStatus.DISPUTED:
            conflicts.append(f"disputed_claim:{support.claim_id}")
        if support.claim_origin == ClaimOrigin.MODEL_HYPOTHESIS:
            pending.append(f"model_hypothesis:{support.claim_id}")
            continue
        if support.claim_status != ClaimStatus.SUPPORTED:
            pending.append(f"unsupported_claim_status:{support.claim_id}")
            continue
        evidence = tuple(
            span
            for span in support.evidence
            if span.source_id == support.source_id
            and span.document_id == support.document_id
            and span.revision_id == support.source_revision_id
            and span.validation_status == "validated"
            and span.support_kind == "supports"
        )
        if len(evidence) != len(support.evidence):
            pending.append(f"unverified_or_detached_evidence:{support.claim_id}")
        if any(
            span.support_kind == "refutes" and span.validation_status == "validated"
            for span in support.evidence
        ):
            conflicts.append(f"refuted_condition:{node.node_id}")
        if not evidence or not support.necessary_condition_supported:
            missing.append(f"necessary_condition_evidence:{node.node_id}")
            continue
        if (
            isinstance(node, VersionInRange)
            and node.range_complete
            and not support.range_completeness_confirmed
        ):
            missing.append(f"range_completeness_evidence:{node.node_id}")
            continue
        valid_claims.add(support.claim_id)
        valid_nodes.add(support.node_id)
        valid_spans.update(span.evidence_id for span in evidence)
    for node in leaves:
        if node.kind not in policy.approved_predicates:
            pending.append(f"predicate_not_approved:{node.kind}")
        if node.kind == "network_reachable" and rule.rule_kind == "software_applicability":
            conflicts.append(f"network_cannot_decide_software:{node.node_id}")
        if node.node_id not in valid_nodes:
            missing.append(f"unsupported_leaf:{node.node_id}")
    if valid_claims != set(rule.supporting_claim_ids):
        missing.append("supporting_claim_references_mismatch")
    if valid_spans != set(rule.source_span_ids):
        missing.append("source_span_references_mismatch")
    if rule.status == RuleStatus.RETIRED:
        pending.append("retired_rule_requires_new_version")
    eligible = not (missing or conflicts or pending)
    resulting_status = rule.status
    if rule.status not in {RuleStatus.PUBLISHED, RuleStatus.RETIRED}:
        resulting_status = RuleStatus.VALIDATED if eligible else RuleStatus.CANDIDATE
    return RuleValidationResult(
        rule_id=rule.rule_id,
        rule_version=rule.version,
        schema_version=rule.schema_version,
        policy_version=policy.policy_version,
        condition_sha256=condition_digest(rule.condition_ast),
        eligible=eligible,
        automatic_publication_eligible=eligible and policy.automatic_publication_enabled,
        resulting_status=resulting_status,
        missing_requirements=tuple(dict.fromkeys(missing)),
        conflicts=tuple(dict.fromkeys(conflicts)),
        pending_review=tuple(dict.fromkeys(pending)),
        supporting_claim_ids=tuple(sorted(valid_claims)),
        source_span_ids=tuple(sorted(valid_spans)),
        source_revision_ids=tuple(sorted({item.source_revision_id for item in supports})),
        source_supports=supports,
        scope=rule.scope,
    )


class RuleEvaluation(ConditionContract):
    rule_id: Label
    rule_version: int
    rule_kind: RuleKind
    asset_snapshot_id: Label
    condition_sha256: str
    evaluation_tree: ConditionEvaluation
    status: AssessmentStatus
    limitations: tuple[str, ...]


def evaluate_rule(
    rule: ConditionRule,
    asset_snapshot: AssetSnapshotResponse,
    *,
    access_scope: AccessScope,
    supporting_facts: tuple[ConditionFact, ...] = (),
) -> RuleEvaluation:
    """Caller selects published rules and checks PG validity before/after pure evaluation."""
    rule = ConditionRule.model_validate(rule.model_dump(mode="python"))
    access_scope.enforce_visible(rule.scope.visibility, rule.scope.tenant_id)
    if rule.status != RuleStatus.PUBLISHED:
        raise ValueError("evaluation requires a published rule")
    result = evaluate_condition_tree(
        rule.condition_ast,
        asset_snapshot,
        access_scope=access_scope,
        supporting_facts=supporting_facts,
        rule_kind=rule.rule_kind,
    )
    statuses = {
        ConditionValue.TRUE: AssessmentStatus.SUPPORTED_APPLICABILITY,
        ConditionValue.FALSE: AssessmentStatus.EXCLUDED_WITH_EVIDENCE,
        ConditionValue.UNKNOWN: AssessmentStatus.INSUFFICIENT_EVIDENCE,
        ConditionValue.CONFLICT: AssessmentStatus.CONFLICTING_EVIDENCE,
    }
    limits = {
        "software_applicability": (
            "software_applicability_does_not_confirm_exploitation_or_absolute_safety"
        ),
        "observed_path": "observed_path_does_not_change_software_fix_status",
        "research_prerequisites": "research_prerequisites_do_not_confirm_execution_success",
    }
    return RuleEvaluation(
        rule_id=rule.rule_id,
        rule_version=rule.version,
        rule_kind=rule.rule_kind,
        asset_snapshot_id=asset_snapshot.snapshot_id,
        condition_sha256=condition_digest(rule.condition_ast),
        evaluation_tree=result,
        status=statuses[result.value],
        limitations=(limits[rule.rule_kind], *result.limitations),
    )
