"""Control interruption releases only its own reservation; consumed budgets stay consumed."""

from asyncio import CancelledError
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import DBAPIError
from test_r14_tool_gateway import (
    FixtureEvidenceReader,
    comparison_call,
    evidence_call,
    evidence_response,
    gateway,
    limits,
)

from ai_intel.api.authentication import Principal
from ai_intel.api.knowledge_contracts import DataMode
from ai_intel.domain.access import AccessScope, Role
from ai_intel.domain.enums import ToolStatus
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.tool_contracts import ReadEvidenceArguments, ToolResult
from ai_intel.investigation.tool_gateway import EvidenceRead, GatewayStoppedError, ToolGateway


@pytest.mark.parametrize("error", [KeyboardInterrupt(), SystemExit(17), CancelledError()])
def test_control_exception_during_preparation_releases_resources(error: BaseException) -> None:
    class InterruptedPreparationReader(FixtureEvidenceReader):
        pending: BaseException | None = error

        @property
        def data_mode(self) -> DataMode:
            if self.pending is not None:
                interruption, self.pending = self.pending, None
                raise interruption
            return "fixture"

    reader = InterruptedPreparationReader()
    subject = gateway(reader, max_result_bytes=4096, max_total_output_bytes=4096)
    with pytest.raises(type(error)) as raised:
        subject.execute(AgentRole.ASSESSOR, evidence_call())
    assert raised.value is error and subject.runs == () and reader.calls == 0
    assert subject.execute(AgentRole.ASSESSOR, evidence_call()).status is ToolStatus.SUCCEEDED
    assert reader.calls == 1


@pytest.mark.parametrize("error", [KeyboardInterrupt(), SystemExit(17), CancelledError()])
def test_control_exception_before_emission_releases_resources(
    error: BaseException,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = FixtureEvidenceReader()
    subject = gateway(reader, max_result_bytes=4096, max_total_output_bytes=4096)
    original_emit = subject._emit
    pending = True

    def interrupt_emission(result: ToolResult) -> ToolResult:
        nonlocal pending
        if pending:
            pending = False
            raise error
        return original_emit(result)

    monkeypatch.setattr(subject, "_emit", interrupt_emission)
    with pytest.raises(type(error)) as raised:
        subject.execute(AgentRole.ASSESSOR, evidence_call())
    assert raised.value is error and subject.runs == ()
    assert subject.execute(AgentRole.ASSESSOR, evidence_call()).status is ToolStatus.SUCCEEDED
    assert reader.calls == 2


@pytest.mark.parametrize("error", [KeyboardInterrupt(), SystemExit(17), CancelledError()])
def test_control_exception_after_emission_does_not_refund_written_bytes(
    error: BaseException,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = FixtureEvidenceReader()
    subject = gateway(reader, max_result_bytes=4096, max_total_output_bytes=4096)
    original_emit = subject._emit

    def emit_then_interrupt(result: ToolResult) -> ToolResult:
        original_emit(result)
        raise error

    monkeypatch.setattr(subject, "_emit", emit_then_interrupt)
    with pytest.raises(type(error)) as raised:
        subject.execute(AgentRole.ASSESSOR, evidence_call())
    assert raised.value is error and len(subject.runs) == 1
    assert subject.runs[0].usage.result_bytes > 0
    monkeypatch.setattr(subject, "_emit", original_emit)
    with pytest.raises(GatewayStoppedError, match="output_budget_exhausted"):
        subject.execute(AgentRole.ASSESSOR, evidence_call())
    assert reader.calls == 1


@pytest.mark.parametrize("error", [KeyboardInterrupt(), SystemExit(17), CancelledError()])
@pytest.mark.parametrize("budget", ["calls", "input"])
def test_control_exception_preserves_already_consumed_call_and_input_budgets(
    error: BaseException,
    budget: str,
) -> None:
    reader = FixtureEvidenceReader()
    reader.error = error
    changes = (
        {"max_calls": 1} if budget == "calls" else {"max_total_input_bytes": len(evidence_call())}
    )
    subject = gateway(reader, **changes)
    with pytest.raises(type(error)) as raised:
        subject.execute(AgentRole.ASSESSOR, evidence_call())
    assert raised.value is error and subject.runs == ()
    reader.error = None
    result = subject.execute(AgentRole.ASSESSOR, evidence_call())
    assert result.status is ToolStatus.BUDGET_EXHAUSTED
    expected = "call_budget_exhausted" if budget == "calls" else "input_budget_exhausted"
    assert result.error_code == expected and reader.calls == 1


@pytest.mark.parametrize("error", [KeyboardInterrupt(), SystemExit(17), CancelledError()])
def test_cancelled_call_does_not_release_another_inflight_call_or_reset_shared_counts(
    error: BaseException,
) -> None:
    first_goal, cancelled_goal, third_goal, fourth_goal = (uuid4() for _ in range(4))
    first_started, third_started, release = Event(), Event(), Event()
    calls: list[UUID] = []

    class SharedReader:
        data_mode = "fixture"

        def read_evidence(
            self,
            principal: Principal,
            scope: AccessScope,
            arguments: ReadEvidenceArguments,
            deadline_monotonic: float,
        ) -> EvidenceRead:
            calls.append(arguments.event_id)
            if len(calls) == 1:
                first_started.set()
                assert release.wait(timeout=3)
            elif len(calls) == 2:
                raise error
            elif len(calls) == 3:
                third_started.set()
                assert release.wait(timeout=3)
            return EvidenceRead(evidence_response(), True)

    subject = ToolGateway(
        Principal("fixture-shared", "owner", Role.ANALYST),
        uuid4(),
        limits(max_calls=4, max_concurrent_calls=2, max_total_output_bytes=12288),
        evidence_reader=SharedReader(),
    )
    with ThreadPoolExecutor(max_workers=2) as workers:
        first = workers.submit(
            subject.execute, AgentRole.ASSESSOR, evidence_call(goal_id=first_goal)
        )
        assert first_started.wait(timeout=3)
        with pytest.raises(type(error)) as raised:
            subject.execute(AgentRole.ASSESSOR, evidence_call(goal_id=cancelled_goal))
        assert raised.value is error and subject.runs == ()
        third = workers.submit(
            subject.execute, AgentRole.ASSESSOR, evidence_call(goal_id=third_goal)
        )
        assert third_started.wait(timeout=3)
        duplicate = subject.execute(AgentRole.ASSESSOR, evidence_call(goal_id=first_goal))
        assert (
            duplicate.status is ToolStatus.PARTIAL and duplicate.error_code == "duplicate_inflight"
        )
        capacity = subject.execute(AgentRole.ASSESSOR, evidence_call(goal_id=fourth_goal))
        assert capacity.status is ToolStatus.BUDGET_EXHAUSTED
        assert capacity.error_code == "concurrency_exhausted" and len(calls) == 3
        release.set()
        assert first.result(timeout=3).status is ToolStatus.SUCCEEDED
        assert third.result(timeout=3).status is ToolStatus.SUCCEEDED
    assert (
        subject.execute(AgentRole.ASSESSOR, evidence_call(goal_id=fourth_goal)).status
        is ToolStatus.SUCCEEDED
    )
    spent = subject.execute(AgentRole.ASSESSOR, evidence_call(goal_id=uuid4()))
    assert (
        spent.status is ToolStatus.BUDGET_EXHAUSTED and spent.error_code == "call_budget_exhausted"
    )
    assert len(calls) == 4 and sum(run.usage.result_bytes for run in subject.runs) <= 12288


@pytest.mark.parametrize("sqlstate", ["57014", "55P03", "08006"])
def test_database_error_status_is_the_original_enum(sqlstate: str) -> None:
    class FixtureDatabaseError(Exception):
        pass

    error = FixtureDatabaseError()
    error.sqlstate = sqlstate
    reader = FixtureEvidenceReader()
    reader.error = DBAPIError("fixture statement", (), error, False)
    result = gateway(reader).execute(AgentRole.ASSESSOR, evidence_call())
    expected = ToolStatus.FAILED if sqlstate == "08006" else ToolStatus.BUDGET_EXHAUSTED
    assert result.status is expected


def test_tool_result_schema_and_normal_results_reuse_the_frozen_status_enum() -> None:
    assert ToolResult.model_fields["status"].annotation is ToolStatus
    assert ToolResult.model_json_schema()["$defs"]["ToolStatus"]["enum"] == [
        item.value for item in ToolStatus
    ]
    assert gateway().execute(AgentRole.ASSESSOR, comparison_call()).status is ToolStatus.SUCCEEDED
    assert gateway().execute(AgentRole.ASSESSOR, comparison_call(None)).status is ToolStatus.PARTIAL
    reader = FixtureEvidenceReader()
    reader.outcome = EvidenceRead(evidence_response(), False)
    assert gateway(reader).execute(AgentRole.ASSESSOR, evidence_call()).status is ToolStatus.PARTIAL
