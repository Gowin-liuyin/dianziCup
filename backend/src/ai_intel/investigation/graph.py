"""Finite LangGraph B2/B2b/B3 workflows call distinct server-owned responsibilities."""

from collections.abc import Callable

from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ai_intel.investigation.capabilities import B2_ROLE_MAP, AgentRole
from ai_intel.investigation.graph_contracts import Strategy, WorkflowState

RoleExecutor = Callable[[AgentRole, WorkflowState], WorkflowState]
UNKNOWN_OPERATION_REASONS = ("model_outcome_unknown", "operation_outcome_unknown")


def get_unknown_operation_reason(state: WorkflowState) -> str | None:
    """Persisted unknown outcomes stop further work even when an earlier gap occupied state."""
    for reason in UNKNOWN_OPERATION_REASONS:
        if state["stop_reason"] == reason or any(
            receipt.get("reason_code") == reason for receipt in state["receipts"]
        ):
            return reason
    return None


def normalize_unknown_operation_state(state: WorkflowState) -> WorkflowState:
    """Stop unknown work without replacing a stronger safety outcome or a confirmed conflict."""
    reason = get_unknown_operation_reason(state)
    if reason is None or state["status"] in {"failed", "waiting_approval", "stale"}:
        return state
    if state["stop_reason"] == "critical_conflict":
        return {**state, "status": "partial"}
    return {**state, "status": "partial", "stop_reason": reason, "verified": False}


def build_investigation_graph(
    strategy: Strategy,
    execute_role: RoleExecutor,
    checkpointer: BaseCheckpointSaver,
) -> CompiledStateGraph[WorkflowState, None, WorkflowState, WorkflowState]:
    """Strategies share executors and budgets; B3 changes only the planner's candidate choice."""
    builder = StateGraph(WorkflowState)
    groups = (
        tuple(B2_ROLE_MAP.items())
        if strategy == "B2"
        else tuple((role.value, (role,)) for role in AgentRole)
    )

    def stage(roles: tuple[AgentRole, ...]) -> Callable[[WorkflowState], WorkflowState]:
        def execute(state: WorkflowState) -> WorkflowState:
            for role in roles:
                unknown_reason = get_unknown_operation_reason(state)
                if unknown_reason is not None:
                    return normalize_unknown_operation_state(state)
                state = execute_role(role, state)
                if state["status"] in {"failed", "waiting_approval", "stale"}:
                    break
            return state

        return execute

    for name, roles in groups:
        builder.add_node(name, RunnableLambda(stage(roles)))
    builder.add_edge(START, groups[0][0])
    for index, (name, _) in enumerate(groups):
        next_node = groups[index + 1][0] if index + 1 < len(groups) else END

        def route(state: WorkflowState, successor: str = next_node) -> str:
            stopped = state["status"] in {"failed", "waiting_approval", "stale"}
            return END if stopped or get_unknown_operation_reason(state) is not None else successor

        builder.add_conditional_edges(name, route, {END: END, next_node: next_node})
    return builder.compile(checkpointer=checkpointer, name="r14-investigation")
