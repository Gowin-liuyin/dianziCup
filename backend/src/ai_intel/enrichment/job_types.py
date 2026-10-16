"""Typed internal snapshots and safe projections of the existing PostgreSQL job authority."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from ai_intel.domain.enrichment_values import DimensionName
from ai_intel.domain.enums import DimensionStatus
from ai_intel.domain.values import VisibilityScope
from ai_intel.enrichment.contracts import DimensionAttempt, EnrichmentContext, EnrichmentDocument
from ai_intel.enrichment.evidence_selection import FieldEvidenceSelection
from ai_intel.enrichment.inputs import LoadedEnrichmentInputs
from ai_intel.enrichment.job_contracts import (
    EnrichmentExecutionPolicy,
    EnrichmentModelInputVersions,
    EventEnrichmentRequest,
)
from ai_intel.infrastructure.models.generation import AttemptMetadata, Provider

type JobStatus = Literal[
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
type ExposureProvider = Literal["hunter", "quake"]
type ModelCallState = Literal["not_reserved", "reserved", "completed", "incomplete_interrupted"]
TERMINAL_STATUSES = frozenset({"succeeded", "partial", "failed", "cancelled", "blocked"})
MODEL_DIMENSIONS = frozenset({"atlas", "versions", "literature", "poc"})
INPUT_AUDIT_VERSION: Literal["r07-input-audit-1"] = "r07-input-audit-1"
MAX_INPUT_AUDIT_BYTES = 4 * 1024 * 1024
type ModelDimension = Literal["atlas", "versions", "literature", "poc"]
type InputAuditState = Literal["recorded", "legacy_unavailable", "not_recorded"]
type AuditDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class InternalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


@dataclass(frozen=True)
class EnrichmentEnqueueReceipt:
    workflow_id: UUID
    parent_job_id: UUID
    reused: bool


class EnrichmentStepView(InternalRecord):
    job_id: UUID
    step_key: str
    dimension: DimensionName | None
    provider: ExposureProvider | None
    status: JobStatus
    error_code: str | None
    output_token_budget: int
    model_call_state: ModelCallState
    model_attempts: tuple[AttemptMetadata, ...]


class EnrichmentDimensionView(InternalRecord):
    dimension: DimensionName
    status: JobStatus
    error_code: str | None
    job_ids: tuple[UUID, ...]
    result_status: DimensionStatus | None


class EnrichmentWorkflowView(InternalRecord):
    workflow_id: UUID
    parent_job_id: UUID
    event_id: UUID
    data_mode: Literal["live", "fixture"]
    parent_status: JobStatus
    scheduling_complete: bool
    workflow_complete: bool
    publication_status: JobStatus | None
    logical_dimensions: tuple[EnrichmentDimensionView, ...]
    steps: tuple[EnrichmentStepView, ...]
    created_at: datetime
    initialized_at: datetime | None


class StepSpec(InternalRecord):
    step_key: str
    dimension: DimensionName
    provider: ExposureProvider | None = None
    output_token_budget: int = 0


class EnrichmentJobPayload(InternalRecord):
    workflow_id: UUID
    binding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    step_key: str | None = Field(default=None, max_length=30)


class ParentScopeSnapshot(InternalRecord):
    revision_id: str
    document_id: str
    source_id: str
    revision_visibility: str
    revision_tenant_id: str | None
    document_visibility: str
    document_tenant_id: str | None
    source_visibility: str
    source_tenant_id: str | None
    source_category: str


class DocumentSnapshot(EnrichmentDocument):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        ser_json_bytes="base64",
        val_json_bytes="base64",
    )


class FrozenEnrichmentInputs(InternalRecord):
    context: EnrichmentContext
    scope: VisibilityScope
    documents: tuple[DocumentSnapshot, ...]
    parents: tuple[ParentScopeSnapshot, ...]

    def loaded(self) -> LoadedEnrichmentInputs:
        return LoadedEnrichmentInputs(
            self.context,
            tuple(
                EnrichmentDocument.model_validate(document.model_dump())
                for document in self.documents
            ),
            self.scope,
        )


class InputAuditRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)


class InputSelectionRange(InputAuditRecord):
    revision_id: UUID
    block_id: UUID
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=1)
    matched_cues: tuple[Annotated[str, Field(min_length=1, max_length=200)], ...] = Field(
        max_length=50
    )

    @model_validator(mode="after")
    def validate_unicode_range(self) -> InputSelectionRange:
        if self.end_offset <= self.start_offset:
            raise ValueError("input_audit_range_invalid")
        return self


class InputSourceVersion(InputAuditRecord):
    revision_id: UUID
    document_id: UUID
    source_id: UUID
    content_sha256: AuditDigest
    source_version: Annotated[str, Field(min_length=1, max_length=200)] | None
    canonical_uri: str = Field(min_length=1, max_length=4000)


class FieldEvidenceSelectionAudit(InputAuditRecord):
    """The actual returned selection is retained; omitted text is referenced, never copied."""

    dimension: ModelDimension
    texts: tuple[Annotated[str, Field(min_length=1, max_length=16384)], ...] = Field(
        min_length=2, max_length=50
    )
    selected: tuple[InputSelectionRange, ...] = Field(min_length=1, max_length=49)
    omitted_block_ids: tuple[tuple[UUID, UUID], ...] = Field(max_length=4000)
    omitted_ranges: tuple[InputSelectionRange, ...] = Field(max_length=4050)
    source_versions: tuple[InputSourceVersion, ...] = Field(min_length=1, max_length=20)
    incomplete: bool
    selection_version: str = Field(min_length=1, max_length=200)

    @classmethod
    def from_selection(cls, selection: FieldEvidenceSelection) -> FieldEvidenceSelectionAudit:
        return cls.model_validate_json(TypeAdapter(FieldEvidenceSelection).dump_json(selection))


class EnrichmentModelInputAudit(InputAuditRecord):
    audit_version: Literal["r07-input-audit-1"] = INPUT_AUDIT_VERSION
    workflow_id: UUID
    job_id: UUID
    dimension: ModelDimension
    input_fingerprint: AuditDigest
    execution_policy_sha256: AuditDigest
    model_input_versions: EnrichmentModelInputVersions
    provider: Provider
    model_version: str = Field(min_length=1, max_length=200)
    input_selections: tuple[FieldEvidenceSelectionAudit, ...] = Field(min_length=1, max_length=1)


class EnrichmentInputAuditView(InputAuditRecord):
    """Internal authorized read; the public workflow DTO never includes quoted source text."""

    workflow_id: UUID
    job_id: UUID
    audit_state: InputAuditState
    record: EnrichmentModelInputAudit | None
    model_attempts: tuple[AttemptMetadata, ...]


class SelectionReport(InputAuditRecord):
    selection_version: str
    dimension: ModelDimension
    incomplete: bool
    selected_ranges: int = Field(ge=1, le=49)
    omitted_blocks: int = Field(ge=0, le=4000)
    omitted_ranges: int = Field(ge=0, le=4050)
    source_revisions: tuple[UUID, ...] = Field(min_length=1, max_length=20)
    instruction: str = Field(min_length=1, max_length=1000)


class SelectionReportEnvelope(InputAuditRecord):
    selection: SelectionReport


class SelectionTextRecord(InputAuditRecord):
    revision_id: UUID
    document_id: UUID
    source_id: UUID
    canonical_uri: str
    document_kind: str
    source_category: str
    source_version: str | None
    content_sha256: AuditDigest
    content_coverage: str
    blocks_complete: bool
    block_id: UUID
    block_text_sha256: AuditDigest
    block_start_offset: int = Field(ge=0)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=20000)


def validate_input_selection(
    selection: FieldEvidenceSelectionAudit,
    frozen: FrozenEnrichmentInputs,
) -> None:
    """Verify immutable anchors and the exact Unicode complement without rerunning retrieval."""
    documents = frozen.documents
    expected_sources = tuple(
        InputSourceVersion(
            revision_id=document.revision_id,
            document_id=document.document_id,
            source_id=document.source_id,
            content_sha256=document.content_sha256,
            source_version=document.source_version,
            canonical_uri=str(document.canonical_uri),
        )
        for document in documents
    )
    if (
        selection.source_versions != expected_sources
        or len(selection.texts) != len(selection.selected) + 1
    ):
        raise ValueError("input_audit_source_identity_invalid")
    if sum(len(text.encode()) for text in selection.texts) > 65536:
        raise ValueError("input_audit_model_input_budget_invalid")
    blocks = {
        (document.revision_id, block.block_id): (document, block)
        for document in documents
        for block in document.blocks
    }
    for item, encoded in zip(selection.selected, selection.texts[1:], strict=True):
        parent = blocks.get((item.revision_id, item.block_id))
        if parent is None or item.end_offset > len(parent[1].text):
            raise ValueError("input_audit_range_invalid")
        document, block = parent
        record = SelectionTextRecord.model_validate_json(encoded)
        expected = SelectionTextRecord(
            revision_id=document.revision_id,
            document_id=document.document_id,
            source_id=document.source_id,
            canonical_uri=str(document.canonical_uri),
            document_kind=document.document_kind.value,
            source_category=document.source_category.value,
            source_version=document.source_version,
            content_sha256=document.content_sha256,
            content_coverage=document.content_coverage,
            blocks_complete=document.blocks_complete,
            block_id=block.block_id,
            block_text_sha256=block.text_sha256,
            block_start_offset=block.start_offset,
            start_offset=item.start_offset,
            end_offset=item.end_offset,
            text=block.text[item.start_offset : item.end_offset],
        )
        if record != expected:
            raise ValueError("input_audit_anchor_invalid")
    expected_omitted = []
    expected_block_ids = []
    for key, (_, block) in blocks.items():
        selected = sorted(
            (item.start_offset, item.end_offset)
            for item in selection.selected
            if (item.revision_id, item.block_id) == key
        )
        if not selected:
            expected_block_ids.append(key)
        position = 0
        for start, end in selected:
            if start < position:
                raise ValueError("input_audit_ranges_overlap")
            if start > position:
                expected_omitted.append(
                    InputSelectionRange(
                        revision_id=key[0],
                        block_id=key[1],
                        start_offset=position,
                        end_offset=start,
                        matched_cues=(),
                    )
                )
            position = end
        if position < len(block.text):
            expected_omitted.append(
                InputSelectionRange(
                    revision_id=key[0],
                    block_id=key[1],
                    start_offset=position,
                    end_offset=len(block.text),
                    matched_cues=(),
                )
            )
    incomplete = bool(expected_omitted) or any(
        not document.blocks_complete or document.content_coverage != "full_text"
        for document in documents
    )
    if (
        selection.omitted_ranges != tuple(expected_omitted)
        or selection.omitted_block_ids != tuple(expected_block_ids)
        or selection.incomplete != incomplete
    ):
        raise ValueError("input_audit_omission_invalid")
    report = SelectionReportEnvelope.model_validate_json(selection.texts[0]).selection
    if (
        report.selection_version != selection.selection_version
        or report.dimension != selection.dimension
        or report.incomplete != incomplete
        or report.selected_ranges != len(selection.selected)
        or report.omitted_blocks != len(selection.omitted_block_ids)
        or report.omitted_ranges != len(selection.omitted_ranges)
        or report.source_revisions != tuple(document.revision_id for document in documents)
    ):
        raise ValueError("input_audit_report_invalid")


def validate_model_input_audit(
    audit: EnrichmentModelInputAudit,
    frozen: FrozenEnrichmentInputs,
    policy: EnrichmentExecutionPolicy,
    attempts: tuple[AttemptMetadata, ...],
) -> None:
    versions = policy.model_input_versions
    if versions is None or audit.model_input_versions != versions or len(attempts) != 1:
        raise ValueError("input_audit_versions_invalid")
    trace = attempts[0]
    if (
        trace.prompt_version != versions.prompt_version
        or trace.schema_version != versions.schema_version
        or trace.provider != audit.provider
        or trace.requested_model != audit.model_version
        or policy.generation_provider != audit.provider
        or policy.approved_model != audit.model_version
    ):
        raise ValueError("input_audit_trace_invalid")
    for selection in audit.input_selections:
        if (
            selection.dimension != audit.dimension
            or selection.selection_version != versions.selection_version
        ):
            raise ValueError("input_audit_selection_version_invalid")
        validate_input_selection(selection, frozen)


class ExposureStepClient(Protocol):
    """R08 supplies one fixed provider call; aggregate publication remains a separate seam."""

    def collect_aggregate(
        self,
        provider: ExposureProvider,
        product_query_id: Literal["ollama", "vllm"],
        *,
        request_timeout_seconds: float,
    ) -> DimensionAttempt: ...


def physical_steps(request: EventEnrichmentRequest) -> tuple[StepSpec, ...]:
    steps: list[StepSpec] = []
    for dimension in request.dimensions:
        if dimension == "exposure":
            providers: tuple[ExposureProvider, ...] = ("hunter", "quake")
            steps.extend(
                StepSpec(step_key="exposure:" + provider, dimension=dimension, provider=provider)
                for provider in providers
            )
        else:
            steps.append(
                StepSpec(
                    step_key=dimension,
                    dimension=dimension,
                    output_token_budget=1024 if dimension in MODEL_DIMENSIONS else 0,
                )
            )
    return tuple(steps)


def logical_job_status(statuses: tuple[JobStatus, ...]) -> JobStatus:
    if not statuses:
        return "queued"
    if any(status not in TERMINAL_STATUSES for status in statuses):
        if all(status == "queued" for status in statuses):
            return "queued"
        return "running"
    if len(set(statuses)) == 1:
        return statuses[0]
    return "partial"


def json_payload(record: BaseModel) -> bytes:
    return json.dumps(
        record.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def combine_exposure_attempts(attempts: tuple[DimensionAttempt, ...]) -> DimensionAttempt:
    """Unknown query is not a zero count; no unreviewed aggregate becomes a supported fact."""
    if not attempts or any(attempt.dimension != "exposure" for attempt in attempts):
        raise ValueError("exposure_attempt_shape_invalid")
    if any(attempt.candidates for attempt in attempts):
        raise ValueError("aggregate_publication_not_connected")
    if all(attempt.status == DimensionStatus.BLOCKED for attempt in attempts):
        status = DimensionStatus.BLOCKED
    elif any(attempt.status == DimensionStatus.FAILED for attempt in attempts):
        status = DimensionStatus.FAILED
    else:
        status = DimensionStatus.PENDING
    return DimensionAttempt(
        dimension="exposure",
        status=status,
        error_code=next(
            (attempt.error_code for attempt in attempts if attempt.error_code), "exposure_unknown"
        ),
        source_ids=tuple(
            dict.fromkeys(source for attempt in attempts for source in attempt.source_ids)
        ),
    )
