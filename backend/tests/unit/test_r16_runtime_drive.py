"""Explicit offline queue fixtures exercise the PG test harness; no database or real wait claim."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from tests.integration import test_r16_revalidation_runtime_pg as runtime


class FixtureClock:
    elapsed = 0.0

    def __init__(self):
        self.sleeps = []
        self.on_sleep = None

    def monotonic(self):
        return self.elapsed

    def sleep(self, seconds):
        assert 0 < seconds <= 1
        self.sleeps.append(seconds)
        self.elapsed += seconds
        if self.on_sleep is not None:
            self.on_sleep()

    def now(self, zone):
        assert zone is UTC
        return datetime(2026, 10, 17, tzinfo=UTC) + timedelta(seconds=self.elapsed)


class FixtureQueue:
    def __init__(self, jobs):
        self.jobs = jobs
        self.queries = []

    def connect(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query):
        self.queries.append(query)
        return self

    def mappings(self):
        return [dict(job) for job in self.jobs]


def job(job_id, status="queued", *, attempt_count=0, next_retry_at=None, error_code=None):
    return dict(
        job_id=job_id,
        status=status,
        attempt_count=attempt_count,
        next_retry_at=next_retry_at,
        error_code=error_code,
    )


@pytest.fixture
def offline_queue(monkeypatch, tmp_path):
    clock = FixtureClock()
    monkeypatch.setattr(runtime.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(runtime.time, "sleep", clock.sleep)
    monkeypatch.setattr(runtime, "datetime", clock)
    monkeypatch.setattr(
        runtime,
        "row",
        lambda engine, job_id: next(job for job in engine.jobs if job["job_id"] == job_id),
    )
    return clock, tmp_path / "drive.jsonl"


def journal(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_drive_waits_for_actual_due_retry_and_returns_pg_terminal_results(
    offline_queue, monkeypatch
):
    clock, path = offline_queue
    queue = FixtureQueue([job("completion"), job("child")])
    calls = []

    def execute(engine, seeded, job_id):
        calls.append((job_id, clock.elapsed))
        current = next(job for job in engine.jobs if job["job_id"] == job_id)
        current["attempt_count"] += 1
        if job_id == "completion" and current["attempt_count"] == 1:
            current.update(
                status="retry_wait",
                next_retry_at=clock.now(UTC) + timedelta(seconds=5),
                error_code="revalidation_completion_pending",
            )
        else:
            current.update(status="succeeded", next_retry_at=None, error_code=None)
        return current["status"]

    monkeypatch.setattr(runtime, "execute", execute)
    assert runtime.drive(queue, {"tenant": "offline-tenant"}, journal_path=path) == [
        ("completion", "succeeded"),
        ("child", "succeeded"),
    ]
    assert calls == [("completion", 0), ("child", 0), ("completion", 5)]
    assert clock.sleeps == [1] * 5
    returned = [entry for entry in journal(path) if entry["event"] == "execution_returned"]
    assert [(entry["outcome"], entry["attempt_count"]) for entry in returned] == [
        ("retry_wait", 1),
        ("succeeded", 1),
        ("succeeded", 2),
    ]
    assert returned[0]["next_retry_at"] == "2026-10-17 00:00:05+00:00"
    assert returned[0]["error_code"] == "revalidation_completion_pending"
    assert journal(path)[-1]["active_count"] == 0
    assert journal(path)[-1]["active_status_counts"] == {"queued": 0, "running": 0, "retry_wait": 0}
    compiled = str(queue.queries[0].compile(compile_kwargs={"literal_binds": True}))
    assert "ORDER BY job_runs.created_at, job_runs.job_id" in compiled
    assert "offline-tenant" in compiled
    assert "revalidate_change" in compiled and "revalidate_assessment" in compiled


def test_drive_does_not_reprioritize_due_retry_before_earlier_queued_job(
    offline_queue, monkeypatch
):
    clock, path = offline_queue
    queue = FixtureQueue([job("earlier"), job("later", "retry_wait", next_retry_at=clock.now(UTC))])
    calls = []

    def execute(engine, seeded, job_id):
        calls.append(job_id)
        next(job for job in engine.jobs if job["job_id"] == job_id)["status"] = "partial"
        return "partial"

    monkeypatch.setattr(runtime, "execute", execute)
    assert runtime.drive(queue, {"tenant": "offline"}, journal_path=path) == [
        ("earlier", "partial"),
        ("later", "partial"),
    ]
    assert calls == ["earlier", "later"]
    assert clock.sleeps == []


def test_drive_null_retry_time_remains_claimable(offline_queue, monkeypatch):
    clock, path = offline_queue
    queue = FixtureQueue([job("completion", "retry_wait", attempt_count=1)])

    def execute(engine, seeded, job_id):
        engine.jobs[0].update(status="partial", attempt_count=2)
        return "partial"

    monkeypatch.setattr(runtime, "execute", execute)
    assert runtime.drive(queue, {"tenant": "offline"}, journal_path=path) == [
        ("completion", "partial")
    ]
    assert clock.sleeps == []


@pytest.mark.parametrize("status", ["failed", "blocked", "cancelled", "waiting_approval"])
def test_drive_preserves_all_bad_terminal_results(offline_queue, monkeypatch, status):
    _, path = offline_queue
    queue = FixtureQueue([job("continuation", status, error_code="fixture_failure")])
    monkeypatch.setattr(runtime, "execute", lambda *args: pytest.fail("terminal job executed"))
    assert runtime.drive(queue, {"tenant": "offline"}, journal_path=path) == [
        ("continuation", status)
    ]
    assert journal(path)[0]["jobs"][0]["error_code"] == "fixture_failure"
    assert journal(path)[-1]["active_count"] == 0


def test_drive_waits_for_running_job_and_reads_actual_final_status(offline_queue, monkeypatch):
    clock, path = offline_queue
    queue = FixtureQueue([job("concurrent", "running", attempt_count=1)])
    clock.on_sleep = lambda: queue.jobs[0].update(status="blocked")
    monkeypatch.setattr(runtime, "execute", lambda *args: pytest.fail("live running job executed"))
    assert runtime.drive(queue, {"tenant": "offline"}, journal_path=path) == [
        ("concurrent", "blocked")
    ]
    assert clock.sleeps == [1]


@pytest.mark.parametrize("status", ["running", "retry_wait"])
def test_drive_deadline_fails_with_pending_work_in_journal(offline_queue, monkeypatch, status):
    clock, path = offline_queue
    due = clock.now(UTC) + timedelta(seconds=45) if status == "retry_wait" else None
    queue = FixtureQueue([job("pending", status, next_retry_at=due)])
    monkeypatch.setattr(runtime, "execute", lambda *args: pytest.fail("future/live job executed"))
    with pytest.raises(AssertionError, match="30 seconds"):
        runtime.drive(queue, {"tenant": "offline"}, journal_path=path)
    assert clock.elapsed == 30
    assert clock.sleeps == [1] * 30
    assert queue.jobs[0]["status"] == status and queue.jobs[0]["next_retry_at"] == due
    assert journal(path)[-1]["event"] == "deadline_exhausted"
    assert journal(path)[-1]["active_count"] == 1


def test_drive_honors_original_100_execution_limit(offline_queue, monkeypatch):
    clock, path = offline_queue
    queue = FixtureQueue([job("pending")])

    def execute(engine, seeded, job_id):
        engine.jobs[0].update(status="retry_wait", next_retry_at=None)
        engine.jobs[0]["attempt_count"] += 1
        return "retry_wait"

    monkeypatch.setattr(runtime, "execute", execute)
    with pytest.raises(AssertionError, match="execution limit"):
        runtime.drive(queue, {"tenant": "offline"}, journal_path=path)
    assert queue.jobs[0]["attempt_count"] == 100
    assert clock.elapsed == 0
    assert journal(path)[-1]["execution_calls"] == 100


def test_drive_returns_when_exactly_the_100th_execution_finishes(offline_queue, monkeypatch):
    _, path = offline_queue
    queue = FixtureQueue([job(str(index)) for index in range(100)])

    def execute(engine, seeded, job_id):
        next(job for job in engine.jobs if job["job_id"] == job_id)["status"] = "succeeded"
        return "succeeded"

    monkeypatch.setattr(runtime, "execute", execute)
    outputs = runtime.drive(queue, {"tenant": "offline"}, journal_path=path)
    assert len(outputs) == 100 and all(outcome == "succeeded" for _, outcome in outputs)
    assert journal(path)[-1]["execution_calls"] == 100
    assert journal(path)[-1]["active_count"] == 0


def test_drive_waits_only_until_fractional_retry_time(offline_queue, monkeypatch):
    clock, path = offline_queue
    queue = FixtureQueue(
        [job("completion", "retry_wait", next_retry_at=clock.now(UTC) + timedelta(seconds=0.25))]
    )

    def execute(engine, seeded, job_id):
        assert clock.elapsed == 0.25
        engine.jobs[0].update(status="succeeded", attempt_count=1, next_retry_at=None)
        return "succeeded"

    monkeypatch.setattr(runtime, "execute", execute)
    assert runtime.drive(queue, {"tenant": "offline"}, journal_path=path) == [
        ("completion", "succeeded")
    ]
    assert clock.sleeps == [0.25]


def test_drive_detects_disappeared_previously_observed_work(offline_queue, monkeypatch):
    clock, path = offline_queue
    queue = FixtureQueue([job("lost", "running")])
    clock.on_sleep = queue.jobs.clear
    monkeypatch.setattr(runtime, "execute", lambda *args: pytest.fail("live running job executed"))
    with pytest.raises(AssertionError, match="job state is missing"):
        runtime.drive(queue, {"tenant": "offline"}, journal_path=path)
    assert journal(path)[-1]["jobs"] == []


@pytest.mark.parametrize("outcome", ["lease_lost", "not_claimed", "unknown"])
def test_drive_unknown_execution_result_is_not_silently_green(offline_queue, monkeypatch, outcome):
    _, path = offline_queue
    queue = FixtureQueue([job("pending")])
    monkeypatch.setattr(runtime, "execute", lambda *args: outcome)
    with pytest.raises(AssertionError, match="classified persisted outcome"):
        runtime.drive(queue, {"tenant": "offline"}, journal_path=path)
    assert journal(path)[-1]["outcome"] == outcome
    assert journal(path)[-1]["status"] == "queued"


def test_drive_unknown_pg_state_is_not_silently_green(offline_queue):
    _, path = offline_queue
    with pytest.raises(AssertionError, match="unknown job status"):
        runtime.drive(
            FixtureQueue([job("unknown", "unknown")]), {"tenant": "offline"}, journal_path=path
        )


def test_drive_missing_cohort_is_not_a_vacuous_success(offline_queue):
    _, path = offline_queue
    with pytest.raises(AssertionError, match="job state is missing"):
        runtime.drive(FixtureQueue([]), {"tenant": "offline"}, journal_path=path)


def test_drive_overlong_synchronous_execute_is_reported_as_failure(offline_queue, monkeypatch):
    clock, path = offline_queue
    queue = FixtureQueue([job("slow")])

    def execute(engine, seeded, job_id):
        clock.elapsed = 31
        engine.jobs[0].update(status="succeeded", attempt_count=1)
        return "succeeded"

    monkeypatch.setattr(runtime, "execute", execute)
    with pytest.raises(AssertionError, match="30 seconds"):
        runtime.drive(queue, {"tenant": "offline"}, journal_path=path)
    assert journal(path)[-2]["outcome"] == "succeeded"
    assert journal(path)[-1]["elapsed_seconds"] == 31
