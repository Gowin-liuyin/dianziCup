"""Current, evidence-bound risk summaries in the caller's PostgreSQL transaction."""

from __future__ import annotations

import math
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import and_, func, or_, select
from sqlalchemy.engine import RowMapping

from ai_intel.api.knowledge_contracts import CitationProjection
from ai_intel.api.knowledge_read_service import KnowledgeReadService, sources
from ai_intel.api.public_component_selector import (
    ComponentAssessmentSelection,
    _identity_gap,
    select_current_component_assessments,
)
from ai_intel.api.public_extension_reads import classify_revision_mode
from ai_intel.api.public_write_adapters import (
    PublicStackCheckRequest,
    PublicStackCheckResult,
    PublicUuid,
    PublicWriteMappingError,
    parse_public_stack_request,
    stack_current_assessments,
)
from ai_intel.assessment.assessment_persistence import assessment_results
from ai_intel.assessment.assessment_service import AssessmentService
from ai_intel.assessment.conditions import (
    ComponentMatches,
    InventoryProvesAbsence,
    VersionInRange,
    condition_digest,
    iter_condition_nodes,
)
from ai_intel.assessment.persistence_contracts import AssessmentReceipt
from ai_intel.assessment.rule_persistence import (
    RulePersistenceError,
    _all_source_rows,
    condition_rule_versions,
    read_rule,
    stored_rule,
)
from ai_intel.assessment.rules import ConditionRule
from ai_intel.assets.inventory_models import asset_snapshots, assets
from ai_intel.domain.access import READ_ASSET, PermissionDeniedError
from ai_intel.domain.enrichment_values import CvssSignalValue
from ai_intel.domain.enums import AssessmentStatus, ClaimStatus, ConditionValue, FreshnessStatus
from ai_intel.enrichment.contracts import CandidateEvidence
from ai_intel.enrichment.inputs import (
    MAX_DOCUMENT_BYTES,
    EnrichmentInputError,
    _load_document,
    _require_input_scopes,
)
from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.infrastructure.minio_store import ObjectStoreUnavailableError
from ai_intel.knowledge.models import content_objects, document_revisions, documents, evidence
from ai_intel.knowledge.persistence import KnowledgeRepository
from ai_intel.knowledge.persistence_models import (
    claim_assertions,
    claim_evidence,
    claims,
    event_documents,
    event_external_ids,
    events,
)
from ai_intel.knowledge.structured_fact_proofs import _LinkedFactEvidence, _verify_source_report

Severity = Literal["none", "low", "medium", "high", "critical"]
MinimumSeverity = Literal["low", "medium", "high", "critical"]
SEVERITY_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
MAX_RULE_INPUTS = 2000
MAX_GRADING_CLAIMS = 8
SourceParentRef = tuple[str, str, str, str]


def normalized_cvss_severity(score: float) -> Severity:
    """Apply r18-risk-policy-1 without changing the source CVSS version or value."""
    if isinstance(score, bool) or not math.isfinite(score) or not 0 <= score <= 10:
        raise ValueError("invalid CVSS score")
    if score == 0:
        return "none"
    if score < 4:
        return "low"
    if score < 7:
        return "medium"
    if score < 9:
        return "high"
    return "critical"


class _PublicRiskRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)


class PublicRiskFinding(_PublicRiskRecord):
    component_index: int = Field(ge=0, le=199)
    event_id: PublicUuid
    assessment_id: PublicUuid
    rule_id: PublicUuid
    rule_version: int = Field(ge=1)
    grading_claim_id: PublicUuid
    severity: Severity
    cvss_score: float = Field(ge=0, le=10, allow_inf_nan=False)
    cvss_version: Literal["2.0", "3.0", "3.1", "4.0"]
    citations: tuple[CitationProjection, ...] = Field(min_length=1, max_length=100)
    freshness: Literal["current"]

    @model_validator(mode="after")
    def require_consistent_grade(self) -> PublicRiskFinding:
        if self.severity != normalized_cvss_severity(self.cvss_score):
            raise ValueError("CVSS score and normalized severity disagree")
        return self


class PublicRiskSummary(_PublicRiskRecord):
    policy_version: Literal["r18-risk-policy-1"]
    minimum_severity: MinimumSeverity
    confirmation: Literal["confirmed", "none_confirmed", "unknown", "conflict"]
    coverage: Literal["complete", "partial", "unknown"]
    freshness: FreshnessStatus
    evaluated_components: int = Field(ge=0, le=200)
    unknown_component_indices: tuple[Annotated[int, Field(ge=0, le=199)], ...] = Field(
        max_length=200
    )
    findings: tuple[PublicRiskFinding, ...] = Field(max_length=200)

    @model_validator(mode="after")
    def require_consistent_confirmation(self) -> PublicRiskSummary:
        if len(set(self.unknown_component_indices)) != len(self.unknown_component_indices):
            raise ValueError("unknown component indices must be unique")
        identities: set[tuple[int, UUID, UUID, UUID, int, UUID]] = set()
        assessments: dict[UUID, tuple[int, UUID, UUID, int]] = {}
        grades: dict[UUID, tuple[UUID, float, str]] = {}
        for finding in self.findings:
            identity = (
                finding.component_index,
                finding.event_id,
                finding.assessment_id,
                finding.rule_id,
                finding.rule_version,
                finding.grading_claim_id,
            )
            if identity in identities:
                raise ValueError("risk findings must be unique")
            identities.add(identity)
            binding = (
                finding.component_index,
                finding.event_id,
                finding.rule_id,
                finding.rule_version,
            )
            if assessments.setdefault(finding.assessment_id, binding) != binding:
                raise ValueError("one assessment has inconsistent component or event bindings")
            grade = (finding.event_id, finding.cvss_score, finding.cvss_version)
            if grades.setdefault(finding.grading_claim_id, grade) != grade:
                raise ValueError("one grading claim has inconsistent event or score bindings")
        confirmed = any(
            SEVERITY_RANK[item.severity] >= SEVERITY_RANK[self.minimum_severity]
            for item in self.findings
        )
        if (self.confirmation == "confirmed") != confirmed:
            raise ValueError("risk confirmation disagrees with threshold findings")
        if self.coverage == "complete" and (
            self.confirmation in {"unknown", "conflict"}
            or self.unknown_component_indices
            or self.freshness != FreshnessStatus.CURRENT
        ):
            raise ValueError("complete coverage requires current qualified components")
        if self.confirmation == "none_confirmed" and self.coverage != "complete":
            raise ValueError("no confirmed threshold finding requires a complete evaluated scope")
        return self


class PublicStackCheckEnvelope(_PublicRiskRecord):
    result: PublicStackCheckResult
    risk_summary: PublicRiskSummary

    @model_validator(mode="after")
    def require_assessment_scope(self) -> PublicStackCheckEnvelope:
        results, summary = self.result.results, self.risk_summary
        if summary.coverage == "complete" and not results:
            raise ValueError("empty result scope cannot establish complete coverage")
        if summary.evaluated_components > len(results):
            raise ValueError("evaluated component count exceeds the returned scope")
        if any(index >= len(results) for index in summary.unknown_component_indices):
            raise ValueError("unknown component index is outside the returned scope")
        for finding in summary.findings:
            if finding.component_index >= len(results):
                raise ValueError("finding component index is outside the returned scope")
            result = results[finding.component_index]
            if (
                result.assessment_id != finding.assessment_id
                or result.status != AssessmentStatus.SUPPORTED_APPLICABILITY
                or result.freshness != FreshnessStatus.CURRENT
                or not result.citations
            ):
                raise ValueError("finding requires the same current supported assessment")
        unknown = {
            index
            for index, result in enumerate(results)
            if result.status
            in {AssessmentStatus.INSUFFICIENT_EVIDENCE, AssessmentStatus.CONFLICTING_EVIDENCE}
            or result.freshness != FreshnessStatus.CURRENT
        }
        if not unknown.issubset(summary.unknown_component_indices):
            raise ValueError("risk summary omits unknown or conflicting component results")
        graded = {finding.component_index for finding in summary.findings}
        missing = any(
            result.assessment_id is None
            or not result.citations
            or (result.status == AssessmentStatus.SUPPORTED_APPLICABILITY and index not in graded)
            for index, result in enumerate(results)
        )
        if summary.coverage == "complete" and (unknown or missing):
            raise ValueError("complete scope requires graded support or evidenced exclusion")
        return self


def _rule_package_scope(rule: ConditionRule) -> set[tuple[str, str]]:
    packages: set[tuple[str, str]] = set()
    for node in iter_condition_nodes(rule.condition_ast):
        if isinstance(node, ComponentMatches | InventoryProvesAbsence):
            packages.add((node.ecosystem, node.package_key))
        elif isinstance(node, VersionInRange):
            packages.add((node.assertion.ecosystem, node.assertion.package_key))
    return packages


def _current_rule_scope(
    knowledge: KnowledgeReadService,
) -> tuple[tuple[ConditionRule, ...], str | None]:
    """Read an optimistic roster without reversing the canonical source-to-rule lock order.

    Qualified assessments acquire publication locks in their shared service. The producer
    rereads this entire roster under those locks before declaring current complete coverage.
    """
    rows = list(
        knowledge.session.execute(
            select(condition_rule_versions)
            .where(
                knowledge._visible(condition_rule_versions),
                condition_rule_versions.c.status == "published",
            )
            .order_by(condition_rule_versions.c.rule_id, condition_rule_versions.c.version)
            .limit(MAX_RULE_INPUTS + 1)
        ).mappings()
    )
    if len(rows) > MAX_RULE_INPUTS:
        return (), "published_rule_query_limit_exceeded"
    rules: list[ConditionRule] = []
    for row in rows:
        rule = stored_rule(row)
        if (
            rule.rule_id != row["rule_id"]
            or rule.version != row["version"]
            or rule.event_id != row["event_id"]
            or rule.rule_kind != row["rule_kind"]
            or rule.scope.visibility != row["visibility"]
            or rule.scope.tenant_id != row["tenant_id"]
            or condition_digest(rule.condition_ast) != row["condition_sha256"]
        ):
            raise PublicWriteMappingError("published_rule_identity_mismatch")
        rules.append(rule)
    return tuple(rules), None


def _assessment_cohort(
    payload: PublicStackCheckRequest, knowledge: KnowledgeReadService
) -> tuple[RowMapping, ...]:
    identities = []
    for component in payload.components:
        if (
            _identity_gap(
                component.ecosystem, component.package_name, component.version, component.purl
            )
            is not None
        ):
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
        identities.append(asset_snapshots.c.canonical_payload["components"].contains([identity]))
    if not identities:
        return ()
    return tuple(
        knowledge.session.execute(
            select(assessment_results)
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
                or_(*identities),
            )
            .order_by(assessment_results.c.assessment_id)
            .limit(MAX_RULE_INPUTS + 1)
        ).mappings()
    )


def _cohort_parent_refs(
    rows: tuple[RowMapping, ...], knowledge: KnowledgeReadService
) -> tuple[SourceParentRef, ...]:
    references: set[SourceParentRef] = set()
    rule_keys = {(row["rule_id"], row["rule_version"]) for row in rows}
    for rule_id, version in sorted(rule_keys):
        rule = stored_rule(read_rule(knowledge.session, knowledge.scope, rule_id, version))
        for parent in _all_source_rows(knowledge.session, rule):
            for prefix in ("", "document_", "source_"):
                knowledge.scope.enforce_visible(
                    parent[prefix + "visibility"], parent[prefix + "tenant_id"]
                )
            references.add(
                (
                    parent["source_id"],
                    parent["document_id"],
                    parent["revision_id"],
                    parent["content_hash"],
                )
            )
            if len(references) > MAX_RULE_INPUTS:
                return tuple(sorted(references))
    event_ids = {row["event_id"] for row in rows}
    if event_ids:
        grade_parents = tuple(
            knowledge.session.execute(
                select(
                    document_revisions.c.revision_id,
                    document_revisions.c.document_id,
                    document_revisions.c.content_hash,
                    document_revisions.c.visibility,
                    document_revisions.c.tenant_id,
                    documents.c.source_id,
                    documents.c.visibility.label("document_visibility"),
                    documents.c.tenant_id.label("document_tenant_id"),
                    sources.c.visibility.label("source_visibility"),
                    sources.c.tenant_id.label("source_tenant_id"),
                )
                .select_from(
                    claims.join(
                        document_revisions,
                        document_revisions.c.revision_id == claims.c.source_revision_id,
                    )
                    .join(documents, documents.c.document_id == document_revisions.c.document_id)
                    .join(sources, sources.c.source_id == documents.c.source_id)
                )
                .where(
                    claims.c.subject.in_((*event_ids, *("event:" + value for value in event_ids))),
                    claims.c.predicate.in_(("cvss_signal", "cvss_score")),
                    claims.c.is_current.is_(True),
                    knowledge._visible(claims),
                )
                .distinct()
                .order_by(document_revisions.c.revision_id)
                .limit(MAX_RULE_INPUTS + 1)
            ).mappings()
        )
        for parent in grade_parents:
            for prefix in ("", "document_", "source_"):
                knowledge.scope.enforce_visible(
                    parent[prefix + "visibility"], parent[prefix + "tenant_id"]
                )
            references.add(
                (
                    parent["source_id"],
                    parent["document_id"],
                    parent["revision_id"],
                    parent["content_hash"],
                )
            )
            if len(references) > MAX_RULE_INPUTS:
                return tuple(sorted(references))
    return tuple(sorted(references))


def _lock_assessment_cohort(
    payload: PublicStackCheckRequest, knowledge: KnowledgeReadService
) -> str | None:
    """Fence bounded candidate parents before any receipt can hold publication locks.

    This follows the existing completion/recommendation cohort lock order. A fresh full
    candidate and source read must agree; no new source lock is acquired while publication
    is held. Current CVSS primary parents are included even when their association is stale.
    """
    rows = _assessment_cohort(payload, knowledge)
    if len(rows) > MAX_RULE_INPUTS:
        return "risk_assessment_cohort_limit_exceeded"
    for row in rows:
        receipt = AssessmentReceipt.model_validate(row["result_payload"])
        if any(
            getattr(receipt, field) != row[field]
            for field in (
                "assessment_id",
                "tenant_id",
                "asset_id",
                "asset_snapshot_id",
                "event_id",
                "rule_id",
                "rule_version",
            )
        ):
            raise PublicWriteMappingError("risk_assessment_cohort_binding_mismatch")
    session = knowledge.session
    session.execute(
        select(assets.c.asset_id)
        .where(
            assets.c.asset_id.in_(sorted({row["asset_id"] for row in rows})),
            assets.c.tenant_id == knowledge.scope.tenant_id,
        )
        .order_by(assets.c.asset_id)
        .with_for_update(read=True)
    ).all()
    try:
        parents = _cohort_parent_refs(rows, knowledge)
    except RulePersistenceError as error:
        if str(error) != "source_roster_budget_exceeded":
            raise
        return "risk_source_cohort_limit_exceeded"
    if len(parents) > MAX_RULE_INPUTS:
        return "risk_source_cohort_limit_exceeded"
    source_ids = sorted({source for source, _document, _revision, _hash in parents})
    revision_ids = sorted({revision for _source, _document, revision, _hash in parents})
    for source_id in source_ids:
        session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended("source:" + source_id, 0)))
        )
    session.execute(
        select(sources.c.source_id)
        .where(sources.c.source_id.in_(source_ids))
        .order_by(sources.c.source_id)
        .with_for_update(read=True)
    ).all()
    session.execute(
        select(document_revisions.c.revision_id)
        .join(documents, documents.c.document_id == document_revisions.c.document_id)
        .where(document_revisions.c.revision_id.in_(revision_ids))
        .order_by(documents.c.document_id, document_revisions.c.revision_id)
        .with_for_update(read=True, of=(documents, document_revisions))
    ).all()
    session.execute(
        select(content_objects.c.content_hash)
        .where(content_objects.c.content_hash.in_(sorted({item[3] for item in parents})))
        .order_by(content_objects.c.content_hash)
        .with_for_update(read=True)
    ).all()
    for key in sorted({"public", "tenant:" + str(knowledge.scope.tenant_id)}):
        session.execute(
            select(
                func.pg_advisory_xact_lock(func.hashtextextended("knowledge-publication:" + key, 0))
            )
        )
    current_rows = _assessment_cohort(payload, knowledge)
    if len(current_rows) > MAX_RULE_INPUTS or current_rows != rows:
        return "risk_assessment_cohort_changed"
    try:
        current_parents = _cohort_parent_refs(current_rows, knowledge)
    except RulePersistenceError as error:
        if str(error) != "source_roster_budget_exceeded":
            raise
        return "risk_source_cohort_changed"
    if len(current_parents) > MAX_RULE_INPUTS or current_parents != parents:
        return "risk_source_cohort_changed"
    return None


def _grade_citations(
    knowledge: KnowledgeReadService,
    linked: tuple[_LinkedFactEvidence, ...],
    verified: tuple[UUID, ...],
) -> tuple[CitationProjection, ...]:
    citations: list[CitationProjection] = []
    by_id = {item.evidence_id: item.evidence for item in linked}
    for identifier in verified:
        projection = knowledge.read_evidence(identifier)
        declared = by_id[identifier]
        locator = knowledge.session.scalar(
            select(evidence.c.locator).where(evidence.c.evidence_id == str(identifier))
        )
        if (
            projection.span_id != identifier
            or projection.revision_id != declared.revision_id
            or projection.quote_text != declared.quote_text
            or projection.quote_sha256 != declared.quote_sha256
            or projection.verified_at is None
            or projection.source_uri is None
            or not isinstance(locator, str)
            or not locator
        ):
            raise PublicWriteMappingError("grading_evidence_projection_mismatch")
        citations.append(
            CitationProjection(
                evidence_id=identifier,
                revision_id=projection.revision_id,
                quote=projection.quote_text,
                locator=locator,
                source_uri=projection.source_uri,
            )
        )
    return tuple(citations)


def _validated_grade(
    row: RowMapping,
    receipt: AssessmentReceipt,
    service: AssessmentService,
    knowledge: KnowledgeReadService,
) -> tuple[CvssSignalValue | None, tuple[CitationProjection, ...], str | None]:
    session = knowledge.session
    record = KnowledgeRepository(session, knowledge.scope).get_claim(row["claim_id"])
    if (
        record.claim_id.value != row["claim_id"]
        or record.subject not in {receipt.event_id, "event:" + receipt.event_id}
        or record.scope != receipt.prepared.inputs.rule.scope
    ):
        raise PublicWriteMappingError("grading_claim_event_binding_mismatch")
    if (
        record.claim_status == ClaimStatus.DISPUTED
        or record.condition_value == ConditionValue.CONFLICT
    ):
        return None, (), "grading_conflict"
    if record.freshness == FreshnessStatus.STALE:
        return None, (), "grading_stale"
    if (
        record.schema_version != 3
        or not isinstance(record.object_value, CvssSignalValue)
        or record.claim_status != ClaimStatus.SUPPORTED
        or record.condition_value == ConditionValue.FALSE
        or record.freshness != FreshnessStatus.CURRENT
        or row["provenance_status"] != "source_verified"
    ):
        return None, (), "grading_fact_not_current_supported"
    revision_id = row["source_revision_id"]
    parent = (
        session.execute(
            select(
                document_revisions,
                documents.c.source_id,
                documents.c.kind,
                content_objects.c.size_bytes,
            )
            .select_from(
                document_revisions.join(documents)
                .join(
                    content_objects,
                    content_objects.c.content_hash == document_revisions.c.content_hash,
                )
                .join(sources, sources.c.source_id == documents.c.source_id)
            )
            .where(document_revisions.c.revision_id == revision_id)
            .with_for_update(
                read=True, of=(document_revisions, documents, content_objects, sources)
            )
        )
        .mappings()
        .first()
    )
    if parent is None or not parent["is_current"]:
        return None, (), "grading_source_stale"
    _require_input_scopes(session, knowledge.scope, record.scope, (revision_id,))
    if parent["size_bytes"] > MAX_DOCUMENT_BYTES:
        return None, (), "grading_source_byte_limit_exceeded"
    classify_revision_mode(parent["source_metadata"], knowledge.data_mode)
    association = session.scalar(
        select(event_documents.c.active)
        .where(
            event_documents.c.event_id == receipt.event_id,
            event_documents.c.revision_id == revision_id,
        )
        .with_for_update(read=True)
    )
    if association is not True:
        return None, (), "grading_event_document_withdrawn"
    assertions = list(
        session.execute(
            select(claim_assertions)
            .where(claim_assertions.c.claim_id == row["claim_id"])
            .limit(MAX_GRADING_CLAIMS + 1)
            .with_for_update(read=True)
        ).mappings()
    )
    primary = [item for item in assertions if item["revision_id"] == revision_id]
    if (
        len(assertions) > MAX_GRADING_CLAIMS
        or len(primary) != 1
        or primary[0]["source_id"] != parent["source_id"]
        or primary[0]["scoring_authority"] != record.object_value.authority
        or any(item["assertion_kind"] != record.claim_origin.value for item in assertions)
    ):
        return None, (), "grading_assertion_not_qualified"
    links = list(
        session.execute(
            select(evidence, claim_evidence.c.support_kind, claim_evidence.c.validation_status)
            .select_from(claim_evidence.join(evidence))
            .where(claim_evidence.c.claim_id == row["claim_id"], knowledge._visible(evidence))
            .order_by(evidence.c.evidence_id)
            .limit(MAX_GRADING_CLAIMS + 1)
            .with_for_update(read=True, of=(claim_evidence, evidence))
        ).mappings()
    )
    if not links or len(links) > MAX_GRADING_CLAIMS:
        return None, (), "grading_evidence_limit_or_missing"
    try:
        document = _load_document(session, service.content_store, record.scope, parent)
    except (EnrichmentInputError, ObjectStoreUnavailableError, FileNotFoundError):
        return None, (), "grading_source_unavailable"
    blocks = {block.block_id: block for block in document.blocks}
    linked: list[_LinkedFactEvidence] = []
    for link in links:
        block = blocks.get(UUID(link["block_id"])) if link["block_id"] else None
        if (
            block is None
            or link["revision_id"] != revision_id
            or link["coordinate_version"] != "fulltext_unicode_v1"
            or link["verified_at"] is None
        ):
            return None, (), "grading_evidence_not_qualified"
        linked.append(
            _LinkedFactEvidence(
                evidence_id=UUID(link["evidence_id"]),
                evidence=CandidateEvidence(
                    revision_id=revision_id,
                    block_id=link["block_id"],
                    start_offset=link["start_offset"] - block.start_offset,
                    end_offset=link["end_offset"] - block.start_offset,
                    quote_text=link["quote"],
                    quote_sha256=link["quote_sha256"],
                ),
                support_kind=link["support_kind"],
                validation_status=link["validation_status"],
                supports_claim=link["supports_claim"],
            )
        )
    identifiers = tuple(
        (str(kind), str(value))
        for kind, value in session.execute(
            select(event_external_ids.c.id_type, event_external_ids.c.id_value)
            .where(event_external_ids.c.event_id == receipt.event_id)
            .limit(101)
            .with_for_update(read=True)
        )
    )
    if len(identifiers) > 100:
        return None, (), "grading_owner_identifier_limit_exceeded"
    verified, gaps = _verify_source_report(
        record, document, tuple(linked), identifiers, primary[0]["json_path"]
    )
    if gaps or not verified:
        return None, (), "grading_source_report_not_verified"
    return record.object_value, _grade_citations(knowledge, tuple(linked), verified), None


def _current_grade_findings(
    index: int,
    receipt: AssessmentReceipt,
    service: AssessmentService,
    knowledge: KnowledgeReadService,
) -> tuple[tuple[PublicRiskFinding, ...], str | None]:
    session = knowledge.session
    event = (
        session.execute(
            select(events)
            .where(events.c.event_id == receipt.event_id, knowledge._visible(events))
            .with_for_update(read=True)
        )
        .mappings()
        .first()
    )
    if event is None or event["status"] != "active":
        return (), "grading_event_not_current"
    conflict = session.scalar(
        select(enrichment_results.c.event_id)
        .where(
            enrichment_results.c.event_id == receipt.event_id,
            enrichment_results.c.dimension == "cvss",
            enrichment_results.c.status == "conflict",
            enrichment_results.c.is_current.is_(True),
        )
        .limit(1)
        .with_for_update(read=True)
    )
    if conflict is not None:
        return (), "grading_conflict"
    rows = list(
        session.execute(
            select(claims)
            .where(
                claims.c.subject.in_((receipt.event_id, "event:" + receipt.event_id)),
                claims.c.predicate.in_(("cvss_signal", "cvss_score")),
                claims.c.is_current.is_(True),
                knowledge._visible(claims),
            )
            .order_by(claims.c.claim_id)
            .limit(MAX_GRADING_CLAIMS + 1)
            .with_for_update(read=True)
        ).mappings()
    )
    if not rows or len(rows) > MAX_GRADING_CLAIMS:
        return (), "grading_claim_limit_or_missing"
    findings: list[PublicRiskFinding] = []
    values: set[tuple[float, str, str]] = set()
    gaps: list[str] = []
    for row in rows:
        grade, citations, gap = _validated_grade(row, receipt, service, knowledge)
        if gap is not None or grade is None:
            gaps.append(gap or "grading_fact_not_qualified")
            continue
        values.add((grade.base_score, grade.standard_version, grade.vector))
        findings.append(
            PublicRiskFinding(
                component_index=index,
                event_id=UUID(receipt.event_id),
                assessment_id=UUID(receipt.assessment_id),
                rule_id=UUID(receipt.rule_id),
                rule_version=receipt.rule_version,
                grading_claim_id=UUID(row["claim_id"]),
                severity=normalized_cvss_severity(grade.base_score),
                cvss_score=grade.base_score,
                cvss_version=grade.standard_version,
                citations=citations,
                freshness="current",
            )
        )
    if len(values) > 1 or "grading_conflict" in gaps:
        return (), "grading_conflict"
    if gaps:
        if any("stale" in gap for gap in gaps):
            return (), "grading_stale"
        return (), gaps[0] if len(set(gaps)) == 1 else "grading_inputs_incomplete"
    return tuple(findings), None


def build_current_stack_envelope(
    payload: PublicStackCheckRequest,
    assessment_service: AssessmentService,
    knowledge_service: KnowledgeReadService,
    *,
    minimum_severity: MinimumSeverity = "high",
) -> PublicStackCheckEnvelope:
    """Read one explicit component scope, leaving all unsupported or incomplete coverage unknown.

    No writes, new sessions or model calls occur here. Root must retain its final current identity
    and scope-epoch fence before exposing or committing either empty or nonempty output.
    """
    if minimum_severity not in {"low", "medium", "high", "critical"}:
        raise ValueError("invalid minimum severity")
    knowledge_service.scope.requires(READ_ASSET)
    if knowledge_service.scope.tenant_id is None:
        raise PermissionDeniedError("tenant asset scope required")
    session = knowledge_service.session
    if not session.in_transaction() or session.connection().engine is not assessment_service.engine:
        raise ValueError("risk summary requires its caller-owned assessment transaction")
    payload = parse_public_stack_request(payload.model_dump_json(exclude_unset=True).encode())
    rules, rule_gap = _current_rule_scope(knowledge_service)
    cohort_gap = _lock_assessment_cohort(payload, knowledge_service)
    selection = (
        select_current_component_assessments(payload, assessment_service, knowledge_service)
        if cohort_gap is None
        else ComponentAssessmentSelection(
            (None,) * len(payload.components),
            (cohort_gap,) * len(payload.components),
            (cohort_gap,),
        )
    )
    result = stack_current_assessments(
        payload, selection.assessment_ids, assessment_service, knowledge_service
    )
    limitations = list(result.limitations)
    findings: list[PublicRiskFinding] = []
    unknown: list[int] = []
    conflicts = False
    stale = False
    evaluated = 0
    used_assessments: set[UUID] = set()
    qualified_rules: dict[int, tuple[str, int, str]] = {}
    for index, component in enumerate(payload.components):
        package = (component.ecosystem, component.package_name)
        relevant = [rule for rule in rules if package in _rule_package_scope(rule)]
        unattributed = any(not _rule_package_scope(rule) for rule in rules)
        gap = cohort_gap or rule_gap
        if gap is None and unattributed:
            gap = "published_rule_component_scope_unknown"
        if gap is None and not relevant:
            gap = "no_current_published_component_rule"
        if gap is None and len(relevant) > 1:
            gap = "multiple_rules_require_public_component_envelope_extension"
        identifier = selection.assessment_ids[index]
        projected = result.results[index]
        if identifier is not None:
            if gap is None and identifier in used_assessments:
                gap = "repeated_component_requires_distinct_public_assessment_binding"
            used_assessments.add(identifier)
        if gap is None and identifier is None:
            gap = selection.reason_codes[index]
        if projected.status == AssessmentStatus.CONFLICTING_EVIDENCE:
            conflicts = True
        stale |= projected.freshness == FreshnessStatus.STALE
        if gap is None and identifier is not None:
            receipt = assessment_service.read_in_session(
                knowledge_service.session, knowledge_service.scope, str(identifier)
            )
            rule = relevant[0]
            if (receipt.rule_id, receipt.rule_version, receipt.event_id) != (
                rule.rule_id,
                rule.version,
                rule.event_id,
            ) or receipt.prepared.inputs.rule != rule:
                raise PublicWriteMappingError("assessment_current_rule_binding_mismatch")
            qualified_rules[index] = (receipt.rule_id, receipt.rule_version, receipt.event_id)
            if receipt.conflicts or receipt.prepared.inputs.validation.conflicts:
                gap = "assessment_conflict"
                conflicts = True
            elif projected.status == AssessmentStatus.SUPPORTED_APPLICABILITY:
                graded, gap = _current_grade_findings(
                    index, receipt, assessment_service, knowledge_service
                )
                if len(findings) + len(graded) > 200:
                    gap = "risk_finding_limit_exceeded"
                elif gap is None:
                    findings.extend(graded)
            elif projected.status != AssessmentStatus.EXCLUDED_WITH_EVIDENCE:
                gap = "assessment_not_definitive"
        if gap is None:
            evaluated += 1
        else:
            unknown.append(index)
            limitations.append(gap)
            conflicts |= "conflict" in gap
            stale |= "stale" in gap
    if not payload.components:
        limitations.append("empty_component_scope")
    final_rules, final_rule_gap = _current_rule_scope(knowledge_service)
    roster_changed = final_rule_gap is not None or final_rules != rules
    if roster_changed:
        limitations.append(final_rule_gap or "current_rule_scope_changed")
        if final_rule_gap is None:
            initial_rules = {(rule.rule_id, rule.version): rule for rule in rules}
            unchanged = {
                (rule.rule_id, rule.version, rule.event_id)
                for rule in final_rules
                if initial_rules.get((rule.rule_id, rule.version)) == rule
            }
            invalid_indices = {
                index for index, binding in qualified_rules.items() if binding not in unchanged
            }
            findings = [item for item in findings if item.component_index not in invalid_indices]
            if invalid_indices:
                result = result.model_copy(
                    update={
                        "results": tuple(
                            item.model_copy(
                                update={
                                    "status": AssessmentStatus.INSUFFICIENT_EVIDENCE,
                                    "reason_code": "current_rule_scope_changed",
                                    "freshness": FreshnessStatus.STALE,
                                    "citations": (),
                                }
                            )
                            if index in invalid_indices
                            else item
                            for index, item in enumerate(result.results)
                        )
                    }
                )
                stale = True
        unknown = list(range(len(payload.components)))
        evaluated = 0
    complete = bool(payload.components) and not unknown
    coverage: Literal["complete", "partial", "unknown"] = (
        "complete" if complete else "partial" if evaluated or findings else "unknown"
    )
    confirmation: Literal["confirmed", "none_confirmed", "unknown", "conflict"] = (
        "confirmed"
        if any(SEVERITY_RANK[item.severity] >= SEVERITY_RANK[minimum_severity] for item in findings)
        else "none_confirmed"
        if complete
        else "conflict"
        if conflicts
        else "unknown"
    )
    if complete:
        limitations = [
            item
            for item in limitations
            if item != "selected_assessments_do_not_prove_complete_rule_or_risk_coverage"
        ]
    limitations = list(dict.fromkeys(limitations))
    if len(limitations) > 100:
        raise PublicWriteMappingError("assessment_limitation_limit")
    return PublicStackCheckEnvelope(
        result=result.model_copy(update={"limitations": tuple(limitations)}),
        risk_summary=PublicRiskSummary(
            policy_version="r18-risk-policy-1",
            minimum_severity=minimum_severity,
            confirmation=confirmation,
            coverage=coverage,
            freshness=FreshnessStatus.STALE
            if stale
            else FreshnessStatus.CURRENT
            if complete
            else FreshnessStatus.UNKNOWN,
            evaluated_components=evaluated,
            unknown_component_indices=tuple(unknown),
            findings=tuple(findings),
        ),
    )
