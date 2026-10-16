"""The server wrapper alone selects final validation; bytes cannot select a guard."""

from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest
from test_detached_job_executor import execution_trace as execution_trace

from ai_intel.workers import executor
from ai_intel.workers.executor import JobExecutionResult


def test_completion_guard_is_immutable_server_registry_configuration():
    def handler(context, payload):
        return JobExecutionResult()

    def guard(session, context, payload, result):
        return None

    wrapper = executor.DetachedJobHandler(handler, completion_guard=guard)
    assert wrapper.completion_guard is guard
    with pytest.raises(FrozenInstanceError):
        wrapper.completion_guard = None


@pytest.mark.parametrize("detached", [False, True])
def test_payload_guard_and_callable_attribute_cannot_select_final_validation(
    execution_trace, monkeypatch, detached
):
    events, active, _payload = execution_trace
    hostile_payload = b'{"completion_guard":"attacker", "mode":"detached"}'
    monkeypatch.setattr(executor, "read_job_payload", lambda *arguments: hostile_payload)

    def guard(*arguments):
        pytest.fail("external selection invoked a guard")

    def legacy(session, context, received):
        assert received is hostile_payload and active == {2}
        return JobExecutionResult()

    def service(context, received):
        assert received is hostile_payload and not active
        return JobExecutionResult()

    service.completion_guard = guard
    legacy.completion_guard = guard
    handler = executor.DetachedJobHandler(service) if detached else legacy
    assert executor.execute_job(object(), str(uuid4()), "worker", {"server_handler": handler}) == (
        "succeeded"
    )
    completion = next(event for event in events if event[0] == "complete")
    assert completion[1] == (3 if detached else 2) and not active
