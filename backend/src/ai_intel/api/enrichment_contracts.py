"""Public workflow projections distinguish dispatch success from dimension publication."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from ai_intel.domain.enrichment_values import DimensionName
from ai_intel.domain.enums import DimensionStatus
from ai_intel.domain.records import StrictRecord
from ai_intel.domain.values import UtcTimestamp
from ai_intel.infrastructure.models.generation import AttemptMetadata

WorkflowJobStatus = Literal[
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


class EnrichmentEnqueueResponse(StrictRecord):
    """The parent job acknowledges durable scheduling, not finished enrichment."""

    workflow_id: UUID
    parent_job_id: UUID
    reused: bool


class EnrichmentDimensionResponse(StrictRecord):
    dimension: DimensionName
    status: WorkflowJobStatus
    error_code: str | None = Field(max_length=100)
    job_ids: tuple[UUID, ...] = Field(max_length=2)
    result_status: DimensionStatus | None


class EnrichmentStepResponse(StrictRecord):
    """Gateway receipts contain hashes and usage, never prompts, sessions or credentials."""

    job_id: UUID
    step_key: str = Field(min_length=1, max_length=40)
    dimension: DimensionName | None
    provider: Literal["hunter", "quake"] | None
    status: WorkflowJobStatus
    error_code: str | None = Field(max_length=100)
    output_token_budget: Literal[0, 1024]
    model_call_state: Literal["not_reserved", "reserved", "completed", "incomplete_interrupted"]
    model_attempts: tuple[AttemptMetadata, ...] = Field(max_length=1)


class EnrichmentWorkflowResponse(StrictRecord):
    workflow_id: UUID
    parent_job_id: UUID
    event_id: UUID
    data_mode: Literal["live", "fixture"]
    parent_status: WorkflowJobStatus
    scheduling_complete: bool
    workflow_complete: bool
    publication_status: WorkflowJobStatus | None
    logical_dimensions: tuple[EnrichmentDimensionResponse, ...] = Field(min_length=1, max_length=9)
    steps: tuple[EnrichmentStepResponse, ...] = Field(max_length=11)
    created_at: UtcTimestamp
    initialized_at: UtcTimestamp | None
