"""Bounded investigation contracts keep model choices separate from server authority."""

from __future__ import annotations

import hashlib
import json
from typing import Literal, TypedDict
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, model_validator

from ai_intel.answering.contracts import GeneratedAnswer
from ai_intel.assessment.conditions import (
    AllOf,
    AnyOf,
    ConditionEvaluation,
    ConditionNode,
    combine_condition_values,
)
from ai_intel.domain.enums import ConditionValue
from ai_intel.infrastructure.models.json_output import strict_json_object
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.tool_contracts import CompareVersionsArguments, ReadEvidenceArguments

GRAPH_VERSION: Literal["r14-langgraph-1"] = "r14-langgraph-1"
Strategy = Literal["B2", "B2b", "B3"]


class WorkflowRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)


class InvestigationRequest(WorkflowRecord):
    question: str = Field(min_length=1, max_length=4096)
    event_id: UUID
    evidence_refs: tuple[ReadEvidenceArguments, ...] = Field(max_length=8)
    strategy: Strategy = "B2b"
    asset_id: UUID | None = None
    asset_snapshot_id: UUID | None = None
    version_comparison: CompareVersionsArguments | None = None

    @model_validator(mode="after")
    def require_consistent_identifiers(self) -> InvestigationRequest:
        if not self.question.strip() or "\0" in self.question:
            raise ValueError("invalid question")
        self.question.encode("utf-8")
        if any(reference.event_id != self.event_id for reference in self.evidence_refs):
            raise ValueError("evidence event mismatch")
        if len({reference.evidence_id for reference in self.evidence_refs}) != len(
            self.evidence_refs
        ):
            raise ValueError("duplicate evidence")
        if (self.asset_id is None) != (self.asset_snapshot_id is None):
            raise ValueError("asset and snapshot must be paired")
        return self


class WorkflowBudget(WorkflowRecord):
    max_tool_calls: int = Field(default=8, ge=1, le=8)
    max_model_calls: int = Field(default=3, ge=0, le=6)
    max_input_bytes: int = Field(default=524288, ge=1024, le=1048576)
    max_output_bytes: int = Field(default=262144, ge=1024, le=1048576)
    model_request_bytes: int = Field(default=65536, ge=1024, le=262144)
    model_response_bytes: int = Field(default=32768, ge=1024, le=262144)
    tool_result_bytes: int = Field(default=16384, ge=1024, le=1048576)
    total_seconds: float = Field(default=120.0, gt=0, le=600, allow_inf_nan=False)
    model_call_seconds: float = Field(default=20.0, gt=0, le=30, allow_inf_nan=False)


class PlannerDecision(WorkflowRecord):
    candidate_action_id: str = Field(min_length=1, max_length=100)
    reason_code: Literal["fill_current_support", "fill_version_ordering"]
    short_reason: str = Field(min_length=1, max_length=300)


class MissingRequirement(WorkflowRecord):
    requirement_id: str = Field(min_length=1, max_length=100)
    state: Literal["unknown", "conflict"]
    decision_relevant: bool
    candidate_action_ids: tuple[str, ...] = Field(max_length=8)


class RoleReceipt(WorkflowRecord):
    role: AgentRole
    status: Literal["succeeded", "partial", "failed", "not_configured", "skipped"]
    reason_code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,99}$")
    evidence_ids: tuple[UUID, ...] = Field(max_length=8)
    operation_keys: tuple[str, ...] = Field(max_length=12)
    output: dict[str, JsonValue]


class WorkflowResult(WorkflowRecord):
    job_id: UUID
    status: Literal["running", "waiting_approval", "succeeded", "partial", "failed", "stale"]
    stop_reason: str
    graph_version: Literal["r14-langgraph-1"] = GRAPH_VERSION
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_mode: Literal["fixture", "live"]
    receipts: tuple[RoleReceipt, ...] = Field(max_length=9)
    answer: GeneratedAnswer | None = None
    evidence_ids: tuple[UUID, ...] = Field(max_length=8)
    missing_requirements: tuple[str, ...] = Field(max_length=20)


class WorkflowState(TypedDict):
    input_sha256: str
    receipts: list[dict[str, JsonValue]]
    evidence: list[dict[str, JsonValue]]
    draft: dict[str, JsonValue] | None
    verified: bool
    candidate_action_id: str | None
    status: str
    stop_reason: str


def json_object(value: BaseModel | dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Only JSON representations cross the graph/checkpoint boundary."""
    raw = value.model_dump_json() if isinstance(value, BaseModel) else json.dumps(value)
    return TypeAdapter(dict[str, JsonValue]).validate_json(raw)


def configuration_digest(value: dict[str, JsonValue]) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def parse_investigation_request(raw: bytes) -> InvestigationRequest:
    payload = strict_json_object(raw, 65536, maximum_nodes=300)
    return InvestigationRequest.model_validate_json(json.dumps(payload, ensure_ascii=False))


def decision_relevant_requirement(
    condition: ConditionNode, evaluation: ConditionEvaluation, node_id: str
) -> bool:
    """Counterfactual copies rank gaps; they never change facts or resolve a conflict."""
    found = False

    def counterfactual(
        node: ConditionNode, result: ConditionEvaluation, replacement: ConditionValue
    ) -> ConditionValue:
        nonlocal found
        if node.node_id != result.node_id:
            raise ValueError("evaluation tree mismatch")
        if node.node_id == node_id:
            found = True
            return replacement
        if isinstance(node, AllOf | AnyOf):
            if len(node.children) != len(result.child_results):
                raise ValueError("evaluation children missing")
            children = tuple(
                counterfactual(child, outcome, replacement)
                for child, outcome in zip(node.children, result.child_results, strict=True)
            )
            return combine_condition_values(node.kind, children)
        return result.value

    try:
        true_result = counterfactual(condition, evaluation, ConditionValue.TRUE)
        false_result = counterfactual(condition, evaluation, ConditionValue.FALSE)
    except ValueError:
        return True
    return not found or true_result != false_result
