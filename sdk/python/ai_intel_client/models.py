"""Typed projections of the approved public API v2; no backend or database imports."""

from __future__ import annotations

import json
import re
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    AnyUrl,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationInfo,
    model_validator,
)

Freshness = Literal["current", "stale", "unknown"]
DataMode = Literal["live", "fixture"]
ClaimStatus = Literal["supported", "disputed", "unverified", "superseded", "withdrawn"]
DimensionName = Literal[
    "cvss", "epss", "kev", "cwe", "atlas", "versions", "literature", "poc", "exposure"
]
DimensionStatus = Literal[
    "available", "not_found", "not_applicable", "conflict", "blocked", "failed", "pending"
]
AssessmentStatus = Literal[
    "supported_applicability",
    "excluded_with_evidence",
    "insufficient_evidence",
    "conflicting_evidence",
]
Text = Annotated[str, Field(min_length=1)]
URI_ADAPTER = TypeAdapter(AnyUrl)
DATETIME_JSON_ADAPTER = TypeAdapter(AwareDatetime, config=ConfigDict(strict=True))


def _validate_absolute_uri(value: str) -> str:
    if (
        re.fullmatch(r"[A-Za-z][A-Za-z0-9+.-]*:[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]*", value)
        is None
        or re.search(r"%(?![0-9a-fA-F]{2})", value) is not None
    ):
        raise ValueError("invalid absolute URI")
    URI_ADAPTER.validate_python(value)
    return value


AbsoluteUri = Annotated[
    str,
    Field(json_schema_extra={"format": "uri"}),
    AfterValidator(_validate_absolute_uri),
]


def _validate_uuid_spelling(value: object) -> object:
    """Check wire spelling before Pydantic can normalize broader UUID forms."""
    if (
        isinstance(value, str)
        and re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value) is None
    ):
        raise ValueError("UUID requires its hyphenated public spelling")
    return value


def _validate_datetime_spelling(value: object, info: ValidationInfo) -> object:
    """Limit JSON text to the frozen date-time format; the core checks calendar validity."""
    if (
        isinstance(value, str)
        and re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt](?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]"
            r"(?:\.[0-9]+)?(?:[Zz]|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])",
            value,
        )
        is None
    ):
        raise ValueError("timestamp requires the public RFC3339 spelling")
    if info.mode == "json" and isinstance(value, str):
        return DATETIME_JSON_ADAPTER.validate_json(json.dumps(value))
    return value


PublicUuid = Annotated[UUID, BeforeValidator(_validate_uuid_spelling)]
PublicDateTime = Annotated[AwareDatetime, BeforeValidator(_validate_datetime_spelling)]


class PublicRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)

    def wire_json(self, *, ensure_ascii: bool = False) -> str:
        """Omitted optional fields remain omitted rather than becoming invalid nulls."""
        return self.model_dump_json(exclude_unset=True, ensure_ascii=ensure_ascii, warnings="error")


class Citation(PublicRecord):
    evidence_id: PublicUuid
    revision_id: PublicUuid
    quote: Text
    locator: Text
    source_uri: AbsoluteUri


class Component(PublicRecord):
    component_id: PublicUuid | None = None
    ecosystem: Text
    package_name: Text
    version: str | None
    purl: str | None = None

    @model_validator(mode="after")
    def require_nonnull_component_id_when_present(self) -> Component:
        if "component_id" in self.model_fields_set and self.component_id is None:
            raise ValueError("component ID cannot be null when present")
        return self


class Enrichment(PublicRecord):
    dimension: DimensionName
    status: DimensionStatus
    claim_ids: tuple[PublicUuid, ...] = Field(max_length=100)
    citations: tuple[Citation, ...] = Field(max_length=100)
    freshness: Freshness
    observed_at: PublicDateTime | None
    source_version: str | None
    error_code: str | None

    @model_validator(mode="after")
    def require_available_evidence(self) -> Enrichment:
        if self.status == "available" and not self.citations:
            raise ValueError("available enrichment requires citations")
        return self


class Relation(PublicRecord):
    relation_id: PublicUuid
    relation_type: Literal[
        "same_event",
        "affects_component_version",
        "mapped_atlas",
        "related_paper",
        "remediated_by",
        "component_version_vulnerability",
    ]
    subject_id: PublicUuid
    object_id: PublicUuid
    source_revision: PublicUuid
    citations: tuple[Citation, ...] = Field(max_length=100)
    rule_or_model_version: Text
    reason: Text
    status: ClaimStatus

    @model_validator(mode="after")
    def require_supported_evidence(self) -> Relation:
        if self.status == "supported" and not self.citations:
            raise ValueError("supported relation requires citations")
        return self


class NormalizedIntel(PublicRecord):
    intel_id: PublicUuid
    revision_id: PublicUuid
    title: Text
    kind: Literal["advisory", "article", "paper", "repository_record", "standard", "policy"]
    external_ids: tuple[Text, ...] = Field(max_length=100)
    citations: tuple[Citation, ...] = Field(max_length=100)
    data_mode: DataMode


class Vulnerability(PublicRecord):
    intel_id: PublicUuid
    event_id: PublicUuid
    title: Text
    external_ids: tuple[Text, ...] = Field(max_length=100)
    enrichments: tuple[Enrichment, ...] = Field(max_length=9)
    relations: tuple[Relation, ...] = Field(max_length=100)
    freshness: Freshness


class Advisory(PublicRecord):
    intel_id: PublicUuid
    revision_id: PublicUuid
    title: Text
    source_uri: AbsoluteUri
    published_at: PublicDateTime | None
    citations: tuple[Citation, ...] = Field(max_length=100)


class AnswerClaim(PublicRecord):
    text: Text
    kind: Literal["source_fact", "rule_result", "project_suggestion"]
    support_ids: tuple[PublicUuid, ...] = Field(max_length=100)

    @model_validator(mode="after")
    def require_fact_support(self) -> AnswerClaim:
        if self.kind != "project_suggestion" and not self.support_ids:
            raise ValueError("facts require support")
        return self


class QAAnswer(PublicRecord):
    kind: Literal["completed"]
    answer_id: PublicUuid
    answer_text: str
    claims: tuple[AnswerClaim, ...] = Field(max_length=100)
    citations: tuple[Citation, ...] = Field(max_length=100)
    limitations: tuple[Text, ...] = Field(max_length=100)
    freshness: Freshness
    data_mode: DataMode
    started_at: PublicDateTime
    completed_at: PublicDateTime
    latency_milliseconds: int = Field(ge=0)

    @model_validator(mode="after")
    def require_complete_support_and_timing(self) -> QAAnswer:
        evidence_ids = [citation.evidence_id for citation in self.citations]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("citations must be unique")
        if any(set(claim.support_ids) - set(evidence_ids) for claim in self.claims):
            raise ValueError("claim support is not present in citations")
        if self.completed_at < self.started_at:
            raise ValueError("answer completion precedes start")
        return self


class TaskHandle(PublicRecord):
    kind: Literal["task"]
    task_id: PublicUuid
    status: Literal["queued", "running", "retry_wait", "waiting_approval", "partial"]
    poll_uri: Annotated[str, Field(pattern=r"^/api/v1/tasks/")]
    created_at: PublicDateTime

    @model_validator(mode="after")
    def require_bound_poll_uri(self) -> TaskHandle:
        if self.poll_uri != f"/api/v1/tasks/{self.task_id}":
            raise ValueError("task polling URI does not match its ID")
        return self


AskResult = Annotated[QAAnswer | TaskHandle, Field(discriminator="kind")]
ASK_RESULT_ADAPTER: TypeAdapter[AskResult] = TypeAdapter(AskResult)


class AskRequest(PublicRecord):
    question: Annotated[str, Field(min_length=1, max_length=4096)]
    conversation_id: PublicUuid | None = None
    asset_ids: tuple[PublicUuid, ...] = Field(default=(), max_length=20)
    event_ids: tuple[PublicUuid, ...] = Field(default=(), max_length=20)
    mode: Literal["auto", "library", "investigate"]
    known_at: PublicDateTime | None = None
    valid_at: PublicDateTime | None = None

    @model_validator(mode="after")
    def validate_question_boundary(self) -> AskRequest:
        if not self.question.strip() or "\0" in self.question:
            raise ValueError("question must be nonempty text")
        try:
            self.question.encode("utf-8")
        except UnicodeError:
            raise ValueError("question must be valid UTF-8") from None
        for name in ("conversation_id", "known_at", "valid_at"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError("omitted optional fields cannot be explicitly null")
        if any(
            value is not None and value.tzinfo is None for value in (self.known_at, self.valid_at)
        ):
            raise ValueError("question timestamps require timezones")
        return self


class StackCheckRequest(PublicRecord):
    components: tuple[Component, ...] = Field(max_length=200)


class ComponentAssessment(PublicRecord):
    component: Component
    status: AssessmentStatus
    reason_code: Text
    assessment_id: PublicUuid | None
    citations: tuple[Citation, ...] = Field(max_length=100)
    freshness: Freshness

    @model_validator(mode="after")
    def preserve_unknown_reasons(self) -> ComponentAssessment:
        if (
            self.reason_code
            in {"no_match", "unsupported", "unsupported_rule", "unsupported_ecosystem"}
            and self.status != "insufficient_evidence"
        ):
            raise ValueError("unsupported and no-match reasons require insufficient evidence")
        return self


class StackCheckResult(PublicRecord):
    kind: Literal["completed"]
    results: tuple[ComponentAssessment, ...] = Field(max_length=200)
    limitations: tuple[Text, ...] = Field(max_length=100)


class StackUploadRequest(PublicRecord):
    upload_id: PublicUuid
    size_bytes: int = Field(ge=1, le=10485760)
    declared_component_count: int = Field(ge=1, le=10000)
    format: Literal[
        "requirements_txt", "package_lock", "sbom_cyclonedx", "json_components", "csv_components"
    ]


Severity = Literal["none", "low", "medium", "high", "critical"]
MinimumSeverity = Literal["low", "medium", "high", "critical"]
Cursor = Annotated[str, Field(min_length=1, max_length=2048)]
StepName = Annotated[str, Field(min_length=1, max_length=500)]
SEVERITY_RANK: dict[str, int] = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


class RiskFinding(PublicRecord):
    component_index: int = Field(ge=0, le=199)
    event_id: PublicUuid
    assessment_id: PublicUuid
    rule_id: PublicUuid
    rule_version: int = Field(ge=1)
    grading_claim_id: PublicUuid
    severity: Severity
    cvss_score: float = Field(ge=0, le=10, allow_inf_nan=False)
    cvss_version: Literal["2.0", "3.0", "3.1", "4.0"]
    citations: tuple[Citation, ...] = Field(min_length=1, max_length=100)
    freshness: Literal["current"]

    @model_validator(mode="after")
    def require_consistent_grade(self) -> RiskFinding:
        score = self.cvss_score
        if score == 0:
            severity = "none"
        elif score < 4:
            severity = "low"
        elif score < 7:
            severity = "medium"
        elif score < 9:
            severity = "high"
        else:
            severity = "critical"
        if self.severity != severity:
            raise ValueError("CVSS score and normalized severity disagree")
        return self


class RiskSummary(PublicRecord):
    policy_version: Literal["r18-risk-policy-1"]
    minimum_severity: MinimumSeverity
    confirmation: Literal["confirmed", "none_confirmed", "unknown", "conflict"]
    coverage: Literal["complete", "partial", "unknown"]
    freshness: Freshness
    evaluated_components: int = Field(ge=0, le=200)
    unknown_component_indices: tuple[Annotated[int, Field(ge=0, le=199)], ...] = Field(
        max_length=200
    )
    findings: tuple[RiskFinding, ...] = Field(max_length=200)

    @model_validator(mode="after")
    def require_consistent_confirmation(self) -> RiskSummary:
        if len(set(self.unknown_component_indices)) != len(self.unknown_component_indices):
            raise ValueError("unknown component indices must be unique")
        identities: set[tuple[int, UUID, UUID, UUID, int, UUID]] = set()
        assessment_bindings: dict[UUID, tuple[int, UUID, UUID, int]] = {}
        claim_bindings: dict[UUID, tuple[UUID, float, str]] = {}
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
            assessment_binding = (
                finding.component_index,
                finding.event_id,
                finding.rule_id,
                finding.rule_version,
            )
            if assessment_bindings.setdefault(finding.assessment_id, assessment_binding) != (
                assessment_binding
            ):
                raise ValueError("one assessment has inconsistent component or event bindings")
            claim_binding = (finding.event_id, finding.cvss_score, finding.cvss_version)
            if claim_bindings.setdefault(finding.grading_claim_id, claim_binding) != claim_binding:
                raise ValueError("one grading claim has inconsistent event or score bindings")
        has_confirmed = any(
            SEVERITY_RANK[finding.severity] >= SEVERITY_RANK[self.minimum_severity]
            for finding in self.findings
        )
        if (self.confirmation == "confirmed") != has_confirmed:
            raise ValueError("risk confirmation disagrees with threshold findings")
        if self.coverage == "complete" and self.confirmation in {"unknown", "conflict"}:
            raise ValueError("unknown or conflicting confirmation cannot have complete coverage")
        if self.confirmation == "none_confirmed" and self.coverage != "complete":
            raise ValueError("no confirmed threshold finding requires a complete evaluated scope")
        if self.coverage == "complete" and (
            self.unknown_component_indices or self.freshness != "current"
        ):
            raise ValueError("complete coverage cannot contain unknown or stale components")
        return self


class StackCheckEnvelope(PublicRecord):
    result: StackCheckResult
    risk_summary: RiskSummary

    @model_validator(mode="after")
    def require_assessment_scope(self) -> StackCheckEnvelope:
        assessments = self.result.results
        summary = self.risk_summary
        if summary.coverage == "complete" and not assessments:
            raise ValueError("empty result scope cannot establish complete coverage")
        if summary.evaluated_components > len(assessments):
            raise ValueError("evaluated component count exceeds the returned scope")
        if any(index >= len(assessments) for index in summary.unknown_component_indices):
            raise ValueError("unknown component index is outside the returned scope")
        for finding in summary.findings:
            if finding.component_index >= len(assessments):
                raise ValueError("finding component index is outside the returned scope")
            assessment = assessments[finding.component_index]
            if (
                assessment.assessment_id != finding.assessment_id
                or assessment.status != "supported_applicability"
                or assessment.freshness != "current"
                or not assessment.citations
            ):
                raise ValueError("finding requires the same current supported assessment")
        graded_indices = {finding.component_index for finding in summary.findings}
        unknown_indices = {
            index
            for index, assessment in enumerate(assessments)
            if assessment.status in {"insufficient_evidence", "conflicting_evidence"}
            or assessment.freshness != "current"
        }
        if not unknown_indices.issubset(summary.unknown_component_indices):
            raise ValueError("risk summary omits unknown or conflicting component results")
        missing_qualification = any(
            assessment.assessment_id is None
            or not assessment.citations
            or (assessment.status == "supported_applicability" and index not in graded_indices)
            for index, assessment in enumerate(assessments)
        )
        if summary.coverage == "complete" and (unknown_indices or missing_qualification):
            raise ValueError("complete scope requires graded support or evidenced exclusion")
        return self


class VulnerabilityPage(PublicRecord):
    items: tuple[Vulnerability, ...] = Field(max_length=100)
    next_cursor: Cursor | None
    data_mode: DataMode

    @model_validator(mode="after")
    def require_unique_events(self) -> VulnerabilityPage:
        event_ids = [item.event_id for item in self.items]
        if len(set(event_ids)) != len(event_ids):
            raise ValueError("vulnerability page event IDs must be unique")
        return self


class VulnerabilityDetailPage(PublicRecord):
    vulnerability: Vulnerability
    advisories: tuple[Advisory, ...] = Field(max_length=100)
    next_cursor: Cursor | None
    mapping_limits: tuple[StepName, ...] = Field(max_length=100)
    data_mode: DataMode


class SourceDescriptor(PublicRecord):
    source_id: Annotated[str, Field(min_length=1, max_length=200)]
    name: StepName
    category: Literal[
        "structured_vulnerability",
        "vendor_advisory",
        "security_community",
        "code_repository",
        "technical_blog",
        "academic_paper",
        "technical_standard",
        "policy_regulation",
    ]
    enabled: bool
    health: Literal["never_polled", "healthy", "partial", "failed", "blocked", "unknown"]
    last_attempt_at: PublicDateTime | None
    last_success_at: PublicDateTime | None
    reason_code: Annotated[str, Field(min_length=1, max_length=100)] | None
    data_mode: DataMode

    @model_validator(mode="after")
    def require_observed_health(self) -> SourceDescriptor:
        if self.health == "healthy" and self.last_success_at is None:
            raise ValueError("healthy sources require an actual successful observation")
        if self.health == "never_polled" and (
            self.last_attempt_at is not None or self.last_success_at is not None
        ):
            raise ValueError("never-polled sources cannot have polling observations")
        return self


class SourcePage(PublicRecord):
    items: tuple[SourceDescriptor, ...] = Field(max_length=100)
    next_cursor: Cursor | None
    data_mode: DataMode

    @model_validator(mode="after")
    def require_unique_sources(self) -> SourcePage:
        if any(item.data_mode != self.data_mode for item in self.items):
            raise ValueError("source page and item data modes must agree")
        source_ids = [item.source_id for item in self.items]
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("source page IDs must be unique")
        return self


class TaskDescriptor(PublicRecord):
    task_id: PublicUuid
    task_type: Literal["ask", "stack_check"]
    status: Literal[
        "queued",
        "running",
        "retry_wait",
        "waiting_approval",
        "succeeded",
        "partial",
        "failed",
        "cancelled",
        "blocked",
    ]
    poll_uri: Annotated[
        str,
        Field(
            pattern=r"^/api/v1/tasks/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
            r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        ),
    ]
    created_at: PublicDateTime
    updated_at: PublicDateTime

    @model_validator(mode="after")
    def require_bound_task_identity(self) -> TaskDescriptor:
        if self.poll_uri != f"/api/v1/tasks/{self.task_id}":
            raise ValueError("task polling URI does not match its ID")
        if self.updated_at < self.created_at:
            raise ValueError("task update precedes creation")
        return self


class PublicProblem(PublicRecord):
    type: AbsoluteUri
    title: StepName
    status: int = Field(ge=400, le=599)
    error: Annotated[str, Field(min_length=1, max_length=100)]
    trace_id: PublicUuid


class TaskResultEnvelope(PublicRecord):
    task: TaskDescriptor
    result: QAAnswer | StackCheckEnvelope | None
    error: PublicProblem | None
    completed_steps: tuple[StepName, ...] = Field(max_length=100)
    pending_steps: tuple[StepName, ...] = Field(max_length=100)
    failed_steps: tuple[StepName, ...] = Field(max_length=100)

    @model_validator(mode="after")
    def require_task_result_consistency(self) -> TaskResultEnvelope:
        steps = (self.completed_steps, self.pending_steps, self.failed_steps)
        if any(len(set(values)) != len(values) for values in steps):
            raise ValueError("task step lists must be unique")
        combined = tuple(step for values in steps for step in values)
        if len(set(combined)) != len(combined):
            raise ValueError("one step cannot have multiple current states")
        if self.result is not None and (
            (self.task.task_type == "ask") != isinstance(self.result, QAAnswer)
        ):
            raise ValueError("result does not match its task type")
        status = self.task.status
        if status in {"queued", "running", "retry_wait", "waiting_approval"} and (
            self.result is not None or self.error is not None
        ):
            raise ValueError("pending tasks cannot have a completed result or error")
        if status == "succeeded" and (
            self.result is None or self.error is not None or self.pending_steps or self.failed_steps
        ):
            raise ValueError("succeeded tasks require only a completed result")
        if status in {"failed", "cancelled", "blocked"} and (
            self.result is not None or self.error is None
        ):
            raise ValueError("unsuccessful terminal tasks require only an explicit problem")
        return self
