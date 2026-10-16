"""Actual LangGraph roles use the real gateway with explicitly isolated offline IO fixtures."""

from collections import deque
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from ai_intel.api.knowledge_contracts import EventDetailResponse, EventSummary
from ai_intel.assets.inventory_contracts import AssetSnapshotResponse
from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from ai_intel.domain.enums import ToolStatus
from ai_intel.investigation import workflow_service
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.graph import build_investigation_graph
from ai_intel.investigation.graph_contracts import InvestigationRequest, WorkflowBudget
from ai_intel.investigation.read_adapters import READ_TOOLS, ReadToolOutcome
from ai_intel.investigation.tool_contracts import (
    ChangesPage,
    ChangeSummary,
    FindChangesCall,
    GetAdvisoryCall,
    GetInventoryCall,
)
from ai_intel.investigation.workflow_service import _initial_state, _WorkflowRuntime
from ai_intel.workers.executor import JobExecutionContext

NOW = datetime(2026, 10, 16, tzinfo=UTC)


@pytest.fixture
def consumer_fixture(monkeypatch):
    request = InvestigationRequest(
        question="explicit fixture question",
        event_id=uuid4(),
        evidence_refs=(),
        asset_id=uuid4(),
        asset_snapshot_id=uuid4(),
    )
    connection = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    actor = object()
    runtime = _WorkflowRuntime(
        SimpleNamespace(data_mode="fixture", model_factory=None),
        connection,
        JobExecutionContext(str(uuid4()), "fixture-consumer", 1, "fixture-owner"),
    )
    runtime.input_sha256 = "a" * 64
    runtime.scope = AccessScope.for_authenticated_user(
        "fixture-user", "fixture-owner", Role.ANALYST
    )
    runtime.actor_reference = actor
    runtime.request = request
    runtime.budget = WorkflowBudget()
    runtime.deadline = datetime.now(UTC) + timedelta(seconds=90)
    advisory = EventDetailResponse(
        event=EventSummary(
            event_id=request.event_id,
            event_type="fixture",
            title="fixture advisory",
            external_ids=(),
            primary_product_ids=(),
            first_seen_at=NOW,
            status="active",
            source_count=0,
            latest_revision_id=None,
            freshness="unknown",
        ),
        dimensions=(),
        revisions=(),
        claims=(),
        data_mode="fixture",
    )
    inventory = AssetSnapshotResponse(
        schema_version="r11-asset-candidate-1",
        snapshot_id=str(request.asset_snapshot_id),
        asset_id=str(request.asset_id),
        tenant_id="fixture-owner",
        snapshot_number=1,
        observed_at=NOW,
        recorded_at=NOW,
        source_kind="fixture",
        inventory_completeness="unknown",
        declared_scope=(),
        components=(),
        configuration=(),
        tool_permissions=None,
        input_channels=None,
        network_exposure=None,
        snapshot_sha256="b" * 64,
    )
    records = {}
    reservations = []
    calls = []
    pages = deque([ChangesPage(event_id=request.event_id, items=(), data_mode="fixture")])
    errors = {}
    status = {}
    constructors = []

    class FixtureAdapter:
        data_mode = "fixture"
        configured_tools = READ_TOOLS

        def __init__(self, connected, authenticated, mode):
            constructors.append((connected, authenticated, mode))

        def read_tool(self, principal, scope, call, deadline_monotonic):
            calls.append((scope, call))
            if call.tool_name in errors:
                raise errors[call.tool_name]
            if isinstance(call, GetAdvisoryCall):
                result = advisory
            elif isinstance(call, GetInventoryCall):
                result = inventory
            else:
                assert isinstance(call, FindChangesCall)
                result = pages.popleft()
            return ReadToolOutcome(
                result, status.get(call.tool_name, ToolStatus.SUCCEEDED), None, NOW, ()
            )

    def reserve(key, kind, role, raw, **values):
        if (
            sum(item[2].get("tool_calls", 0) for item in reservations) + values.get("tool_calls", 0)
            > runtime.budget.max_tool_calls
        ):
            return "budget_exhausted"
        reservations.append((key, kind, values))
        return None

    def complete(key, output, status="succeeded"):
        records[key] = output

    @contextmanager
    def transaction():
        yield None

    def fixture_graph(self, event_id):
        self.input_sha256 = "c" * 64
        return SimpleNamespace(edges=())

    monkeypatch.setattr(workflow_service, "PostgresReadToolAdapter", FixtureAdapter, raising=False)
    monkeypatch.setattr(runtime, "guard", lambda **kwargs: None)
    monkeypatch.setattr(runtime, "lookup", records.get)
    monkeypatch.setattr(runtime, "reserve", reserve)
    monkeypatch.setattr(runtime, "complete_operation", complete)
    monkeypatch.setattr(runtime, "transaction", transaction)
    monkeypatch.setattr(
        workflow_service.KnowledgeReadService, "event_detail", lambda self, event_id: advisory
    )
    monkeypatch.setattr(workflow_service.EvidenceGraphReadService, "event_graph", fixture_graph)
    return SimpleNamespace(
        runtime=runtime,
        calls=calls,
        pages=pages,
        errors=errors,
        status=status,
        records=records,
        reservations=reservations,
        constructors=constructors,
        connection=connection,
        actor=actor,
    )


@pytest.mark.parametrize("strategy", ["B2", "B2b", "B3"])
def test_real_graph_consumes_all_three_typed_reads_without_claiming_finished_duties(
    consumer_fixture, strategy
):
    fixture = consumer_fixture
    runtime = fixture.runtime
    runtime.request = runtime.request.model_copy(update={"strategy": strategy})
    graph = build_investigation_graph(strategy, runtime.run_role, InMemorySaver())
    result = graph.invoke(
        _initial_state(runtime.input_sha256), {"configurable": {"thread_id": "fixture-consumer"}}
    )
    assert [type(call) for _, call in fixture.calls] == [
        GetAdvisoryCall,
        GetInventoryCall,
        FindChangesCall,
    ]
    assert fixture.constructors == [(fixture.connection, fixture.actor, "fixture")] * 3
    advisory, inventory, changes = [
        fixture.records[key] for key, kind, _ in fixture.reservations if kind == "tool"
    ]
    assert advisory["data"]["event"]["event_id"] == str(runtime.request.event_id)
    assert inventory["data"]["snapshot_id"] == str(runtime.request.asset_snapshot_id)
    assert inventory["data"]["snapshot_sha256"] == "b" * 64
    assert changes["data"]["data_mode"] == "fixture"
    assert all(item["is_synthetic"] for item in [advisory, inventory, changes])
    assert result["evidence"] == [] and result["draft"] is None
    receipts = {item["role"]: item for item in result["receipts"]}
    assert receipts["collector"]["reason_code"] == "collection_adapter_not_configured"
    assert receipts["collector"]["status"] == "partial"
    assert receipts["assessor"]["reason_code"] == "assessment_adapter_not_configured"
    assert receipts["assessor"]["status"] == "partial"
    assert receipts["reporter"]["output"]["changes_complete"] is True
    assert receipts["reporter"]["status"] == "partial"
    assert result["status"] == "partial"


def test_reporter_consumes_continuation_before_marking_event_changes_complete(consumer_fixture):
    fixture = consumer_fixture
    fixture.pages.clear()
    change = ChangeSummary(
        change_id=uuid4(), change_type="knowledge_published", knowledge_epoch=2, recorded_at=NOW
    )
    fixture.pages.extend(
        [
            ChangesPage(
                event_id=fixture.runtime.request.event_id,
                items=(change,),
                next_cursor="fixture-next",
                data_mode="fixture",
            ),
            ChangesPage(event_id=fixture.runtime.request.event_id, items=(), data_mode="fixture"),
        ]
    )
    state = fixture.runtime.run_role(AgentRole.REPORTER, _initial_state("a" * 64))
    output = state["receipts"][-1]["output"]
    assert [call.arguments.cursor for _, call in fixture.calls] == [None, "fixture-next"]
    assert all(call.arguments.limit == 25 for _, call in fixture.calls)
    assert output["changes_complete"] is True
    assert len(output["changes_pages"]) == 2
    assert output["changes_pages"][0]["data"]["items"][0]["knowledge_epoch"] == 2
    assert output["changes_next_cursor"] is None
    assert state["status"] == "partial" and state["draft"] is None


def test_reporter_budget_exhaustion_retains_cursor_and_never_claims_empty_global_result(
    consumer_fixture,
):
    fixture = consumer_fixture
    fixture.runtime.budget = WorkflowBudget(max_tool_calls=1)
    fixture.pages.clear()
    fixture.pages.append(
        ChangesPage(
            event_id=fixture.runtime.request.event_id,
            items=(),
            next_cursor="fixture-unread",
            data_mode="fixture",
        )
    )
    state = fixture.runtime.run_role(AgentRole.REPORTER, _initial_state("a" * 64))
    output = state["receipts"][-1]["output"]
    assert len(fixture.calls) == 1
    assert output["changes_complete"] is False and output["changes_next_cursor"] == "fixture-unread"
    assert state["receipts"][-1]["reason_code"] == "budget_exhausted"
    assert state["stop_reason"] == "budget_exhausted"


@pytest.mark.parametrize(
    "role,tool",
    [
        (AgentRole.COLLECTOR, "get_advisory"),
        (AgentRole.ASSESSOR, "get_inventory"),
        (AgentRole.REPORTER, "find_changes"),
    ],
)
def test_read_denial_stops_graph_and_keeps_actual_error(consumer_fixture, role, tool):
    fixture = consumer_fixture
    fixture.errors[tool] = PermissionDeniedError("fixture revoked")
    state = fixture.runtime.run_role(role, _initial_state("a" * 64))
    assert state["status"] == "waiting_approval" and state["stop_reason"] == "permission_required"
    result = next(value for key, value in fixture.records.items() if key.startswith("tool:"))
    assert result["status"] == "denied" and result["error_code"] == "resource_unavailable"
    assert result["data"] is None


@pytest.mark.parametrize("role", [AgentRole.COLLECTOR, AgentRole.ASSESSOR, AgentRole.REPORTER])
def test_role_receipt_replay_does_not_reserve_or_read_again(consumer_fixture, role):
    fixture = consumer_fixture
    initial = _initial_state("a" * 64)
    original = fixture.runtime.run_role(role, initial)
    reservations, calls = len(fixture.reservations), len(fixture.calls)
    assert fixture.runtime.run_role(role, initial) == original
    assert len(fixture.reservations) == reservations and len(fixture.calls) == calls == 1


@pytest.mark.parametrize(
    "reason",
    [
        "critical_conflict",
        "operation_outcome_unknown",
        "model_outcome_unknown",
        "deadline_exhausted",
        "budget_exhausted",
    ],
)
def test_reporter_does_not_read_after_unresolved_stop(consumer_fixture, reason):
    fixture = consumer_fixture
    state = {**_initial_state("a" * 64), "stop_reason": reason}
    output = fixture.runtime.run_role(AgentRole.REPORTER, state)
    assert fixture.calls == [] and output["stop_reason"] == reason


def test_cancel_or_lost_authority_prevents_reservation_and_read(consumer_fixture, monkeypatch):
    fixture = consumer_fixture

    def denied(**kwargs):
        raise PermissionDeniedError("fixture cancelled or revoked")

    monkeypatch.setattr(fixture.runtime, "guard", denied)
    with pytest.raises(PermissionDeniedError):
        fixture.runtime.run_role(AgentRole.COLLECTOR, _initial_state("a" * 64))
    assert fixture.reservations == [] and fixture.calls == []


@pytest.mark.parametrize("status", [ToolStatus.PARTIAL, ToolStatus.NO_RESULT])
def test_changes_empty_page_retains_tool_status_and_completeness_semantics(
    consumer_fixture, status
):
    fixture = consumer_fixture
    fixture.status["find_changes"] = status
    fixture.pages.clear()
    fixture.pages.append(
        ChangesPage(
            event_id=fixture.runtime.request.event_id,
            items=(),
            next_cursor="fixture-partial" if status == ToolStatus.PARTIAL else None,
            data_mode="fixture",
        )
    )
    result = fixture.runtime.run_role(AgentRole.REPORTER, _initial_state("a" * 64))
    output = result["receipts"][-1]["output"]
    assert output["changes_pages"][0]["status"] == status.value
    assert output["changes_complete"] is (status == ToolStatus.NO_RESULT)
    assert output["changes_next_cursor"] == (
        "fixture-partial" if status == ToolStatus.PARTIAL else None
    )
    assert result["status"] == "partial" and result["draft"] is None


def test_repeated_changes_cursor_stops_finitely_with_incomplete_receipt(consumer_fixture):
    fixture = consumer_fixture
    fixture.pages.clear()
    fixture.pages.extend(
        [
            ChangesPage(
                event_id=fixture.runtime.request.event_id,
                items=(),
                next_cursor="fixture-repeated",
                data_mode="fixture",
            )
        ]
        * 2
    )
    result = fixture.runtime.run_role(AgentRole.REPORTER, _initial_state("a" * 64))
    receipt = result["receipts"][-1]
    assert len(fixture.calls) == 2 and receipt["output"]["changes_complete"] is False
    assert receipt["reason_code"] == "changes_continuation_invalid"


def test_interrupted_node_reuses_completed_read_without_new_tool_reservation(consumer_fixture):
    fixture = consumer_fixture
    initial = _initial_state("a" * 64)
    first = fixture.runtime.run_role(AgentRole.COLLECTOR, initial)
    fixture.records["node:collector"] = {"error_code": "operation_outcome_unknown"}
    before = len(fixture.reservations)
    replay = fixture.runtime.run_role(AgentRole.COLLECTOR, initial)
    assert replay == first and len(fixture.calls) == 1
    assert len(fixture.reservations) == before


def test_unknown_reserved_read_is_not_repeated_or_forged_into_success(consumer_fixture):
    fixture = consumer_fixture
    fixture.records["tool:collector:get_advisory"] = {"error_code": "operation_outcome_unknown"}
    result = fixture.runtime.run_role(AgentRole.COLLECTOR, _initial_state("a" * 64))
    assert fixture.calls == []
    assert result["receipts"][-1]["output"]["advisory"] is None
    assert result["receipts"][-1]["reason_code"] == "operation_outcome_unknown"


def test_inventory_output_limit_is_recorded_without_fabricating_assessment(consumer_fixture):
    fixture = consumer_fixture
    fixture.runtime.budget = WorkflowBudget(tool_result_bytes=1024)
    result = fixture.runtime.run_role(AgentRole.ASSESSOR, _initial_state("a" * 64))
    inventory = result["receipts"][-1]["output"]["inventory"]
    assert inventory["status"] == "partial" and inventory["error_code"] == "output_limit"
    assert inventory["data"] is None and result["receipts"][-1]["status"] == "partial"


def test_reporter_preserves_budget_stop_even_when_answer_was_verified(consumer_fixture):
    fixture = consumer_fixture
    fixture.runtime.budget = WorkflowBudget(max_tool_calls=1)
    fixture.pages.clear()
    fixture.pages.append(
        ChangesPage(
            event_id=fixture.runtime.request.event_id,
            items=(),
            next_cursor="fixture-unread",
            data_mode="fixture",
        )
    )
    state = {**_initial_state("a" * 64), "verified": True}
    result = fixture.runtime.run_role(AgentRole.REPORTER, state)
    assert result["stop_reason"] == "budget_exhausted"
    assert result["receipts"][-1]["output"]["changes_complete"] is False


@pytest.mark.parametrize(
    "status", ["succeeded", "partial", "failed", "waiting_approval", "cancelled"]
)
def test_configuration_stale_terminal_job_preserves_history_without_new_io(
    consumer_fixture, status
):
    fixture = consumer_fixture
    fixture.runtime.job_status = status
    fixture.runtime.finish_stale()
    assert fixture.reservations == [] and fixture.calls == []
