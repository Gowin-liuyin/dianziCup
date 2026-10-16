"""Explicit fixture graphs test boundaries; these tests are not real Agent/live evidence."""

import json
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import ValidationError

from ai_intel.assessment.conditions import AllOf, ConditionEvaluation, ConfigurationEquals
from ai_intel.domain.enums import ConditionValue
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.checkpoint_runtime import (
    PlainJsonSerializer,
    local_graph_execution,
    validate_checkpoint_schema,
)
from ai_intel.investigation.graph import build_investigation_graph
from ai_intel.investigation.graph_contracts import (
    InvestigationRequest,
    PlannerDecision,
    WorkflowBudget,
    configuration_digest,
    decision_relevant_requirement,
)
from ai_intel.investigation.tool_contracts import ReadEvidenceArguments
from ai_intel.investigation.workflow_service import _initial_state


def request_fields():
    event_id = uuid4()
    return {
        "question": "本次公告说明什么？",
        "event_id": event_id,
        "evidence_refs": (
            ReadEvidenceArguments(event_id=event_id, evidence_id=uuid4(), revision_id=uuid4()),
        ),
    }


@pytest.mark.parametrize(
    "field",
    [
        "tenant_id",
        "owner_user_id",
        "thread_id",
        "checkpoint_id",
        "credential",
        "role",
        "skip_validation",
    ],
)
def test_request_rejects_authority_injection(field):
    with pytest.raises(ValidationError):
        InvestigationRequest(**request_fields(), **{field: "forged"})


@pytest.mark.parametrize(
    "changes", [{"question": "\0"}, {"asset_id": uuid4()}, {"strategy": "freeform"}]
)
def test_request_rejects_invalid_boundary(changes):
    with pytest.raises(ValidationError):
        InvestigationRequest(**{**request_fields(), **changes})


def test_cross_event_evidence_and_duplicate_evidence_rejected():
    fields = request_fields()
    reference = fields["evidence_refs"][0]
    with pytest.raises(ValidationError):
        InvestigationRequest(**{**fields, "event_id": uuid4()})
    with pytest.raises(ValidationError):
        InvestigationRequest(**{**fields, "evidence_refs": (reference, reference)})


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_tool_calls", 9),
        ("max_model_calls", -1),
        ("total_seconds", float("inf")),
        ("model_call_seconds", 31.0),
        ("max_model_calls", True),
    ],
)
def test_budget_rejects_unbounded_or_coerced_values(field, value):
    with pytest.raises(ValidationError):
        WorkflowBudget(**{field: value})


def test_planner_has_no_tool_permission_or_final_assessment_fields():
    raw = {
        "candidate_action_id": "read_evidence:1",
        "reason_code": "fill_current_support",
        "short_reason": "核验当前来源",
    }
    for field in ["tool_name", "authorization", "finalAssessment"]:
        with pytest.raises(ValidationError):
            PlannerDecision.model_validate_json(json.dumps({**raw, field: "forged"}))


@pytest.mark.parametrize("kind", ["pickle", "msgpack", "bytes", "unsafe_python_object"])
def test_serializer_refuses_non_json_tags(kind):
    with pytest.raises(ValueError):
        PlainJsonSerializer().loads_typed((kind, b"payload"))


@pytest.mark.parametrize("value", [object(), uuid4(), {1: "bad"}, float("nan"), "\ud800"])
def test_serializer_refuses_objects_non_text_keys_and_nan(value):
    with pytest.raises(ValueError):
        PlainJsonSerializer().dumps_typed(value)


def test_serializer_duplicate_keys_cycles_and_depth_fail_without_execution():
    serializer = PlainJsonSerializer()
    with pytest.raises(ValueError):
        serializer.loads_typed(("json", b'{"a":1,"a":2}'))
    cyclic = []
    cyclic.append(cyclic)
    with pytest.raises(ValueError):
        serializer.dumps_typed(cyclic)
    deep = []
    for _ in range(26):
        deep = [deep]
    with pytest.raises(ValueError):
        serializer.dumps_typed(deep)
    payload = {
        "lc": 2,
        "type": "constructor",
        "id": ["os", "system"],
        "kwargs": {"command": "forged"},
    }
    assert serializer.loads_typed(serializer.dumps_typed(payload)) == payload


@pytest.mark.parametrize("strategy,nodes", [("B2", 4), ("B2b", 9), ("B3", 9)])
def test_fixture_graph_uses_finite_real_langgraph_nodes_and_explicit_responsibility_calls(
    strategy, nodes
):
    calls = []

    def execute(role, state):
        calls.append(role)
        return state

    graph = build_investigation_graph(strategy, execute, InMemorySaver(serde=PlainJsonSerializer()))
    graph.invoke(_initial_state("a" * 64), {"configurable": {"thread_id": "fixture-only"}})
    assert calls == list(AgentRole)
    assert len([name for name in graph.get_graph().nodes if not name.startswith("__")]) == nodes


def test_fixture_graph_stops_on_waiting_approval_without_unexecuted_role_claims():
    calls = []

    def execute(role, state):
        calls.append(role)
        return {**state, "status": "waiting_approval", "stop_reason": "permission_required"}

    graph = build_investigation_graph("B2b", execute, InMemorySaver(serde=PlainJsonSerializer()))
    result = graph.invoke(_initial_state("b" * 64), {"configurable": {"thread_id": "fixture-only"}})
    assert result["status"] == "waiting_approval" and calls == [AgentRole.ORCHESTRATOR]


def test_fixture_checkpoint_interrupt_resumes_remaining_roles_without_replaying_tools():
    calls = []

    def execute(role, state):
        calls.append(role)
        return state

    graph = build_investigation_graph("B2b", execute, InMemorySaver(serde=PlainJsonSerializer()))
    config = {"configurable": {"thread_id": "fixture-restart"}}
    graph.invoke(_initial_state("c" * 64), config, interrupt_after=("triage",), durability="sync")
    assert calls == list(AgentRole)[:3]
    assert graph.get_state(config).next == ("enricher",)
    graph.invoke(None, config, durability="sync")
    assert calls == list(AgentRole)


def test_remote_tracing_environment_and_ambient_callback_are_disabled(monkeypatch):
    from langchain_core.tracers.context import tracing_v2_callback_var
    from langsmith.utils import tracing_is_enabled

    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    with local_graph_execution():
        assert tracing_is_enabled() is False
        assert tracing_v2_callback_var.get() is None


def test_counterfactual_criticality_does_not_mutate_unknown_or_conflict():
    left = ConfigurationEquals(
        node_id="known", kind="configuration_equals", field="trust_remote_code", expected=True
    )
    right = ConfigurationEquals(
        node_id="missing",
        kind="configuration_equals",
        field="authentication_required",
        expected=True,
    )
    condition = AllOf(node_id="root", kind="all_of", children=(left, right))
    for state in [ConditionValue.UNKNOWN, ConditionValue.CONFLICT]:
        evaluation = ConditionEvaluation(
            node_id="root",
            value=ConditionValue.FALSE,
            reason_code="all_of",
            child_results=(
                ConditionEvaluation(
                    node_id="known", value=ConditionValue.FALSE, reason_code="fixture_false"
                ),
                ConditionEvaluation(node_id="missing", value=state, reason_code="fixture_missing"),
            ),
        )
        original = evaluation.model_dump_json()
        assert decision_relevant_requirement(condition, evaluation, "missing") is False
        assert evaluation.model_dump_json() == original
        decisive = evaluation.model_copy(
            update={
                "child_results": (
                    evaluation.child_results[0].model_copy(update={"value": ConditionValue.TRUE}),
                    evaluation.child_results[1],
                )
            }
        )
        assert decision_relevant_requirement(condition, decisive, "missing") is True
    assert decision_relevant_requirement(condition, evaluation, "unavailable_node") is True


def test_configuration_hash_covers_budget_strategy_and_model_without_order_sensitivity():
    original = {"strategy": "B2", "model": "approved", "budget": 3}
    assert configuration_digest(original) == configuration_digest(dict(reversed(original.items())))
    for field in original:
        assert configuration_digest(original) != configuration_digest(
            {**original, field: "changed"}
        )


@pytest.mark.parametrize(
    "schema", ["public", "other_tenant", "test_r14_workflow_x;DROP SCHEMA public", "../private"]
)
def test_checkpoint_setup_scope_rejects_arbitrary_namespace(schema):
    with pytest.raises(ValueError):
        validate_checkpoint_schema(schema)
