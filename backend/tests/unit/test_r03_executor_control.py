"""离线执行控制测试核对回滚先于重试，不替代真实PG并发验证。"""

from contextlib import contextmanager
from uuid import uuid4

import pytest

from ai_intel.workers import executor
from ai_intel.workers.executor import JobExecutionError, JobExecutionResult
from ai_intel.workers.jobs import JobLeaseLostError, JobPayloadUnavailableError


@pytest.fixture()
def fixture_executor(monkeypatch):
    events = []

    class FixtureSession:
        def __init__(self, engine):
            self.engine = engine

        def __enter__(self):
            return self

        def __exit__(self, *arguments):
            return False

        @contextmanager
        def begin(self):
            events.append("begin")
            try:
                yield
            except Exception:
                events.append("rollback")
                raise
            else:
                events.append("commit")

    monkeypatch.setattr(executor, "Session", FixtureSession)
    monkeypatch.setattr(
        executor,
        "claim_job",
        lambda *a: {
            "attempt_count": 3,
            "tenant_id": "authenticated-tenant",
            "job_type": "fixture_handler",
        },
    )
    monkeypatch.setattr(executor, "require_job_lease", lambda *a, **k: None)
    monkeypatch.setattr(executor, "read_job_payload", lambda *a: b'{"source_id":"fixed"}')
    monkeypatch.setattr(executor, "complete_job", lambda *a, **k: events.append(("completed", k)))

    def schedule(*arguments, **options):
        events.append(("failure", options))
        return "blocked" if options["blocked"] else "retry_wait"

    monkeypatch.setattr(executor, "schedule_retry_or_fail", schedule)
    return events


def test_handler_receives_pg_identity_and_completion_shares_effect_transaction(
    fixture_executor,
) -> None:
    job_id = str(uuid4())

    def handler(session, context, payload):
        assert context.job_id == job_id and context.tenant_id == "authenticated-tenant"
        assert context.attempt_count == 3 and payload == b'{"source_id":"fixed"}'
        fixture_executor.append("business_effect")
        return JobExecutionResult("partial", "pg:fixture:result")

    assert (
        executor.execute_job(object(), job_id, "worker", {"fixture_handler": handler}) == "partial"
    )
    assert fixture_executor[0:3] == ["begin", "commit", "begin"]
    assert fixture_executor[3] == "business_effect"
    assert fixture_executor[4][0] == "completed"
    assert fixture_executor[4][1]["expected_attempt"] == 3
    assert fixture_executor[5] == "commit"


@pytest.mark.parametrize(
    "failure,code,blocked",
    [
        (JobExecutionError("upstream_timeout", retry_after_seconds=12), "upstream_timeout", False),
        (JobExecutionError("upstream_auth_denied", blocked=True), "upstream_auth_denied", True),
        (RuntimeError("private raw upstream details"), "handler_failed", False),
    ],
)
def test_business_failure_rolls_back_before_single_sanitized_failure_transaction(
    fixture_executor,
    failure,
    code,
    blocked,
) -> None:
    def handler(session, context, payload):
        raise failure

    expected = "blocked" if blocked else "retry_wait"
    assert (
        executor.execute_job(object(), str(uuid4()), "worker", {"fixture_handler": handler})
        == expected
    )
    assert fixture_executor[2:5] == ["begin", "rollback", "begin"]
    assert fixture_executor[5][0] == "failure"
    assert fixture_executor[5][1]["error_code"] == code
    assert fixture_executor[5][1]["expected_attempt"] == 3
    assert (
        len(
            [
                event
                for event in fixture_executor
                if isinstance(event, tuple) and event[0] == "failure"
            ]
        )
        == 1
    )


def test_unknown_handler_does_not_read_payload_and_is_blocked(
    fixture_executor, monkeypatch
) -> None:
    def forbidden(*args):
        raise AssertionError("unsupported handler accessed payload")

    monkeypatch.setattr(executor, "read_job_payload", forbidden)
    assert executor.execute_job(object(), str(uuid4()), "worker", {}) == "blocked"
    assert fixture_executor[5][1]["error_code"] == "unsupported_job_type"


def test_legacy_payload_is_blocked_without_calling_handler(fixture_executor, monkeypatch) -> None:
    def legacy(*args):
        raise JobPayloadUnavailableError("legacy_job_payload_unavailable")

    monkeypatch.setattr(executor, "read_job_payload", legacy)
    assert (
        executor.execute_job(
            object(),
            str(uuid4()),
            "worker",
            {"fixture_handler": lambda *a: pytest.fail("unrecoverable payload reached handler")},
        )
        == "blocked"
    )
    assert fixture_executor[5][1]["error_code"] == "legacy_job_payload_unavailable"


def test_invalid_json_handler_input_is_blocked(fixture_executor) -> None:
    def invalid(session, context, payload):
        executor.SourceFetchFailure.model_validate_json(b"{}")
        raise AssertionError("unreachable")

    assert (
        executor.execute_job(object(), str(uuid4()), "worker", {"fixture_handler": invalid})
        == "blocked"
    )
    assert fixture_executor[5][1]["error_code"] == "invalid_job_payload"


def test_lost_lease_rolls_back_and_does_not_schedule_over_new_owner(
    fixture_executor, monkeypatch
) -> None:
    def lost(*args, **kwargs):
        raise JobLeaseLostError("no longer owned")

    monkeypatch.setattr(executor, "require_job_lease", lost)
    assert executor.execute_job(object(), str(uuid4()), "worker", {}) == "lease_lost"
    assert fixture_executor == ["begin", "commit", "begin", "rollback"]


def test_duplicate_delivery_does_not_open_business_transaction(
    fixture_executor, monkeypatch
) -> None:
    monkeypatch.setattr(executor, "claim_job", lambda *a: None)
    assert executor.execute_job(object(), str(uuid4()), "worker", {}) == "not_claimed"
    assert fixture_executor == ["begin", "commit"]
