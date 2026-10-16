"""Explicit offline IO fixtures exercise real role and shared completion boundaries."""

import copy
import json
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.exc import DBAPIError
from test_r07_source_report_reader import read_case
from test_r14_shared_read_consumers import consumer_fixture

from ai_intel.api.credentials import SessionCredential
from ai_intel.domain.access import CrossTenantAccessError
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.models.generation import (
    AttemptMetadata,
    GenerationClient,
    GenerationFailure,
    GenerationRequest,
    TokenUsage,
)
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.investigation import runtime as factory_module
from ai_intel.investigation import workflow_service as module
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.graph import OUTPUT_BUDGET_FAILURE, build_investigation_graph
from ai_intel.investigation.graph_contracts import (
    InvestigationRequest,
    PlannerDecision,
    WorkflowBudget,
)
from ai_intel.investigation.tool_contracts import (
    GetAdvisoryArguments,
    GetAdvisoryCall,
    ReadEvidenceArguments,
)
from ai_intel.investigation.workflow_service import _initial_state, _WorkflowRuntime
from ai_intel.knowledge.structured_fact_proofs import (
    StructuredFactProofChangedError,
    StructuredFactProofRead,
    StructuredFactProofReader,
    StructuredFactProofRequest,
)
from ai_intel.workers.executor import JobExecutionContext
from ai_intel.workers.jobs import JobLeaseLostError

__all__ = ["consumer_fixture", "read_case"]


def reserved_row(key, size=52, kind="node"):
    return {
        "operation_key": key,
        "status": "reserved",
        "output_bytes": size,
        "output_json": None,
        "kind": kind,
        "input_bytes": 0,
        "model_calls": int(kind == "model"),
        "tool_calls": int(kind == "tool"),
    }


@pytest.fixture
def accounting_fixture(monkeypatch):
    runtime = _WorkflowRuntime(
        SimpleNamespace(_model_config={"model_version": None}),
        SimpleNamespace(exec_driver_sql=lambda value: None),
        JobExecutionContext(str(uuid4()), "explicit-fixture", 1, None),
    )
    runtime.budget = WorkflowBudget(max_output_bytes=1024)
    runtime.deadline = datetime.now(UTC) + timedelta(seconds=30)
    runtime.input_sha256 = "a" * 64
    rows = []
    statements = []

    class Session:
        def execute(self, statement):
            statements.append(statement)
            parameters = statement.compile().params
            if statement.is_update:
                row = next(
                    row for row in rows if row["operation_key"] == parameters["operation_key_1"]
                )
                row.update({key: parameters[key] for key in ("status", "output_json")})
            elif statement.is_insert:
                rows.append({key: parameters.get(key) for key in reserved_row("")})

    @contextmanager
    def transaction():
        yield Session()

    monkeypatch.setattr(runtime, "transaction", transaction)
    monkeypatch.setattr(runtime, "guard", lambda **kwargs: None)
    monkeypatch.setattr(runtime, "guard_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime, "operation_rows", lambda session: rows)
    monkeypatch.setattr(module, "renew_lease", lambda *args, **kwargs: None)
    return SimpleNamespace(runtime=runtime, rows=rows, statements=statements)


def test_frozen_encoding_counts_real_chinese_utf8_bytes():
    assert module._output_json_bytes({"值": "中文"}) == len('{"值":"中文"}'.encode())
    assert module._output_json_bytes({"z": 1, "值": "中文"}) == 22
    with pytest.raises(ValueError):
        module._output_json_bytes({"bad": float("nan")})


@pytest.mark.parametrize("kind", ["node", "tool", "model"])
def test_completion_counts_candidate_actual_and_retains_other_pending_reservation(
    accounting_fixture, kind
):
    fixture = accounting_fixture
    fixture.rows.extend([reserved_row("current", kind=kind), reserved_row("pending", 900, "model")])
    rejected = {"value": "中" * 50}
    assert module._output_json_bytes(rejected) > 124
    assert fixture.runtime.complete_operation("current", rejected) == OUTPUT_BUDGET_FAILURE
    assert fixture.rows[0]["output_json"] == {"error_code": OUTPUT_BUDGET_FAILURE}
    assert fixture.rows[0]["status"] == "failed"
    assert fixture.rows[1] == reserved_row("pending", 900, "model")
    assert rejected == {"value": "中" * 50}
    assert fixture.rows[0]["output_bytes"] == 52


def test_completed_actual_usage_replaces_original_reservation_in_next_reserve(accounting_fixture):
    fixture = accounting_fixture
    fixture.rows.append(reserved_row("finished", 1024, "model"))
    assert fixture.runtime.complete_operation("finished", {"value": "中"}) is None
    assert (
        fixture.runtime.reserve("node:qa", "node", AgentRole.QA, b"fixture", input_bytes=0) is None
    )
    assert fixture.rows[-1]["output_bytes"] == module.OUTPUT_BUDGET_FAILURE_BYTES
    assert fixture.rows[0]["output_bytes"] == 1024


def test_next_reserve_counts_cumulative_completed_bytes_instead_of_small_node_slots(
    accounting_fixture,
):
    fixture = accounting_fixture
    fixture.rows.append(reserved_row("finished"))
    assert fixture.runtime.complete_operation("finished", {"value": "中" * 320}) is None
    assert (
        fixture.runtime.reserve("node:qa", "node", AgentRole.QA, b"fixture", output_bytes=100)
        == "budget_exhausted"
    )
    assert len(fixture.rows) == 1


def test_rejection_receipt_is_immutable_and_no_second_output_is_returned(accounting_fixture):
    fixture = accounting_fixture
    fixture.rows.append(reserved_row("current"))
    assert (
        fixture.runtime.complete_operation("current", {"report": "secret fixture" * 100})
        == OUTPUT_BUDGET_FAILURE
    )
    saved = copy.deepcopy(fixture.rows)
    assert fixture.runtime.complete_operation("current", {"value": "new"}) == OUTPUT_BUDGET_FAILURE
    assert fixture.rows == saved
    with pytest.raises(ValueError, match="operation_reservation_missing"):
        fixture.runtime.complete_operation("absent", {"value": "new"})


def test_finished_success_does_not_accept_a_different_unsaved_value(accounting_fixture):
    fixture = accounting_fixture
    fixture.rows.append(reserved_row("current"))
    assert fixture.runtime.complete_operation("current", {"value": "same"}) is None
    assert fixture.runtime.complete_operation("current", {"value": "same"}) is None
    with pytest.raises(ValueError, match="already_completed"):
        fixture.runtime.complete_operation("current", {"value": "different"})


def test_node_cannot_start_io_without_fixed_failure_capacity(accounting_fixture, monkeypatch):
    fixture = accounting_fixture
    fixture.rows.append(
        {**reserved_row("done"), "status": "succeeded", "output_json": {"value": "a" * 970}}
    )
    monkeypatch.setattr(fixture.runtime, "lookup", lambda key: None)
    monkeypatch.setattr(
        fixture.runtime, "tool", lambda *args: pytest.fail("IO after failure slot exhausted")
    )
    state = fixture.runtime.run_role(AgentRole.COLLECTOR, _initial_state("a" * 64))
    assert state["stop_reason"] == OUTPUT_BUDGET_FAILURE
    assert state["receipts"] == [] and len(fixture.rows) == 1


@pytest.mark.parametrize("strategy", ["B2", "B2b", "B3"])
def test_rejected_large_node_is_absent_from_return_and_checkpoint(
    consumer_fixture, monkeypatch, strategy
):
    fixture = consumer_fixture
    saver = InMemorySaver()
    failed = []

    def reject(key, output, status="succeeded"):
        if key.startswith("node:"):
            failed.append(key)
            fixture.records[key] = {"error_code": OUTPUT_BUDGET_FAILURE}
            return OUTPUT_BUDGET_FAILURE
        fixture.records[key] = output

    monkeypatch.setattr(fixture.runtime, "complete_operation", reject)
    graph = build_investigation_graph(strategy, fixture.runtime.run_role, saver)
    config = {"configurable": {"thread_id": "explicit-budget-fixture"}}
    state = graph.invoke(_initial_state("a" * 64), config)
    assert failed == ["node:orchestrator"]
    assert state["stop_reason"] == OUTPUT_BUDGET_FAILURE
    assert state["receipts"] == [] and state["draft"] is None and not state["verified"]
    assert graph.get_state(config).values == state
    assert not fixture.calls
    replay = fixture.runtime.run_role(AgentRole.ORCHESTRATOR, _initial_state("a" * 64))
    assert replay == state and len(failed) == 1


def test_tool_output_rejected_at_completion_is_never_returned(consumer_fixture, monkeypatch):
    fixture = consumer_fixture
    monkeypatch.setattr(fixture.runtime, "complete_operation", lambda *args: OUTPUT_BUDGET_FAILURE)
    call = GetAdvisoryCall(
        tool_name="get_advisory",
        arguments=GetAdvisoryArguments(event_id=fixture.runtime.request.event_id),
        goal_id=uuid4(),
    )
    assert fixture.runtime.tool(AgentRole.COLLECTOR, call, "tool:fixture") is None
    assert fixture.runtime.last_operation_error == OUTPUT_BUDGET_FAILURE
    fixture.records["tool:prior"] = {"error_code": OUTPUT_BUDGET_FAILURE}
    fixture.runtime.last_operation_error = None
    assert fixture.runtime.tool(AgentRole.COLLECTOR, call, "tool:prior") is None
    assert fixture.runtime.last_operation_error == OUTPUT_BUDGET_FAILURE


def test_pg_budget_failure_recovery_precedes_unknown_and_old_verified_state(
    consumer_fixture, monkeypatch
):
    fixture = consumer_fixture
    fixture.runtime.service._operation_output_accounting_version = (
        module.OPERATION_OUTPUT_ACCOUNTING_VERSION
    )

    @contextmanager
    def transaction():
        yield SimpleNamespace(scalar=lambda statement: "model:qa")

    monkeypatch.setattr(fixture.runtime, "transaction", transaction)
    incoming = {
        **_initial_state("a" * 64),
        "stop_reason": "model_outcome_unknown",
        "verified": True,
        "draft": {"rejected": "中" * 3000},
        "evidence": [{"rejected": "large"}],
    }
    restored = fixture.runtime.restore_node_state(incoming)
    assert restored["stop_reason"] == OUTPUT_BUDGET_FAILURE
    assert restored["draft"] is None and restored["evidence"] == [] and restored["receipts"] == []
    assert not restored["verified"]
    assert incoming["verified"]


def test_default_factory_injects_only_configured_storage_without_external_calls(tmp_path):
    engine = create_engine("postgresql+psycopg://fixture@127.0.0.1/test_dianzi_fixture")
    settings = ApplicationSettings(
        app_env="test", data_mode="fixture", raw_content_directory=str(tmp_path)
    )
    service = factory_module.build_investigation_service(
        engine, settings, SessionCredential(SecretStr("fixture-session"))
    )
    assert isinstance(service._content_store, ContentStore)
    assert service._source_report_consumer_version == module.SOURCE_REPORT_CONSUMER_VERSION
    assert (
        service._operation_output_accounting_version == module.OPERATION_OUTPUT_ACCOUNTING_VERSION
    )
    assert service.model_factory is None
    direct = module.InvestigationWorkflowService(
        engine,
        SessionCredential(SecretStr("fixture-session")),
        "unused",
        "test_r14_workflow_fixture",
        data_mode="fixture",
    )
    assert (
        direct._content_store is None and direct._source_report_consumer_version == "not_configured"
    )
    engine.dispose()


@pytest.mark.parametrize(
    "status,reason",
    [
        ("reported", "enrichment_write_adapter_not_configured"),
        ("partial", "source_reports_partial"),
        ("not_found", "source_reports_not_found"),
    ],
)
def test_enricher_consumes_existing_source_reader_with_authenticated_idle_context(
    consumer_fixture, read_case, monkeypatch, status, reason
):
    fixture = consumer_fixture
    fixture.runtime.request = InvestigationRequest(
        question="fixture report",
        event_id=read_case.request.event_id,
        evidence_refs=(ReadEvidenceArguments(**read_case.request.model_dump()),),
    )
    fixture.runtime.connection = read_case.connection
    fixture.runtime.actor_reference = read_case.actor
    fixture.runtime.scope = read_case.scope
    fixture.runtime.service._content_store = read_case.store
    if status == "partial":
        read_case.store.read_verified.side_effect = FileNotFoundError("explicit fixture absent")
    if status == "not_found":
        monkeypatch.setattr(
            read_case.reader,
            "_read_inputs",
            lambda *args: replace(read_case.snapshot, claim_rows=()),
        )
    arguments = []

    def reader_factory(*args):
        arguments.append(args)
        return read_case.reader

    monkeypatch.setattr(module, "build_source_report_reader", reader_factory)
    state = fixture.runtime.run_role(AgentRole.ENRICHER, _initial_state("a" * 64))
    receipt = state["receipts"][-1]
    assert arguments == [
        (read_case.connection, read_case.actor, read_case.scope, read_case.store, "fixture")
    ]
    assert receipt["reason_code"] == reason and receipt["status"] == "partial"
    output = receipt["output"]
    assert output["source_report_read_status"] == status
    report = output["source_reports"][0]
    assert report["status"] == status
    if status != "not_found":
        fact = report["facts"][0]
        assert fact["record"]["condition_value"] == "unknown"
        assert fact["record"]["freshness"] == "unknown"
        assert fact["record"]["claim_origin"] == "structured_source"
    assert state["evidence"] == [] and state["draft"] is None and not state["verified"]


def test_eight_report_references_share_one_deadline_and_keep_all_sixtyfour_facts(
    consumer_fixture, read_case, monkeypatch
):
    fixture = consumer_fixture
    read_case.store.read_verified.side_effect = FileNotFoundError("fixture absent")
    partial = read_case.reader.read(read_case.request, module.time.monotonic() + 4)
    references = tuple(
        ReadEvidenceArguments(
            event_id=read_case.request.event_id,
            evidence_id=uuid4(),
            revision_id=read_case.request.revision_id,
        )
        for _ in range(8)
    )
    fixture.runtime.request = InvestigationRequest(
        question="fixture reports", event_id=read_case.request.event_id, evidence_refs=references
    )
    fixture.runtime.service._content_store = read_case.store
    reader = Mock(spec=StructuredFactProofReader)
    reader.read.side_effect = tuple(
        StructuredFactProofRead(
            request=StructuredFactProofRequest(**reference.model_dump()),
            status="partial",
            facts=partial.facts * 8,
            input_sha256="b" * 64,
            data_mode="fixture",
        )
        for reference in references
    )
    monkeypatch.setattr(module, "build_source_report_reader", lambda *args: reader)
    monkeypatch.setattr(fixture.runtime, "remaining_seconds", lambda: 2.0)
    started = module.time.monotonic()
    state = fixture.runtime.run_role(AgentRole.ENRICHER, _initial_state("a" * 64))
    reports = state["receipts"][-1]["output"]["source_reports"]
    assert len(reports) == 8 and sum(len(report["facts"]) for report in reports) == 64
    deadlines = [call.args[1] for call in reader.read.call_args_list]
    assert len(set(deadlines)) == 1 and started < deadlines[0] <= module.time.monotonic() + 2


@pytest.mark.parametrize(
    "failure",
    [
        TimeoutError("fixture timeout"),
        CrossTenantAccessError("fixture acl"),
        StructuredFactProofChangedError("fixture epoch"),
        JobLeaseLostError("fixture lease"),
    ],
)
def test_source_report_failure_remains_distinct_and_cannot_claim_reported(
    consumer_fixture, monkeypatch, failure
):
    fixture = consumer_fixture
    request = fixture.runtime.request
    fixture.runtime.request = request.model_copy(
        update={
            "evidence_refs": (
                ReadEvidenceArguments(
                    event_id=request.event_id, evidence_id=uuid4(), revision_id=uuid4()
                ),
            )
        }
    )
    fixture.runtime.service._content_store = object()
    reader = Mock(spec=StructuredFactProofReader)
    reader.read.side_effect = failure
    monkeypatch.setattr(module, "build_source_report_reader", lambda *args: reader)
    if isinstance(failure, TimeoutError):
        state = fixture.runtime.run_role(AgentRole.ENRICHER, _initial_state("a" * 64))
        assert state["receipts"][-1]["reason_code"] == "source_report_deadline_exhausted"
        assert state["receipts"][-1]["output"]["source_reports"] == []
    else:
        expected = (
            module.WorkflowChangedError
            if isinstance(failure, StructuredFactProofChangedError)
            else type(failure)
        )
        with pytest.raises(expected):
            fixture.runtime.run_role(AgentRole.ENRICHER, _initial_state("a" * 64))
        assert not fixture.records


def test_empty_references_are_explicit_gap_without_reader_io(consumer_fixture, monkeypatch):
    fixture = consumer_fixture
    fixture.runtime.service._content_store = object()
    monkeypatch.setattr(
        module, "build_source_report_reader", lambda *args: pytest.fail("reader IO for empty refs")
    )
    state = fixture.runtime.run_role(AgentRole.ENRICHER, _initial_state("a" * 64))
    assert state["receipts"][-1]["reason_code"] == "source_report_references_missing"


def test_large_source_report_never_enters_checkpoint_after_completion_rejection(
    consumer_fixture, monkeypatch
):
    fixture = consumer_fixture
    request = fixture.runtime.request
    reference = ReadEvidenceArguments(
        event_id=request.event_id, evidence_id=uuid4(), revision_id=uuid4()
    )
    fixture.runtime.request = request.model_copy(update={"evidence_refs": (reference,)})
    fixture.runtime.service._content_store = object()
    report = StructuredFactProofRead(
        request=StructuredFactProofRequest(**reference.model_dump()),
        status="not_found",
        missing_requirements=("中" * 5000,),
        input_sha256="b" * 64,
        data_mode="fixture",
    )
    reader = Mock(spec=StructuredFactProofReader)
    reader.read.return_value = report
    monkeypatch.setattr(module, "build_source_report_reader", lambda *args: reader)
    captured = []

    def rejected(key, output, status="succeeded"):
        captured.append(module._output_json_bytes(output))
        fixture.records[key] = {"error_code": OUTPUT_BUDGET_FAILURE}
        return OUTPUT_BUDGET_FAILURE

    monkeypatch.setattr(fixture.runtime, "complete_operation", rejected)
    saver = InMemorySaver()
    graph = build_investigation_graph(
        "B2b", lambda role, state: fixture.runtime.run_role(AgentRole.ENRICHER, state), saver
    )
    config = {"configurable": {"thread_id": "fixture-large-report"}}
    state = graph.invoke(_initial_state("a" * 64), config)
    assert captured[0] > 15000
    assert state["stop_reason"] == OUTPUT_BUDGET_FAILURE and state["receipts"] == []
    for checkpoint in saver.list(config):
        assert "中" * 100 not in json.dumps(checkpoint.checkpoint, ensure_ascii=False)
    assert not fixture.runtime.result(state).answer


@pytest.mark.parametrize("path", ["success", "failure", "deadline"])
def test_all_model_completion_callers_preserve_budget_failure_without_returning_value(
    consumer_fixture, monkeypatch, path
):
    fixture = consumer_fixture
    runtime = fixture.runtime
    runtime.service._model_config = {
        "provider": "deepseek_openai",
        "model_version": "deepseek-flash",
    }
    generated = Mock()
    constructed = []

    def factory(limits):
        constructed.append(limits)
        client = Mock(spec=GenerationClient)
        client.limits = limits
        client.provider = "deepseek_openai"
        client.approved_model = "deepseek-flash"
        client.generate = generated
        if path == "deadline":
            monkeypatch.setattr(runtime, "remaining_seconds", lambda: 0.01)
        return client

    runtime.service.model_factory = factory
    now = datetime.now(UTC)
    attempt = AttemptMetadata(
        provider="deepseek_openai",
        requested_model="deepseek-flash",
        response_model="deepseek-flash",
        call_id="fixture-call",
        finish_reason="stop",
        prompt_version="fixture-1",
        schema_version="fixture-1",
        codec_version="generation-wire-1",
        prompt_sha256="a" * 64,
        schema_sha256="a" * 64,
        body_sha256="a" * 64,
        response_sha256="a" * 64,
        started_at=now,
        completed_at=now,
        elapsed_milliseconds=0,
        http_status=200,
        usage=TokenUsage(),
        outcome="succeeded",
    )
    if path == "failure":
        generated.side_effect = GenerationFailure("fixture_format_error", (attempt,))
    else:
        generated.return_value = SimpleNamespace(
            value=PlannerDecision(
                candidate_action_id="fixture-action",
                reason_code="fill_current_support",
                short_reason="fixture",
            ),
            attempts=(attempt,),
            format_repair_used=False,
        )
    completed = Mock(return_value=OUTPUT_BUDGET_FAILURE)
    monkeypatch.setattr(runtime, "complete_operation", completed)
    request = GenerationRequest(
        system_text="fixture",
        question="fixture",
        evidence_texts=(),
        prompt_version="fixture-1",
        schema_version="fixture-1",
        model_version="deepseek-flash",
        max_output_tokens=100,
    )
    assert runtime.model(AgentRole.QA, request, PlannerDecision, "model:fixture") is None
    assert runtime.last_operation_error == OUTPUT_BUDGET_FAILURE
    assert completed.call_count == 1 and len(constructed) == 1
    assert generated.call_count == (0 if path == "deadline" else 1)
    fixture.records["model:fixture"] = {"error_code": OUTPUT_BUDGET_FAILURE}
    runtime.last_operation_error = None
    assert runtime.model(AgentRole.QA, request, PlannerDecision, "model:fixture") is None
    assert runtime.last_operation_error == OUTPUT_BUDGET_FAILURE and len(constructed) == 1


def test_bounded_operation_row_load_rejects_a_twentyfourth_row(accounting_fixture):
    fixture = accounting_fixture
    rows = [reserved_row(str(index)) for index in range(module.MAX_WORKFLOW_OPERATIONS + 1)]
    statements = []

    class Session:
        def execute(self, statement):
            statements.append(statement)
            return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: rows))

    with pytest.raises(ValueError, match="operation_count_invalid"):
        _WorkflowRuntime.operation_rows(fixture.runtime, Session())
    assert statements[-1].compile().params["param_1"] == 24


def test_terminal_budget_error_without_a_new_node_slot_clears_old_verified_result(consumer_fixture):
    runtime = consumer_fixture.runtime
    runtime.job_error_code = OUTPUT_BUDGET_FAILURE
    state = {**_initial_state("a" * 64), "verified": True, "draft": {"old": "answer"}}
    restored = runtime.restore_node_state(state)
    assert restored["stop_reason"] == OUTPUT_BUDGET_FAILURE
    assert restored["draft"] is None and not restored["verified"]


def test_node_reservation_deadline_remains_distinct_from_output_budget(
    consumer_fixture, monkeypatch
):
    runtime = consumer_fixture.runtime
    monkeypatch.setattr(runtime, "reserve", lambda *args, **kwargs: "deadline_exhausted")
    state = runtime.run_role(AgentRole.COLLECTOR, _initial_state("a" * 64))
    assert state["stop_reason"] == "deadline_exhausted"
    assert not consumer_fixture.calls and not consumer_fixture.records


@pytest.mark.parametrize("sqlstate", ["57014", "55P03", "08006"])
def test_source_pg_statement_and_lock_timeout_remain_distinct_from_database_failure(
    consumer_fixture, monkeypatch, sqlstate
):
    fixture = consumer_fixture
    request = fixture.runtime.request
    reference = ReadEvidenceArguments(
        event_id=request.event_id, evidence_id=uuid4(), revision_id=uuid4()
    )
    fixture.runtime.request = request.model_copy(update={"evidence_refs": (reference,)})
    fixture.runtime.service._content_store = object()

    class DatabaseFailure(Exception):
        pass

    original = DatabaseFailure("explicit fixture database error")
    original.sqlstate = sqlstate
    reader = Mock(spec=StructuredFactProofReader)
    failure = DBAPIError(None, None, original)
    reader.read.side_effect = failure
    monkeypatch.setattr(module, "build_source_report_reader", lambda *args: reader)
    if sqlstate in {"57014", "55P03"}:
        state = fixture.runtime.run_role(AgentRole.ENRICHER, _initial_state("a" * 64))
        assert state["receipts"][-1]["reason_code"] == "source_report_deadline_exhausted"
        assert state["receipts"][-1]["output"]["source_reports"] == []
    else:
        with pytest.raises(DBAPIError) as raised:
            fixture.runtime.run_role(AgentRole.ENRICHER, _initial_state("a" * 64))
        assert raised.value is failure and fixture.records == {}
