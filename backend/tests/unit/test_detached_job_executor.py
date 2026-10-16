"""Fixture transactions verify the opt-in boundary; PG tests verify actual row locks."""

import asyncio
from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from ai_intel.workers import executor
from ai_intel.workers.executor import JobExecutionError, JobExecutionResult
from ai_intel.workers.jobs import JobLeaseLostError, JobPayloadUnavailableError


@pytest.fixture()
def execution_trace(monkeypatch):
    events = []
    active_sessions = set()
    payload = b'{"mode":"detached","tenant_id":"attacker","permissions":["admin"]}'

    class FixtureSession:
        def __init__(self, engine):
            self.number = len([event for event in events if event[0] == "open"]) + 1

        def __enter__(self):
            active_sessions.add(self.number)
            events.append(("open", self.number))
            return self

        def __exit__(self, *arguments):
            active_sessions.remove(self.number)
            events.append(("close", self.number))
            return False

        @contextmanager
        def begin(self):
            events.append(("begin", self.number))
            try:
                yield
            except BaseException:
                events.append(("rollback", self.number))
                raise
            else:
                events.append(("commit", self.number))

    def lease(session, *arguments, **options):
        events.append(("lease", session.number, options["expected_attempt"]))

    def complete(session, *arguments, **options):
        events.append(("complete", session.number, arguments, options))

    def retry(session, *arguments, **options):
        events.append(("retry", session.number, options))
        return "blocked" if options["blocked"] else "retry_wait"

    monkeypatch.setattr(executor, "Session", FixtureSession)
    monkeypatch.setattr(
        executor,
        "claim_job",
        lambda *arguments: {
            "attempt_count": 3,
            "tenant_id": "pg-tenant",
            "job_type": "server_handler",
        },
    )
    monkeypatch.setattr(executor, "require_job_lease", lease)
    monkeypatch.setattr(executor, "read_job_payload", lambda *arguments: payload)
    monkeypatch.setattr(executor, "complete_job", complete)
    monkeypatch.setattr(executor, "schedule_retry_or_fail", retry)
    return events, active_sessions, payload


@pytest.mark.parametrize("outcome", ["succeeded", "partial", "failed", "blocked"])
def test_detached_receives_pg_context_after_payload_transaction_closed(execution_trace, outcome):
    events, active, payload = execution_trace
    job_id = str(uuid4())

    def handler(context, received):
        assert not active
        assert context == executor.JobExecutionContext(job_id, "server-worker", 3, "pg-tenant")
        assert received == payload
        assert events[-1] == ("close", 2)
        events.append(("detached_effect",))
        return JobExecutionResult(outcome, "pg:fixture:effect", "fixture_result")

    result = executor.execute_job(
        object(), job_id, "server-worker", {"server_handler": executor.DetachedJobHandler(handler)}
    )
    assert result == outcome
    completion = next(event for event in events if event[0] == "complete")
    assert completion[1] == 3
    assert completion[3] == {
        "expected_attempt": 3,
        "result_ref": "pg:fixture:effect",
        "error_code": "fixture_result",
    }
    assert events[-2:] == [("commit", 3), ("close", 3)] and not active
    assert not any(event[0] == "retry" for event in events)


def test_payload_cannot_select_detached_mode_or_override_pg_identity(execution_trace):
    events, active, payload = execution_trace

    def legacy_handler(session, context, received):
        assert active == {2} and context.tenant_id == "pg-tenant"
        assert received == payload
        events.append(("legacy_effect", session.number))
        return JobExecutionResult()

    assert (
        executor.execute_job(object(), str(uuid4()), "worker", {"server_handler": legacy_handler})
        == "succeeded"
    )
    effect = next(event for event in events if event[0] == "legacy_effect")
    completion = next(event for event in events if event[0] == "complete")
    assert effect[1] == completion[1] == 2
    assert len([event for event in events if event[0] == "open"]) == 2 and not active


@pytest.mark.parametrize("phase", ["payload", "complete"])
def test_lost_lease_before_and_after_detached_effect_is_not_fake_success(
    execution_trace, monkeypatch, phase
):
    events, active, _payload = execution_trace

    def lost(*arguments, **options):
        raise JobLeaseLostError("lease expired")

    def handler(context, payload):
        assert not active
        events.append(("committed_service_effect",))
        return JobExecutionResult()

    monkeypatch.setattr(
        executor, "require_job_lease" if phase == "payload" else "complete_job", lost
    )
    assert (
        executor.execute_job(
            object(),
            str(uuid4()),
            "worker",
            {"server_handler": executor.DetachedJobHandler(handler)},
        )
        == "lease_lost"
    )
    assert any(event[0] == "committed_service_effect" for event in events) == (phase == "complete")
    assert not any(event[0] in {"retry", "complete"} for event in events) and not active


@pytest.mark.parametrize(
    "error,code,blocked",
    [
        (JobExecutionError("upstream_timeout", retry_after_seconds=12), "upstream_timeout", False),
        (JobExecutionError("actor_revoked", blocked=True), "actor_revoked", True),
        (RuntimeError("private upstream detail"), "handler_failed", False),
        (SQLAlchemyError("private database detail"), "database_operation_failed", False),
    ],
)
def test_detached_failure_uses_one_fresh_existing_retry_transaction(
    execution_trace, error, code, blocked
):
    events, active, _payload = execution_trace

    def handler(context, payload):
        assert not active
        raise error

    assert executor.execute_job(
        object(), str(uuid4()), "worker", {"server_handler": executor.DetachedJobHandler(handler)}
    ) == ("blocked" if blocked else "retry_wait")
    retries = [event for event in events if event[0] == "retry"]
    assert len(retries) == 1 and retries[0][1] == 3
    assert retries[0][2]["error_code"] == code
    assert retries[0][2]["expected_attempt"] == 3
    assert retries[0][2]["retry_after_seconds"] == getattr(error, "retry_after_seconds", None)
    assert not any(event[0] == "complete" for event in events) and not active


def test_detached_validation_failure_keeps_existing_classification(execution_trace):
    events, active, _payload = execution_trace

    def handler(context, payload):
        executor.SourceFetchFailure.model_validate_json(b"{}")
        raise AssertionError("unreachable")

    assert (
        executor.execute_job(
            object(),
            str(uuid4()),
            "worker",
            {"server_handler": executor.DetachedJobHandler(handler)},
        )
        == "blocked"
    )
    assert (
        next(event for event in events if event[0] == "retry")[2]["error_code"]
        == "invalid_job_payload"
    )
    assert not active


@pytest.mark.parametrize("phase", ["handler", "complete"])
@pytest.mark.parametrize("error", [KeyboardInterrupt(), SystemExit(), asyncio.CancelledError()])
def test_control_exception_propagates_same_object_without_retry(
    execution_trace, monkeypatch, phase, error
):
    events, active, _payload = execution_trace

    def interrupted(*arguments, **options):
        raise error

    handler = interrupted if phase == "handler" else lambda context, payload: JobExecutionResult()
    if phase == "complete":
        monkeypatch.setattr(executor, "complete_job", interrupted)
    with pytest.raises(type(error)) as captured:
        executor.execute_job(
            object(),
            str(uuid4()),
            "worker",
            {"server_handler": executor.DetachedJobHandler(handler)},
        )
    assert captured.value is error and not active
    assert not any(event[0] == "retry" for event in events)


def test_bad_payload_never_reaches_detached_handler(execution_trace, monkeypatch):
    events, active, _payload = execution_trace

    def unreadable(*arguments):
        raise JobPayloadUnavailableError("job_payload_digest_mismatch")

    monkeypatch.setattr(executor, "read_job_payload", unreadable)
    handler = executor.DetachedJobHandler(
        lambda *arguments: pytest.fail("invalid payload executed")
    )
    assert (
        executor.execute_job(object(), str(uuid4()), "worker", {"server_handler": handler})
        == "blocked"
    )
    assert (
        next(event for event in events if event[0] == "retry")[2]["error_code"]
        == "job_payload_digest_mismatch"
    )
    assert not active


def test_duplicate_unclaimed_delivery_never_reads_or_executes(execution_trace, monkeypatch):
    events, active, _payload = execution_trace
    monkeypatch.setattr(executor, "claim_job", lambda *arguments: None)
    handler = executor.DetachedJobHandler(lambda *arguments: pytest.fail("duplicate executed"))
    assert (
        executor.execute_job(object(), str(uuid4()), "worker", {"server_handler": handler})
        == "not_claimed"
    )
    assert events == [("open", 1), ("begin", 1), ("commit", 1), ("close", 1)] and not active
