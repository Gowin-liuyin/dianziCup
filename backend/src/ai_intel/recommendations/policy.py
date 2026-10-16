"""Deterministic recommendations; storage, authentication and PG checks belong to callers."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import TypeAdapter

from ai_intel.api.knowledge_contracts import CitationProjection
from ai_intel.assessment.conditions import EvidenceReference
from ai_intel.assessment.persistence_contracts import AssessmentReceipt
from ai_intel.domain.enums import AssessmentStatus, ClaimOrigin, ClaimStatus, FreshnessStatus
from ai_intel.domain.values import UtcTimestamp
from ai_intel.recommendations.contracts import (
    MAX_CANDIDATES,
    MAX_INPUT_EVENTS,
    AssessmentReference,
    CandidateKind,
    RecommendationBatch,
    RecommendationCandidate,
    RecommendationEventInput,
    RecommendationKey,
    RecommendationReason,
    RecommendationSubscription,
    SelectorEvidence,
)


def require_item_budget(value: int) -> None:
    if type(value) is not int or not 1 <= value <= MAX_CANDIDATES:
        raise ValueError("item_budget_out_of_bounds")


def _supported(selector: SelectorEvidence) -> bool:
    return (
        selector.claim_status == ClaimStatus.SUPPORTED
        and selector.claim_origin != ClaimOrigin.MODEL_HYPOTHESIS
        and selector.support_kind == "supports"
        and selector.validation_status == "validated"
    )


def _assessment_reference(receipt: AssessmentReceipt) -> AssessmentReference:
    snapshot = receipt.prepared.asset_snapshot
    rule = receipt.prepared.inputs.rule
    result = receipt.rule_result
    if (
        (receipt.tenant_id, receipt.asset_id, receipt.asset_snapshot_id)
        != (snapshot.tenant_id, snapshot.asset_id, snapshot.snapshot_id)
        or (receipt.event_id, receipt.rule_id, receipt.rule_version)
        != (rule.event_id, rule.rule_id, rule.version)
        or receipt.prepared.scope_watch.tenant_id != receipt.tenant_id
        or not receipt.prepared.asset_active
        or receipt.prepared.asset_current_snapshot_id != receipt.asset_snapshot_id
        or (result is None and receipt.status != AssessmentStatus.INSUFFICIENT_EVIDENCE)
        or (
            result is not None
            and (
                result.status != receipt.status
                or (result.rule_id, result.rule_version, result.asset_snapshot_id)
                != (receipt.rule_id, receipt.rule_version, receipt.asset_snapshot_id)
            )
        )
    ):
        raise ValueError("assessment_receipt_binding_mismatch")
    nodes_by_evidence: dict[str, set[str]] = {}
    pending_nodes = [result.evaluation_tree] if result is not None else []
    while pending_nodes:
        node = pending_nodes.pop()
        for evidence_id in node.evidence_ids:
            nodes_by_evidence.setdefault(evidence_id, set()).add(node.node_id)
        pending_nodes.extend(node.child_results)
    evidence_by_id: dict[str, EvidenceReference] = {}
    for support in receipt.prepared.inputs.supports:
        span = support.evidence
        if span.evidence_id not in nodes_by_evidence:
            continue
        if (
            support.binding.evidence_id != span.evidence_id
            or support.binding.node_id not in nodes_by_evidence[span.evidence_id]
            or span.validation_status != "validated"
            or support.semantic_status not in {"supports", "refutes"}
            or span.support_kind != support.semantic_status
        ):
            raise ValueError("assessment_evidence_binding_mismatch")
        previous = evidence_by_id.get(span.evidence_id)
        if previous is not None and previous != span:
            raise ValueError("assessment_evidence_identity_mismatch")
        evidence_by_id[span.evidence_id] = span
    if nodes_by_evidence.keys() != evidence_by_id.keys():
        raise ValueError("assessment_evidence_binding_mismatch")
    evidence = tuple(evidence_by_id[key] for key in sorted(evidence_by_id))
    if (
        receipt.status
        in {
            AssessmentStatus.SUPPORTED_APPLICABILITY,
            AssessmentStatus.EXCLUDED_WITH_EVIDENCE,
        }
        and not evidence
    ):
        raise ValueError("definitive_assessment_requires_evidence")
    if any(
        span.scope.visibility == "tenant" and span.scope.tenant_id != receipt.tenant_id
        for span in evidence
    ):
        raise ValueError("assessment_evidence_tenant_mismatch")
    return AssessmentReference(
        assessment_id=receipt.assessment_id,
        asset_id=receipt.asset_id,
        asset_snapshot_id=receipt.asset_snapshot_id,
        rule_id=receipt.rule_id,
        rule_version=receipt.rule_version,
        status=receipt.status,
        knowledge_epoch=receipt.knowledge_epoch,
        scope_epoch_map=dict(receipt.scope_epoch_map),
        input_digest=receipt.input_digest,
        evidence=evidence,
        missing_requirements=receipt.missing_requirements,
        conflicts=receipt.conflicts,
        limitations=receipt.limitations,
    )


def candidate_order(candidate: RecommendationCandidate) -> tuple[int, int, float, str, str]:
    """High-consequence unresolved conditions precede supported risks in the same bucket."""
    kind_order = {
        "prioritize_verification": 0,
        "supported_risk": 1,
        "intelligence_update": 2,
        "excluded_with_evidence": 3,
    }
    return (
        candidate.priority_bucket,
        kind_order[candidate.kind],
        -candidate.observed_at.timestamp(),
        candidate.key.event_id,
        candidate.key.material_version,
    )


def _candidate(
    subscription: RecommendationSubscription, event: RecommendationEventInput, cutoff: datetime
) -> RecommendationCandidate | None:
    if event.current_state_checked_at < cutoff:
        raise ValueError("current_state_check_precedes_cutoff")
    if event.current_state_checked_at == cutoff and (
        event.status_at_cutoff != event.current_status
        or event.freshness_at_cutoff != event.current_freshness
    ):
        raise ValueError("as_of_state_conflicts_with_current_state")
    if (
        event.observed_at > cutoff
        or event.valid_from > cutoff
        or (event.valid_until is not None and event.valid_until <= cutoff)
        or event.status_at_cutoff in {ClaimStatus.WITHDRAWN, ClaimStatus.SUPERSEDED}
        or event.freshness_at_cutoff != FreshnessStatus.CURRENT
    ):
        return None
    reasons: list[RecommendationReason] = []
    high_consequence = False
    for selector in event.selectors:
        if not _supported(selector):
            continue
        if selector.selector_kind == "consequence" and selector.selector_value == "high":
            high_consequence = True
        elif (
            selector.selector_kind == "product"
            and selector.selector_value in subscription.product_keys
        ) or (
            selector.selector_kind == "risk_topic"
            and selector.selector_value in subscription.risk_topics
        ):
            reasons.append(
                RecommendationReason(
                    code="product_match"
                    if selector.selector_kind == "product"
                    else "risk_topic_match",
                    matched_key=selector.selector_value,
                    claim_id=selector.claim_id,
                    citations=selector.citations,
                )
            )
    assessments: list[AssessmentReference] = []
    for receipt in event.assessments:
        if receipt.tenant_id != subscription.tenant_id or receipt.event_id != event.event_id:
            raise ValueError("assessment_scope_mismatch")
        if receipt.asset_id not in subscription.asset_ids:
            continue
        if receipt.freshness != FreshnessStatus.CURRENT or receipt.created_at > cutoff:
            continue
        reference = _assessment_reference(receipt)
        assessments.append(reference)
        reasons.append(
            RecommendationReason(
                code="asset_assessment",
                matched_key=receipt.asset_id,
                assessment_id=receipt.assessment_id,
            )
        )
    if not reasons:
        return None
    if high_consequence:
        for selector in event.selectors:
            if _supported(selector) and (selector.selector_kind, selector.selector_value) == (
                "consequence",
                "high",
            ):
                reasons.append(
                    RecommendationReason(
                        code="high_consequence",
                        matched_key="high",
                        claim_id=selector.claim_id,
                        citations=selector.citations,
                    )
                )
    states = {reference.status for reference in assessments}
    unresolved = (
        bool(
            states & {AssessmentStatus.INSUFFICIENT_EVIDENCE, AssessmentStatus.CONFLICTING_EVIDENCE}
        )
        or event.status_at_cutoff != ClaimStatus.SUPPORTED
    )
    kind: CandidateKind
    if unresolved:
        kind = "prioritize_verification"
        priority = 0 if high_consequence else 2
    elif AssessmentStatus.SUPPORTED_APPLICABILITY in states:
        kind = "supported_risk"
        priority = 0 if high_consequence else 1
    elif states and states == {AssessmentStatus.EXCLUDED_WITH_EVIDENCE}:
        kind = "excluded_with_evidence"
        priority = 3
    else:
        kind = "intelligence_update"
        priority = 0 if high_consequence else 3
    if priority > subscription.maximum_priority_bucket:
        return None
    return RecommendationCandidate(
        key=RecommendationKey(
            subscription_id=subscription.subscription_id,
            event_id=event.event_id,
            material_version=event.material_version,
        ),
        tenant_id=subscription.tenant_id,
        user_id=subscription.user_id,
        kind=kind,
        priority_bucket=priority,
        reasons=tuple(
            sorted(
                reasons,
                key=lambda item: (
                    item.code,
                    item.matched_key,
                    item.claim_id or item.assessment_id or "",
                ),
            )
        ),
        assessments=tuple(sorted(assessments, key=lambda item: item.assessment_id)),
        observed_at=event.observed_at,
        source_changed_at=event.source_changed_at,
        valid_from=event.valid_from,
        valid_until=event.valid_until,
        validity_as_of=cutoff,
        freshness_at_cutoff=event.freshness_at_cutoff,
        current_status=event.current_status,
        current_freshness=event.current_freshness,
        current_state_checked_at=event.current_state_checked_at,
        limitations=("project_priority_rule_not_exploit_confirmation",)
        + (("unresolved_evidence_requires_verification",) if unresolved else ()),
    )


def generate_recommendation_candidates(
    subscription: RecommendationSubscription,
    events: tuple[RecommendationEventInput, ...],
    *,
    cutoff_at: datetime,
    existing_keys: tuple[RecommendationKey, ...] = (),
    max_candidates: int = MAX_CANDIDATES,
) -> RecommendationBatch:
    """Caller must enforce PG authorization and as-of validity before calling and before commit.

    This function does not persist deduplication or check subscription revocation races.
    """
    require_item_budget(max_candidates)
    cutoff = TypeAdapter(UtcTimestamp).validate_python(cutoff_at)
    subscription = RecommendationSubscription.model_validate(subscription.model_dump(mode="python"))
    if len(events) > MAX_INPUT_EVENTS or len(existing_keys) > MAX_INPUT_EVENTS:
        raise ValueError("input_event_budget_exceeded")
    if not subscription.enabled:
        return RecommendationBatch(
            subscription=subscription,
            cutoff_at=cutoff,
            candidates=(),
            eligible_count=0,
            partial=False,
            continuation_keys=(),
            stop_reason="disabled",
        )
    seen = {(key.subscription_id, key.event_id, key.material_version) for key in existing_keys}
    versions: dict[tuple[str, str], RecommendationEventInput] = {}
    citations_by_id: dict[UUID, CitationProjection] = {}
    active_events: set[str] = set()
    candidates: list[RecommendationCandidate] = []
    for item in events:
        event = RecommendationEventInput.model_validate(item.model_dump(mode="python"))
        for selector in event.selectors:
            for citation in selector.citations:
                previous_citation = citations_by_id.get(citation.evidence_id)
                if previous_citation is not None and previous_citation != citation:
                    raise ValueError("selector_evidence_identity_mismatch")
                citations_by_id[citation.evidence_id] = citation
        version_key = (event.event_id, event.material_version)
        previous = versions.get(version_key)
        if previous is not None:
            if previous != event:
                raise ValueError("material_version_collision")
            continue
        versions[version_key] = event
        candidate = _candidate(subscription, event, cutoff)
        if candidate is not None:
            if event.event_id in active_events:
                raise ValueError("ambiguous_active_material_versions")
            active_events.add(event.event_id)
            if (
                candidate.key.subscription_id,
                candidate.key.event_id,
                candidate.key.material_version,
            ) not in seen:
                candidates.append(candidate)
    candidates.sort(key=candidate_order)
    selected = tuple(candidates[:max_candidates])
    continuation = tuple(candidate.key for candidate in candidates[max_candidates:])
    return RecommendationBatch(
        subscription=subscription,
        cutoff_at=cutoff,
        candidates=selected,
        eligible_count=len(candidates),
        partial=bool(continuation),
        continuation_keys=continuation,
        stop_reason="item_budget"
        if continuation
        else ("complete" if candidates else "no_supported_subscription_match"),
    )
