"""Internal investigation inputs retain existing business DTOs and reject model authority."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, TypeAdapter

from ai_intel.api.knowledge_contracts import EvidenceResponse
from ai_intel.assessment.version_ranges import VersionComparison
from ai_intel.domain.enums import ToolStatus
from ai_intel.domain.records import StrictRecord
from ai_intel.domain.values import UtcTimestamp
from ai_intel.infrastructure.models.json_output import strict_json_object


class ToolName(StrEnum):
    SEARCH_INTELLIGENCE = "search_intelligence"
    GET_ADVISORY = "get_advisory"
    GET_INVENTORY = "get_inventory"
    GET_PUBLIC_OBSERVATIONS = "get_public_observations"
    COMPARE_VERSIONS = "compare_versions"
    EVALUATE_RULE = "evaluate_rule"
    SEARCH_PAPERS = "search_papers"
    READ_EVIDENCE = "read_evidence"
    FIND_CHANGES = "find_changes"


class ToolInput(StrictRecord):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ReadEvidenceArguments(ToolInput):
    event_id: UUID
    evidence_id: UUID
    revision_id: UUID


class CompareVersionsArguments(ToolInput):
    left_version: str | None = Field(max_length=128)
    right_version: str | None = Field(max_length=128)
    scheme: Literal["pep440", "semver", "osv_ecosystem", "unknown"]
    ecosystem: str = Field(min_length=1, max_length=100)


class ReadEvidenceCall(ToolInput):
    tool_name: Literal["read_evidence"]
    arguments: ReadEvidenceArguments
    goal_id: UUID


class CompareVersionsCall(ToolInput):
    tool_name: Literal["compare_versions"]
    arguments: CompareVersionsArguments
    goal_id: UUID


class UnconfiguredArguments(ToolInput):
    """Unavailable tools accept no speculative URL, query or authority contract."""


class UnconfiguredCall(ToolInput):
    tool_name: Literal[
        "search_intelligence",
        "get_advisory",
        "get_inventory",
        "get_public_observations",
        "evaluate_rule",
        "search_papers",
        "find_changes",
    ]
    arguments: UnconfiguredArguments
    goal_id: UUID


ToolCall = ReadEvidenceCall | CompareVersionsCall | UnconfiguredCall
TOOL_CALL_ADAPTER: TypeAdapter[ToolCall] = TypeAdapter(
    Annotated[ToolCall, Field(discriminator="tool_name")]
)


def parse_tool_call(raw: bytes, maximum_bytes: int) -> ToolCall:
    """The shared JSON boundary checks duplicate keys, depth and Unicode before schemas."""
    payload = strict_json_object(raw, maximum_bytes, maximum_nodes=100)
    return TOOL_CALL_ADAPTER.validate_json(json.dumps(payload, ensure_ascii=False))


class ToolUsage(StrictRecord):
    request_bytes: int = Field(strict=True, ge=0)
    result_bytes: int = Field(strict=True, ge=0)
    service_calls: int = Field(strict=True, ge=0)
    cached: bool


class SearchedScope(StrictRecord):
    """Identifiers describe a bounded read, never a claim about worldwide absence."""

    goal_id: UUID | None
    scope_kind: Literal["public", "tenant", "local", "none"]
    event_id: UUID | None = None
    revision_id: UUID | None = None


class ToolResult(StrictRecord):
    tool_run_id: UUID
    call_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool_name: ToolName | None
    status: ToolStatus
    data: EvidenceResponse | VersionComparison | None
    evidence_ids: tuple[UUID, ...] = Field(max_length=1)
    searched_scope: SearchedScope
    observed_at: UtcTimestamp | None
    executed_at: UtcTimestamp
    retryable: bool
    error_code: str | None = Field(max_length=80)
    usage: ToolUsage
    is_synthetic: bool
    limitations: tuple[str, ...] = Field(max_length=3)
