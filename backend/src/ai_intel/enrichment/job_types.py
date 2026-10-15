"""Typed internal snapshots and safe projections of the existing PostgreSQL job authority."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ai_intel.domain.enrichment_values import DimensionName
from ai_intel.domain.enums import DimensionStatus
from ai_intel.domain.values import VisibilityScope
from ai_intel.enrichment.contracts import DimensionAttempt, EnrichmentContext, EnrichmentDocument
from ai_intel.enrichment.inputs import LoadedEnrichmentInputs
from ai_intel.enrichment.job_contracts import EventEnrichmentRequest
from ai_intel.infrastructure.models.generation import AttemptMetadata

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
