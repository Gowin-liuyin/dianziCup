"""Frozen v2 write DTOs and projections over the existing question and PG assessment services."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator
from sqlalchemy import select

from ai_intel.answering.service import GroundedQuestionService
from ai_intel.api.knowledge_contracts import CitationProjection
from ai_intel.api.knowledge_read_service import KnowledgeReadService
from ai_intel.api.question_contracts import QuestionAnswerResponse, QuestionRequest
from ai_intel.assessment.assessment_service import AssessmentService
from ai_intel.assessment.conditions import (
    ComponentMatches,
    InventoryProvesAbsence,
    VersionInRange,
    condition_digest,
    iter_condition_nodes,
)
from ai_intel.assessment.persistence_contracts import AssessmentReceipt
from ai_intel.domain.access import READ_ASSET, AccessScope
from ai_intel.domain.enums import AssessmentStatus, FreshnessStatus
from ai_intel.infrastructure.models.json_output import strict_json_object
from ai_intel.knowledge.models import evidence

MAX_PUBLIC_WRITE_BYTES = 1048576


class PublicWriteMappingError(ValueError):
    """A current service result cannot be faithfully projected into the frozen public contract."""


def _public_uuid(value: object) -> object:
    if (
        isinstance(value, str)
        and re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value) is None
    ):
        raise ValueError("UUID requires its public hyphenated spelling")
    return value


PublicUuid = Annotated[UUID, BeforeValidator(_public_uuid)]


class PublicComponent(BaseModel):
    """Exact Component wire fields from public_api_v2, without asset or tenant authority."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)
    component_id: PublicUuid | None = None
    ecosystem: str = Field(min_length=1)
    package_name: str = Field(min_length=1)
    version: str | None
    purl: str | None = None

    @model_validator(mode="after")
    def reject_null_component_identity(self) -> PublicComponent:
        if "component_id" in self.model_fields_set and self.component_id is None:
            raise ValueError("component identity cannot be explicitly null")
        return self


class PublicStackCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)
    components: tuple[PublicComponent, ...] = Field(max_length=200)


class PublicComponentAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)
    component: PublicComponent
    status: AssessmentStatus
    reason_code: str = Field(min_length=1)
    assessment_id: UUID | None
    citations: tuple[CitationProjection, ...] = Field(max_length=100)
    freshness: FreshnessStatus

    @model_validator(mode="after")
    def preserve_missing_or_unsupported_reasons(self) -> PublicComponentAssessment:
        if (
            self.reason_code
            in {"no_match", "unsupported", "unsupported_rule", "unsupported_ecosystem"}
            and self.status != AssessmentStatus.INSUFFICIENT_EVIDENCE
        ):
            raise ValueError("missing or unsupported inputs require insufficient evidence")
        return self


class PublicStackCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)
    kind: Literal["completed"]
    results: tuple[PublicComponentAssessment, ...] = Field(max_length=200)
    limitations: tuple[str, ...] = Field(max_length=100)


def parse_public_ask_request(raw: bytes) -> QuestionRequest:
    """Reuse QuestionRequest with the frozen public UUID and optional-field boundary."""
    payload = strict_json_object(raw, MAX_PUBLIC_WRITE_BYTES, maximum_nodes=1000)
    for name in ("conversation_id", "known_at", "valid_at"):
        if name in payload and payload[name] is None:
            raise ValueError("optional public fields cannot be explicitly null")
    identifiers = [payload.get("conversation_id")]
    for name in ("asset_ids", "event_ids"):
        values = payload.get(name, [])
        if isinstance(values, list):
            identifiers.extend(values)
    for value in identifiers:
        if value is not None:
            _public_uuid(value)
    for name in ("known_at", "valid_at"):
        value = payload.get(name)
        if value is not None and (
            not isinstance(value, str)
            or re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt](?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]"
                r"(?:\.[0-9]+)?(?:[Zz]|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])",
                value,
            )
            is None
        ):
            raise ValueError("public timestamps require RFC3339 spelling")
    return QuestionRequest.model_validate_json(json.dumps(payload, ensure_ascii=False))


def parse_public_stack_request(raw: bytes) -> PublicStackCheckRequest:
    payload = strict_json_object(raw, MAX_PUBLIC_WRITE_BYTES, maximum_nodes=5000)
    return PublicStackCheckRequest.model_validate_json(json.dumps(payload, ensure_ascii=False))


def ask_current_question(
    service: GroundedQuestionService,
    payload: QuestionRequest,
    scope_provider: Callable[[], AccessScope],
    idempotency_key: str,
    *,
    session_token: str,
) -> QuestionAnswerResponse:
    """Delegate synchronous answering without generating content or bypassing its PG rechecks.

    The existing service accepts cookies. Root must complete its ActorReference and atomic
    key-budget seam before mounting this adapter for Bearer SDK calls.
    """
    if re.fullmatch(r"[\x21-\x7e]{1,200}", idempotency_key) is None:
        raise ValueError("public operation key is invalid")
    validated = parse_public_ask_request(payload.model_dump_json(exclude_unset=True).encode())
    answer = service.ask(validated, scope_provider, idempotency_key, session_token=session_token)
    return QuestionAnswerResponse.model_validate_json(answer.model_dump_json())


def _component_in_snapshot(component: PublicComponent, receipt: AssessmentReceipt) -> bool:
    return any(
        item.ecosystem == component.ecosystem
        and item.package_name == component.package_name
        and item.version == component.version
        and (component.component_id is None or item.component_id == str(component.component_id))
        and (component.purl is None or item.purl == component.purl)
        for item in receipt.prepared.asset_snapshot.components
    )


def _rule_targets_only_component(component: PublicComponent, receipt: AssessmentReceipt) -> bool:
    rule = receipt.prepared.inputs.rule
    if rule.rule_kind != "software_applicability":
        return False
    package_scopes: set[tuple[str, str]] = set()
    for node in iter_condition_nodes(rule.condition_ast):
        if isinstance(node, ComponentMatches | InventoryProvesAbsence):
            package_scopes.add((node.ecosystem, node.package_key))
        elif isinstance(node, VersionInRange):
            package_scopes.add((node.assertion.ecosystem, node.assertion.package_key))
    package_components = tuple(
        item
        for item in receipt.prepared.asset_snapshot.components
        if item.ecosystem == component.ecosystem and item.package_name == component.package_name
    )
    return package_scopes == {(component.ecosystem, component.package_name)} and all(
        item.version == component.version for item in package_components
    )


def _current_citations(
    receipt: AssessmentReceipt, knowledge: KnowledgeReadService
) -> tuple[CitationProjection, ...]:
    citations: dict[UUID, CitationProjection] = {}
    for support in receipt.prepared.inputs.supports:
        reference = support.evidence
        identifier = UUID(reference.evidence_id)
        projected = knowledge.read_evidence(identifier)
        if (
            projected.verified_at is None
            or projected.source_uri is None
            or str(projected.revision_id) != reference.revision_id
            or projected.quote_sha256 != reference.quote_sha256
            or projected.quote_text != reference.quote_text
        ):
            raise PublicWriteMappingError("assessment_evidence_changed")
        locator = knowledge.session.scalar(
            select(evidence.c.locator).where(evidence.c.evidence_id == str(identifier))
        )
        if not isinstance(locator, str) or not locator:
            raise PublicWriteMappingError("assessment_locator_unavailable")
        citation = CitationProjection(
            evidence_id=identifier,
            revision_id=projected.revision_id,
            quote=projected.quote_text,
            locator=locator,
            source_uri=projected.source_uri,
        )
        if identifier in citations and citations[identifier] != citation:
            raise PublicWriteMappingError("assessment_evidence_conflict")
        citations[identifier] = citation
    if len(citations) > 100:
        raise PublicWriteMappingError("assessment_citation_limit")
    return tuple(citations.values())


def stack_current_assessments(
    payload: PublicStackCheckRequest,
    assessment_ids: tuple[UUID | None, ...],
    service: AssessmentService,
    knowledge: KnowledgeReadService,
) -> PublicStackCheckResult:
    """Project trusted PG-selected assessments in the caller's authenticated transaction.

    IDs are an internal server selection, never body fields. Missing selection remains unknown;
    this slice cannot prove all published rules were searched or produce a RiskSummary. Root's
    route must retain the final current-identity and scope-epoch fence before committing.
    """
    knowledge.scope.requires(READ_ASSET)
    if len(assessment_ids) != len(payload.components):
        raise PublicWriteMappingError("component_selection_count_mismatch")
    results: list[PublicComponentAssessment] = []
    limitations = ["selected_assessments_do_not_prove_complete_rule_or_risk_coverage"]
    for component, identifier in zip(payload.components, assessment_ids, strict=True):
        status = AssessmentStatus.INSUFFICIENT_EVIDENCE
        reason = "assessment_not_available"
        freshness = FreshnessStatus.UNKNOWN
        citations: tuple[CitationProjection, ...] = ()
        if identifier is not None:
            receipt = service.read_in_session(knowledge.session, knowledge.scope, str(identifier))
            if (
                receipt.assessment_id != str(identifier)
                or receipt.tenant_id != knowledge.scope.tenant_id
                or not _component_in_snapshot(component, receipt)
            ):
                raise PublicWriteMappingError("component_assessment_binding_mismatch")
            freshness = receipt.freshness
            snapshot = receipt.prepared.asset_snapshot
            rule = receipt.prepared.inputs.rule
            if (
                receipt.asset_id != snapshot.asset_id
                or receipt.asset_snapshot_id != snapshot.snapshot_id
                or receipt.tenant_id != snapshot.tenant_id
                or receipt.rule_id != rule.rule_id
                or receipt.rule_version != rule.version
                or receipt.event_id != rule.event_id
            ):
                raise PublicWriteMappingError("assessment_receipt_identity_mismatch")
            if receipt.rule_result is not None and (
                receipt.rule_result.rule_id != receipt.rule_id
                or receipt.rule_result.rule_version != receipt.rule_version
                or receipt.rule_result.asset_snapshot_id != receipt.asset_snapshot_id
                or receipt.rule_result.status != receipt.status
                or receipt.rule_result.rule_kind != rule.rule_kind
                or receipt.rule_result.condition_sha256 != condition_digest(rule.condition_ast)
            ):
                raise PublicWriteMappingError("assessment_rule_result_mismatch")
            if freshness == FreshnessStatus.CURRENT and not _rule_targets_only_component(
                component, receipt
            ):
                reason = "unsupported_rule"
                limitations.append(
                    "selected_rule_does_not_establish_component_software_applicability"
                )
            elif freshness == FreshnessStatus.CURRENT:
                status = receipt.status
                reason = (
                    receipt.rule_result.evaluation_tree.reason_code
                    if receipt.rule_result is not None
                    else "unsupported_rule"
                )
                citations = _current_citations(receipt, knowledge)
                if status in {
                    AssessmentStatus.SUPPORTED_APPLICABILITY,
                    AssessmentStatus.EXCLUDED_WITH_EVIDENCE,
                } and (receipt.rule_result is None or not citations):
                    raise PublicWriteMappingError("definitive_assessment_support_unavailable")
            else:
                reason = (
                    "assessment_stale"
                    if freshness == FreshnessStatus.STALE
                    else ("assessment_freshness_unknown")
                )
            limitations.extend(receipt.limitations)
        results.append(
            PublicComponentAssessment(
                component=component,
                status=status,
                reason_code=reason,
                assessment_id=identifier,
                citations=citations,
                freshness=freshness,
            )
        )
    unique_limitations = tuple(dict.fromkeys(limitations))
    if len(unique_limitations) > 100:
        raise PublicWriteMappingError("assessment_limitation_limit")
    return PublicStackCheckResult(
        kind="completed", results=tuple(results), limitations=unique_limitations
    )
