"""Trusted wrapper opt-in cannot be selected by payload or callable arity."""

from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest
from test_detached_job_executor import execution_trace as execution_trace

from ai_intel.workers import executor
from ai_intel.workers.executor import JobExecutionResult


def test_two_argument_callable_is_not_implicitly_detached(execution_trace):
    events, active, _payload = execution_trace

    def not_registered_as_detached(context, payload):
        pytest.fail("arity must not select execution mode")

    assert (
        executor.execute_job(
            object(), str(uuid4()), "worker", {"server_handler": not_registered_as_detached}
        )
        == "retry_wait"
    )
    assert (
        next(event for event in events if event[0] == "retry")[2]["error_code"] == "handler_failed"
    )
    assert not any(event[0] == "complete" for event in events) and not active


@pytest.mark.parametrize("invalid", [None, {"outcome": "succeeded"}, object()])
def test_untyped_result_cannot_be_completed_as_success(execution_trace, invalid):
    events, active, _payload = execution_trace
    handler = executor.DetachedJobHandler(lambda context, payload: invalid)
    assert (
        executor.execute_job(object(), str(uuid4()), "worker", {"server_handler": handler})
        == "retry_wait"
    )
    assert (
        next(event for event in events if event[0] == "retry")[2]["error_code"] == "handler_failed"
    )
    assert not any(event[0] == "complete" for event in events) and not active


def test_unknown_pg_job_type_never_reads_payload_or_chooses_handler(execution_trace, monkeypatch):
    events, active, _payload = execution_trace
    monkeypatch.setattr(
        executor,
        "read_job_payload",
        lambda *arguments: pytest.fail("unsupported type read payload"),
    )
    assert executor.execute_job(object(), str(uuid4()), "worker", {}) == "blocked"
    assert (
        next(event for event in events if event[0] == "retry")[2]["error_code"]
        == "unsupported_job_type"
    )
    assert not active


def test_server_wrapper_registration_is_immutable():
    handler = executor.DetachedJobHandler(lambda context, payload: JobExecutionResult())
    with pytest.raises(FrozenInstanceError):
        handler.handler = lambda context, payload: JobExecutionResult("blocked")
