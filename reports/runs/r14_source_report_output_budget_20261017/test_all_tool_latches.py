"""Independent typed calls exercise every catalog tool and each actual model role."""

from uuid import UUID

import pytest
from test_r14_shared_read_consumers import consumer_fixture
from test_r14_unknown_boundary_fix2 import make_tool_call

from ai_intel.infrastructure.models.generation import GenerationRequest
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.graph_contracts import PlannerDecision
from ai_intel.investigation.tool_contracts import ToolName, UnconfiguredArguments, UnconfiguredCall

__all__ = ["consumer_fixture"]


@pytest.mark.parametrize("reason", ["operation_outcome_unknown", "model_outcome_unknown"])
@pytest.mark.parametrize("tool_name", list(ToolName))
def test_all_nine_catalog_tools_stop_before_lookup_and_reserve(
    consumer_fixture, monkeypatch, reason, tool_name
):
    fixture = consumer_fixture
    fixture.runtime.last_operation_error = reason

    def forbidden_lookup(key):
        raise AssertionError("later tool lookup reached after unknown result")

    monkeypatch.setattr(fixture.runtime, "lookup", forbidden_lookup)
    if tool_name in {
        ToolName.SEARCH_INTELLIGENCE,
        ToolName.GET_PUBLIC_OBSERVATIONS,
        ToolName.EVALUATE_RULE,
        ToolName.SEARCH_PAPERS,
    }:
        call = UnconfiguredCall(
            tool_name=tool_name.value,
            arguments=UnconfiguredArguments(),
            goal_id=UUID(fixture.runtime.context.job_id),
        )
    else:
        call = make_tool_call(fixture, tool_name.value)
    assert fixture.runtime.tool(AgentRole.ORCHESTRATOR, call, "tool:independent-later") is None
    assert fixture.calls == [] and fixture.reservations == []
    assert fixture.runtime.last_operation_error == reason


@pytest.mark.parametrize("reason", ["operation_outcome_unknown", "model_outcome_unknown"])
@pytest.mark.parametrize("role", [AgentRole.ORCHESTRATOR, AgentRole.QA, AgentRole.CRITIC])
def test_three_actual_model_roles_stop_before_lookup_and_factory(
    consumer_fixture, monkeypatch, reason, role
):
    fixture = consumer_fixture
    fixture.runtime.last_operation_error = reason

    def forbidden_lookup(key):
        raise AssertionError("later model lookup reached after unknown result")

    def forbidden_factory(limits):
        raise AssertionError("model factory reached after unknown result")

    monkeypatch.setattr(fixture.runtime, "lookup", forbidden_lookup)
    fixture.runtime.service.model_factory = forbidden_factory
    request = GenerationRequest(
        system_text="isolated fixture",
        question="explicit offline question",
        evidence_texts=(),
        prompt_version="isolated-fixture-1",
        schema_version="isolated-fixture-1",
        model_version="isolated-fixture-1",
        max_output_tokens=100,
        allow_format_repair=False,
    )
    assert fixture.runtime.model(role, request, PlannerDecision, "model:independent-later") is None
    assert fixture.calls == [] and fixture.reservations == []
    assert fixture.runtime.last_operation_error == reason
