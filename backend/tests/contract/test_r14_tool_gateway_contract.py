"""The internal gateway accepts only approved fixed tools and complete bounded results."""

import json
from uuid import uuid4

import pytest
from pydantic import ValidationError
from test_r14_tool_gateway import (
    FixtureEvidenceReader,
    comparison_call,
    evidence_call,
    evidence_response,
    gateway,
    limits,
)

from ai_intel.investigation.capabilities import (
    B2_ROLE_MAP,
    ROLE_CAPABILITIES,
    TOOL_SPECS,
    AgentRole,
    available_tools,
)
from ai_intel.investigation.tool_contracts import ToolName, ToolResult
from ai_intel.investigation.tool_gateway import EvidenceRead


@pytest.mark.parametrize(
    "field", ["tenant_id", "role", "authorization", "skip_validation", "url", "sql", "shell"]
)
@pytest.mark.parametrize("position", ["call", "arguments"])
def test_t32_c02_and_c06_model_and_material_cannot_add_authority(field: str, position: str) -> None:
    payload = json.loads(evidence_call())
    (payload if position == "call" else payload["arguments"])[field] = "malicious material"
    reader = FixtureEvidenceReader()
    result = gateway(reader).execute(AgentRole.ASSESSOR, json.dumps(payload).encode())
    assert result.status == "denied" and result.error_code == "invalid_tool_input"
    assert result.data is None and reader.calls == 0


@pytest.mark.parametrize(
    "name", ["shell", "execute_sql", "fetch_url", "delete_assets", "READ_EVIDENCE"]
)
def test_t32_c06_unregistered_tool_names_never_dispatch(name: str) -> None:
    payload = json.loads(evidence_call())
    payload["tool_name"] = name
    reader = FixtureEvidenceReader()
    result = gateway(reader).execute(AgentRole.ASSESSOR, json.dumps(payload).encode())
    assert result.status == "denied" and reader.calls == 0


@pytest.mark.parametrize(
    "raw",
    [
        b"[]",
        b'{"tool_name":"read_evidence","tool_name":"shell"}',
        b'{"x":NaN}',
        b'{"x":"\\ud800"}',
        b"{",
    ],
)
def test_invalid_json_is_a_failure_not_an_empty_search(raw: bytes) -> None:
    result = gateway().execute(AgentRole.QA, raw)
    assert result.status == "denied" and result.error_code == "invalid_tool_input"
    assert result.status != "no_result"


def test_role_is_injected_by_server_and_cannot_be_a_model_string() -> None:
    reader = FixtureEvidenceReader()
    result = gateway(reader).execute("assessor", evidence_call())
    assert result.status == "denied" and reader.calls == 0


def test_orchestrator_cannot_call_a_tool_even_if_principal_is_analyst() -> None:
    assert (
        gateway().execute(AgentRole.ORCHESTRATOR, comparison_call()).error_code
        == "role_tool_denied"
    )


def test_registered_unavailable_tool_has_explicit_status_and_no_fallback() -> None:
    result = gateway().execute(
        AgentRole.ASSESSOR,
        json.dumps(
            {
                "tool_name": "get_public_observations",
                "goal_id": str(uuid4()),
                "arguments": {},
            }
        ).encode(),
    )
    assert result.status == "not_configured" and result.error_code == "tool_not_configured"
    assert result.usage.service_calls == 0 and not result.is_synthetic


def test_oversized_evidence_preserves_full_reference_and_drops_complete_data() -> None:
    reader = FixtureEvidenceReader()
    reader.outcome = EvidenceRead(evidence_response("中" * 4000), True)
    result = gateway(reader, max_result_bytes=1024).execute(AgentRole.ASSESSOR, evidence_call())
    assert (
        result.status == "partial" and result.error_code == "output_limit" and result.data is None
    )
    assert result.evidence_ids == (reader.outcome.evidence.span_id,)
    assert result.searched_scope.revision_id == reader.outcome.evidence.revision_id
    assert result.usage.result_bytes == len(result.model_dump_json().encode()) <= 1024


def test_byte_limit_counts_utf8_and_blocks_before_io() -> None:
    reader = FixtureEvidenceReader()
    subject = gateway(reader, max_request_bytes=100)
    result = subject.execute(AgentRole.ASSESSOR, evidence_call())
    assert result.status == "budget_exhausted" and result.error_code == "input_budget_exhausted"
    assert reader.calls == 0


def test_total_input_bytes_prevent_unlimited_replay() -> None:
    subject = gateway(max_total_input_bytes=len(comparison_call()))
    assert subject.execute(AgentRole.ASSESSOR, comparison_call()).status == "succeeded"
    assert (
        subject.execute(AgentRole.ASSESSOR, comparison_call()).error_code
        == "input_budget_exhausted"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"max_calls": True},
        {"max_calls": 0},
        {"max_calls": 9},
        {"max_concurrent_calls": 0},
        {"max_result_bytes": 100},
        {"deadline_monotonic": float("inf")},
        {"deadline_monotonic": float("nan")},
    ],
)
def test_server_budget_itself_is_strict_and_finite(change: dict[str, int | float]) -> None:
    with pytest.raises(ValidationError):
        limits(**change)


def test_nine_w10_responsibilities_and_nine_tool_names_are_immutable_and_honest() -> None:
    assert len(ROLE_CAPABILITIES) == 9 and set(ROLE_CAPABILITIES) == set(AgentRole)
    assert len(TOOL_SPECS) == 9 and set(TOOL_SPECS) == set(ToolName)
    assert (
        available_tools("B2")
        == available_tools("B2b")
        == available_tools("B3")
        == {
            ToolName.READ_EVIDENCE,
            ToolName.COMPARE_VERSIONS,
        }
    )
    assert {role for roles in B2_ROLE_MAP.values() for role in roles} == set(AgentRole)
    assert all(
        capability.responsibility and capability.output_requirement and capability.unavailable_work
        for capability in ROLE_CAPABILITIES.values()
    )
    assert all(
        spec.input_schema is None and spec.output_schema is None
        for spec in TOOL_SPECS.values()
        if not spec.configured
    )
    with pytest.raises(TypeError):
        TOOL_SPECS[ToolName.GET_PUBLIC_OBSERVATIONS] = TOOL_SPECS[ToolName.READ_EVIDENCE]


def test_tool_result_retains_all_original_05_fields_and_existing_business_models() -> None:
    fields = ToolResult.model_json_schema()["properties"]
    assert {
        "tool_run_id",
        "status",
        "data",
        "evidence_ids",
        "searched_scope",
        "observed_at",
        "executed_at",
        "retryable",
        "error_code",
        "usage",
        "is_synthetic",
    } <= set(fields)
    assert "EvidenceResponse" in ToolResult.model_json_schema()["$defs"]
    assert "VersionComparison" in ToolResult.model_json_schema()["$defs"]
