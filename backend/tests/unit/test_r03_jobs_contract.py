"""任务边界不访问外部网络，保持错误分类与重试预算。"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.workers.executor import JobExecutionError, JobExecutionResult, SourceFetchFailure
from ai_intel.workers.jobs import retry_delay_seconds


@pytest.mark.parametrize("attempt,seconds", [(1, 5), (2, 10), (6, 160), (7, 300), (10, 300)])
def test_persistent_retry_has_bounded_exponential_delay(attempt: int, seconds: int) -> None:
    assert retry_delay_seconds(attempt) == seconds


def test_retry_after_is_bounded_and_never_a_zero_delay_loop() -> None:
    assert retry_delay_seconds(1, 0) == 5
    assert retry_delay_seconds(2, 45) == 45
    for delay in (-1, 301, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            retry_delay_seconds(1, delay)


def test_invalid_enqueue_input_is_rejected_before_database_io() -> None:
    class NoDatabase:
        def execute(self, statement: object) -> None:
            raise AssertionError("invalid input reached database")

    for values in (
        {"tenant_id": ""},
        {"max_attempts": 11},
        {"max_attempts": 0},
        {"job_type": ""},
        {"payload": b"x" * 1048577},
        {"idempotency_key": ""},
        {"created_at": datetime(2026, 10, 15)},
    ):
        arguments = {
            "tenant_id": None,
            "job_type": "parse_document",
            "payload": b"{}",
            "created_at": datetime.now(UTC),
            **values,
        }
        with pytest.raises(ValueError):
            enqueue_job(NoDatabase(), **arguments)


@pytest.mark.parametrize("field", ["tenant_id", "url", "sql", "shell", "authorization"])
def test_builtin_payload_cannot_self_authorize_or_supply_tools(field: str) -> None:
    with pytest.raises(ValidationError):
        SourceFetchFailure.model_validate_json(
            '{"source_id":"fixed","observed_at":"2026-10-15T00:00:00Z","' + field + '":"forbidden"}'
        )


def test_result_and_failure_cannot_publish_raw_secret_messages_or_urls() -> None:
    with pytest.raises(ValueError):
        JobExecutionError("https://user:secret@provider.invalid")
    with pytest.raises(ValueError):
        JobExecutionResult(error_code="raw provider error with credentials")
    with pytest.raises(ValueError):
        JobExecutionResult(result_ref="file:///private/document")


def test_production_publisher_uses_fixed_task_name_and_only_job_uuid(monkeypatch) -> None:
    from uuid import uuid4

    from ai_intel.workers import runtime

    sent = []
    monkeypatch.setattr(
        runtime.celery_app, "send_task", lambda *args, **kwargs: sent.append((args, kwargs))
    )
    job_id = str(uuid4())
    runtime.publish_job_event({"job_id": job_id, "topic": "os.system", "payload_ref": "untrusted"})
    assert sent == [(("ai_intel.jobs.execute",), {"args": [job_id], "retry": False})]
    with pytest.raises(ValueError):
        runtime.publish_job_event({"job_id": "../private", "topic": "os.system"})
    assert len(sent) == 1
