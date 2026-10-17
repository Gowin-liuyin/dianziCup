"""Conservative component selection over current, authenticated PostgreSQL assessments."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from packageurl import PackageURL, ValidationSeverity
from sqlalchemy import and_, select

from ai_intel.api.knowledge_read_service import KnowledgeReadService
from ai_intel.api.public_write_adapters import (
    PublicComponent,
    PublicStackCheckRequest,
    PublicWriteMappingError,
    _component_in_snapshot,
    _rule_targets_only_component,
    parse_public_stack_request,
)
from ai_intel.assessment.assessment_persistence import assessment_results
from ai_intel.assessment.assessment_service import AssessmentService
from ai_intel.assessment.conditions import (
    AllOf,
    AnyOf,
    ComponentMatches,
    InventoryProvesAbsence,
    VersionInRange,
    iter_condition_nodes,
)
from ai_intel.assessment.persistence_contracts import AssessmentReceipt
from ai_intel.assessment.rule_persistence import condition_rule_versions
from ai_intel.assessment.version_ranges import compare_versions
from ai_intel.assets.inventory_models import asset_snapshots, assets
from ai_intel.domain.access import READ_ASSET, PermissionDeniedError
from ai_intel.domain.enums import FreshnessStatus

MAX_COMPONENT_SELECTION_CANDIDATES = 200
SELECTION_LIMITATIONS = (
    "selected_assessments_do_not_prove_complete_rule_or_risk_coverage",
    "component_selection_requires_exact_snapshot_identity_spelling",
)


@dataclass(frozen=True, slots=True)
class ComponentAssessmentSelection:
    """Internal per-index selection reasons; this is not a complete risk assessment."""

    assessment_ids: tuple[UUID | None, ...]
    reason_codes: tuple[str, ...]
    limitations: tuple[str, ...]


def _identity_gap(
    ecosystem: str,
    package_name: str,
    version: str | None,
    purl: str | None,
    *,
    scheme: str = "osv_ecosystem",
) -> str | None:
    comparison = compare_versions(version, version, scheme=scheme, ecosystem=ecosystem)
    if comparison.status != "comparable":
        return comparison.reason
    if purl is None:
        return None
    try:
        parsed = PackageURL.from_string(purl)
        if any(
            message.severity == ValidationSeverity.ERROR for message in parsed.validate(strict=True)
        ):
            return "invalid_purl"
    except (TypeError, ValueError):
        return "invalid_purl"
    if parsed.qualifiers or parsed.subpath:
        return "unsupported_purl_features"
    purl_ecosystem = {"pypi": "PyPI", "npm": "npm"}.get(parsed.type, parsed.type)
    purl_package = parsed.name if not parsed.namespace else parsed.namespace + "/" + parsed.name
    if purl_ecosystem != ecosystem or purl_package != package_name:
        return "component_purl_identity_mismatch"
    if parsed.version is not None and (
        compare_versions(version, parsed.version, scheme=scheme, ecosystem=ecosystem).ordering != 0
    ):
        return "component_purl_version_mismatch"
    return None


def _receipt_gap(component: PublicComponent, receipt: AssessmentReceipt) -> str | None:
    if receipt.freshness != FreshnessStatus.CURRENT:
        if receipt.freshness == FreshnessStatus.STALE:
            return "assessment_stale"
        return "unknown_freshness"
    if not _component_in_snapshot(component, receipt):
        raise PublicWriteMappingError("component_assessment_binding_mismatch")
    if not _rule_targets_only_component(component, receipt):
        return "unsupported_rule"
    if any(
        not isinstance(
            node, AllOf | AnyOf | ComponentMatches | InventoryProvesAbsence | VersionInRange
        )
        for node in iter_condition_nodes(receipt.prepared.inputs.rule.condition_ast)
    ):
        return "unsupported_component_rule"
    for item in receipt.prepared.asset_snapshot.components:
        if item.ecosystem == component.ecosystem and item.package_name == component.package_name:
            gap = _identity_gap(
                item.ecosystem,
                item.package_name,
                item.version,
                item.purl,
                scheme=item.version_scheme,
            )
            if gap is not None:
                return gap
    return None


def select_current_component_assessments(
    payload: PublicStackCheckRequest,
    service: AssessmentService,
    knowledge: KnowledgeReadService,
) -> ComponentAssessmentSelection:
    """Select at most one unambiguous current assessment for each exact request component.

    The caller must construct knowledge from its transaction's currently locked authentication
    context, then retain its final identity fence for empty and nonempty selections. Candidate
    reads use that same transaction and the assessment service's authentication/source recheck.
    Purl semantics validate existing identities; they do not rewrite frozen public wire fields.
    Unknown versions, broad asset rules and multiple current candidates remain insufficient.
    """
    knowledge.scope.requires(READ_ASSET)
    if knowledge.scope.tenant_id is None:
        raise PermissionDeniedError("tenant asset scope required")
    session = knowledge.session
    if not session.in_transaction() or session.connection().engine is not service.engine:
        raise ValueError("component selection requires its caller-owned assessment transaction")
    validated = parse_public_stack_request(payload.model_dump_json(exclude_unset=True).encode())
    selected: list[UUID | None] = []
    reasons: list[str] = []
    for component in validated.components:
        gap = _identity_gap(
            component.ecosystem, component.package_name, component.version, component.purl
        )
        if gap is not None:
            selected.append(None)
            reasons.append(gap)
            continue
        identity: dict[str, str | None] = {
            "ecosystem": component.ecosystem,
            "package_name": component.package_name,
            "version": component.version,
        }
        if component.component_id is not None:
            identity["component_id"] = str(component.component_id)
        if component.purl is not None:
            identity["purl"] = component.purl
        query = (
            select(assessment_results.c.assessment_id)
            .select_from(
                assessment_results.join(
                    asset_snapshots,
                    and_(
                        assessment_results.c.asset_snapshot_id == asset_snapshots.c.snapshot_id,
                        assessment_results.c.asset_id == asset_snapshots.c.asset_id,
                        assessment_results.c.tenant_id == asset_snapshots.c.tenant_id,
                    ),
                )
                .join(
                    assets,
                    and_(
                        assets.c.asset_id == asset_snapshots.c.asset_id,
                        assets.c.tenant_id == asset_snapshots.c.tenant_id,
                        assets.c.current_snapshot_id == asset_snapshots.c.snapshot_id,
                    ),
                )
                .join(
                    condition_rule_versions,
                    and_(
                        assessment_results.c.rule_id == condition_rule_versions.c.rule_id,
                        assessment_results.c.rule_version == condition_rule_versions.c.version,
                    ),
                )
            )
            .where(
                assessment_results.c.tenant_id == knowledge.scope.tenant_id,
                assets.c.active.is_(True),
                condition_rule_versions.c.status == "published",
                asset_snapshots.c.canonical_payload["components"].contains([identity]),
            )
            .order_by(assessment_results.c.assessment_id)
            .limit(MAX_COMPONENT_SELECTION_CANDIDATES + 1)
        )
        candidates: Sequence[str] = session.scalars(query).all()
        if len(candidates) > MAX_COMPONENT_SELECTION_CANDIDATES:
            selected.append(None)
            reasons.append("component_candidate_limit_exceeded")
            continue
        current_ids: list[UUID] = []
        gaps: set[str] = set()
        for identifier in candidates:
            receipt = service.read_in_session(session, knowledge.scope, identifier)
            if (
                receipt.assessment_id != identifier
                or receipt.tenant_id != knowledge.scope.tenant_id
            ):
                raise PublicWriteMappingError("component_assessment_binding_mismatch")
            receipt_gap = _receipt_gap(component, receipt)
            if receipt_gap is not None:
                gaps.add(receipt_gap)
                continue
            current_ids.append(UUID(identifier))
            if len(current_ids) > 1:
                break
        if len(current_ids) == 1 and not gaps:
            selected.append(current_ids[0])
            reasons.append("selected_current_assessment")
        else:
            selected.append(None)
            if len(current_ids) > 1:
                reasons.append("ambiguous_current_assessments")
            elif len(gaps) == 1:
                reasons.append(next(iter(gaps)))
            elif gaps:
                reasons.append("incomplete_current_assessments")
            else:
                reasons.append("no_match")
    limitations = tuple(
        dict.fromkeys(
            (
                *SELECTION_LIMITATIONS,
                *(reason for reason in reasons if reason != "selected_current_assessment"),
            )
        )
    )
    return ComponentAssessmentSelection(tuple(selected), tuple(reasons), limitations)
