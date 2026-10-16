"""Isolated transaction traces check the final guard; actual PG locks need separate tests."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from test_detached_job_executor import execution_trace as execution_trace

from ai_intel.workers import executor
from ai_intel.workers.executor import JobExecutionError, JobExecutionResult
from ai_intel.workers.jobs import JobLeaseLostError


@pytest.mark.parametrize("outcome", ["succeeded", "partial", "failed", "blocked"])
def test_guard_runs_after_final_lease_in_the_completion_transaction(execution_trace, outcome):
    events, active, payload = execution_trace
    job_id = str(uuid4())
    result = JobExecutionResult(outcome, "pg:fixture:effect", "fixture_result")
    received_context = []

    def handler(context, received):
        assert not active and received is payload
        received_context.append(context)
        events.append(("detached_effect",))
        return result

    def guard(session, context, received, received_result):
        assert active == {3} and session.number == 3
        assert context is received_context[0]
        assert context == executor.JobExecutionContext(job_id, "worker", 3, "pg-tenant")
        assert received is payload and received_result is result
        assert events[-1] == ("lease", 3, 3)
        events.append(("guard", session.number))

    assert (
        executor.execute_job(
            object(),
            job_id,
            "worker",
            {"server_handler": executor.DetachedJobHandler(handler, completion_guard=guard)},
        )
        == outcome
    )
    final_events = events[events.index(("begin", 3)) :]
    assert [event[0] for event in final_events] == [
        "begin",
        "lease",
        "guard",
        "complete",
        "commit",
        "close",
    ]
    assert final_events[3][1] == 3 and final_events[3][3]["expected_attempt"] == 3
    assert not any(event[0] == "retry" for event in events) and not active


@pytest.mark.parametrize("explicit_none", [False, True])
def test_guard_none_preserves_existing_detached_results(execution_trace, explicit_none):
    events, active, _payload = execution_trace

    def handler(context, payload):
        assert not active
        return JobExecutionResult("partial", "pg:fixture:existing")

    wrapper = (
        executor.DetachedJobHandler(handler, completion_guard=None)
        if explicit_none
        else executor.DetachedJobHandler(handler)
    )
    assert wrapper.completion_guard is None
    assert executor.execute_job(object(), str(uuid4()), "worker", {"server_handler": wrapper}) == (
        "partial"
    )
    completion = next(event for event in events if event[0] == "complete")
    assert completion[1] == 3 and completion[3]["result_ref"] == "pg:fixture:existing"
    assert not active


@pytest.mark.parametrize(
    "failure,expected_status",
    [
        (JobExecutionError("inputs_changed", retry_after_seconds=12), "retry_wait"),
        (JobExecutionError("owner_revoked", blocked=True), "blocked"),
        (JobExecutionError("invalid_final_state", permanent=True), "failed"),
    ],
)
def test_guard_rejection_rolls_back_before_one_fresh_failure_transaction(
    execution_trace, monkeypatch, failure, expected_status
):
    events, active, _payload = execution_trace

    def guard(session, context, payload, result):
        events.append(("guard", session.number))
        raise failure

    def retry(session, *arguments, **options):
        assert active == {4} and session.number == 4
        assert events[-4:] == [("rollback", 3), ("close", 3), ("open", 4), ("begin", 4)]
        assert arguments[2] is failure.permanent
        assert options == {
            "expected_attempt": 3,
            "error_code": failure.error_code,
            "blocked": failure.blocked,
            "retry_after_seconds": failure.retry_after_seconds,
        }
        events.append(("retry", session.number))
        return expected_status

    monkeypatch.setattr(executor, "schedule_retry_or_fail", retry)
    wrapper = executor.DetachedJobHandler(
        lambda context, payload: JobExecutionResult(), completion_guard=guard
    )
    assert executor.execute_job(object(), str(uuid4()), "worker", {"server_handler": wrapper}) == (
        expected_status
    )
    assert [event for event in events if event[0] == "retry"] == [("retry", 4)]
    assert not any(event[0] == "complete" for event in events) and not active


@pytest.mark.parametrize("phase", ["before_guard", "during_guard"])
def test_final_lease_loss_never_completes_or_retries(execution_trace, monkeypatch, phase):
    events, active, _payload = execution_trace
    original_lease = executor.require_job_lease

    def lease(session, *arguments, **options):
        original_lease(session, *arguments, **options)
        if phase == "before_guard" and session.number == 3:
            raise JobLeaseLostError("new owner or attempt")

    def guard(session, context, payload, result):
        events.append(("guard", session.number))

    def complete(*arguments, **options):
        assert phase == "during_guard"
        raise JobLeaseLostError("expired during final validation")

    monkeypatch.setattr(executor, "require_job_lease", lease)
    monkeypatch.setattr(executor, "complete_job", complete)
    wrapper = executor.DetachedJobHandler(
        lambda context, payload: JobExecutionResult(), completion_guard=guard
    )
    assert executor.execute_job(object(), str(uuid4()), "worker", {"server_handler": wrapper}) == (
        "lease_lost"
    )
    assert (("guard", 3) in events) == (phase == "during_guard")
    assert events[-2:] == [("rollback", 3), ("close", 3)]
    assert not any(event[0] in {"complete", "retry"} for event in events) and not active


def test_completion_uses_fresh_clock_after_guard(execution_trace, monkeypatch):
    events, _active, _payload = execution_trace
    started_at = datetime(2026, 10, 16, tzinfo=UTC)
    current_time = [started_at]
    times = []

    def lease(session, job_id, worker_id, now, **options):
        times.append(("lease", session.number, now))

    def guard(session, context, payload, result):
        current_time[0] += timedelta(seconds=2)

    def complete(session, job_id, worker_id, outcome, now, **options):
        times.append(("complete", session.number, now))

    monkeypatch.setattr(executor, "require_job_lease", lease)
    monkeypatch.setattr(executor, "complete_job", complete)
    wrapper = executor.DetachedJobHandler(
        lambda context, payload: JobExecutionResult(), completion_guard=guard
    )
    assert (
        executor.execute_job(
            object(),
            str(uuid4()),
            "worker",
            {"server_handler": wrapper},
            clock=lambda: current_time[0],
        )
        == "succeeded"
    )
    assert times == [
        ("lease", 2, started_at),
        ("lease", 3, started_at),
        ("complete", 3, started_at + timedelta(seconds=2)),
    ]
    assert events[-2:] == [("commit", 3), ("close", 3)]


@pytest.mark.parametrize("error", [KeyboardInterrupt(), SystemExit(), asyncio.CancelledError()])
def test_guard_control_exception_propagates_without_retry(execution_trace, error):
    events, active, _payload = execution_trace

    def guard(session, context, payload, result):
        raise error

    wrapper = executor.DetachedJobHandler(
        lambda context, payload: JobExecutionResult(), completion_guard=guard
    )
    with pytest.raises(type(error)) as captured:
        executor.execute_job(object(), str(uuid4()), "worker", {"server_handler": wrapper})
    assert captured.value is error
    assert events[-2:] == [("rollback", 3), ("close", 3)]
    assert not any(event[0] in {"complete", "retry"} for event in events) and not active
