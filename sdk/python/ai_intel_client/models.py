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
