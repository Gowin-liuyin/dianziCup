"""隔离Redis DB8中的实际Celery进程消费，绝不以直接函数调用代替worker。"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from threading import Thread
from uuid import uuid4

import pytest
from celery import Celery
from pydantic import SecretStr
from redis import Redis
from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from ai_intel.infrastructure.outbox import enqueue_job, relay_pending_events
from ai_intel.knowledge.models import fetch_attempts, job_runs, outbox_events

pytestmark = [pytest.mark.real_pg, pytest.mark.real_services]
EVIDENCE = Path(__file__).resolve().parents[3] / "reports/runs/recovery_r03_executor_20261015"
FIXTURE_WORKER = '''"""Explicit subprocess fixture handler, never imported by production."""
import os
import time
from datetime import UTC, datetime
from sqlalchemy import insert
from ai_intel.knowledge.models import fetch_attempts
from ai_intel.workers.runtime import celery_app, EXECUTION_HANDLERS
from ai_intel.workers.executor import JobExecutionResult, record_source_fetch_failure
assert os.environ["APP_ENV"] == "test" and os.environ["DATA_MODE"] == "fixture"
def interrupted_handler(session, context, payload):
    if context.attempt_count > 1:
        return record_source_fetch_failure(session, context, payload)
    import json
    source_id = json.loads(payload)["source_id"]
    session.execute(insert(fetch_attempts).values(attempt_id=context.job_id,
        source_id=source_id, attempted_at=datetime.now(UTC), outcome="failed", new_event_count=0))
    time.sleep(90)
    return JobExecutionResult(result_ref="pg:fetch_attempt:" + context.job_id)
EXECUTION_HANDLERS["r03_fixture_interrupted"] = interrupted_handler
celery_app.conf.task_default_queue = os.environ["R03_QUEUE"]
celery_app.conf.broker_transport_options["visibility_timeout"] = 5
celery_app.conf.beat_schedule = {
    "r03-dispatch": {"task": "ai_intel.jobs.dispatch_pending", "schedule": 2.0},
}
celery_app.start(sys.argv[1:])
'''.replace("import os\n", "import os\nimport sys\n", 1)


def wait_for(predicate: Callable[[], bool], timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.2)
    raise AssertionError("actual Celery process did not reach expected PG state before deadline")


def scrub_process_output(output: str) -> str:
    for key in ("TEST_DATABASE_URL", "TEST_REDIS_URL"):
        value = os.environ[key]
        values = (value, make_url(value).password or "")
        for credential in values:
            if not credential:
                continue
            output = output.replace(credential, "[redacted test credential]")
            if len(credential) >= 8:
                fragments = {credential[i : i + 8] for i in range(len(credential) - 7)}
                output = re.sub(
                    "|".join(re.escape(piece) for piece in sorted(fragments)),
                    "[redacted test credential fragment]",
                    output,
                )
    return output


def cleanup_owned_broker_state(client: Redis, run_id: str) -> dict[str, int]:
    """只清理已停进程本run路由/成员，不flush或删除别人的未确认消息。"""
    recovered_delivery_tags = []
    for delivery_tag, encoded in client.hgetall("unacked").items():
        message = json.loads(encoded)
        if len(message) == 3 and message[2] == run_id + "_queue":
            recovered_delivery_tags.append(delivery_tag)
    if recovered_delivery_tags:
        client.hdel("unacked", *recovered_delivery_tags)
        client.zrem("unacked_index", *recovered_delivery_tags)
    removed_bindings = 0
    for binding_key in ("_kombu.binding.celery.pidbox",):
        owned_members = [
            member for member in client.smembers(binding_key) if run_id.encode() in member
        ]
        if owned_members:
            removed_bindings += client.srem(binding_key, *owned_members)
    redis_keys = client.keys()
    owned_keys = [key for key in redis_keys if run_id.encode() in key]
    if owned_keys:
        client.delete(*owned_keys)
    return {
        "owned_unacked_removed": len(recovered_delivery_tags),
        "owned_bindings_removed": removed_bindings,
        "owned_queue_keys_removed": len(owned_keys),
    }


@pytest.fixture()
def queue_processes(
    migrated_engine: Engine, tmp_path: Path, register_sensitive_failure_value
) -> Iterator[tuple[Celery, Callable[..., subprocess.Popen], str]]:
    connection_url = os.environ["TEST_REDIS_URL"]
    parsed = make_url(connection_url)
    assert parsed.host == "127.0.0.1" and parsed.port == 26379 and parsed.database == "8"
    register_sensitive_failure_value(SecretStr(connection_url))
    client = Redis.from_url(connection_url, socket_connect_timeout=2, socket_timeout=2)
    initial_keys = client.keys()
    assert initial_keys == [], "Redis DB8 must be empty before this isolated package run"
    run_id = "r03_" + uuid4().hex
    queue = run_id + "_queue"
    environment = os.environ.copy()
    environment.update(
        DATABASE_URL=os.environ["TEST_DATABASE_URL"],
        REDIS_URL=connection_url,
        APP_ENV="test",
        DATA_MODE="fixture",
        R03_QUEUE=queue,
    )
    entrypoint = tmp_path / "r03_fixture_worker.py"
    entrypoint.write_text(FIXTURE_WORKER, encoding="utf-8")
    processes: list[tuple[str, subprocess.Popen, list[str], Thread, str]] = []

    def start(name: str, *, beat: bool = False) -> subprocess.Popen:
        started_at = datetime.now().astimezone().isoformat(timespec="seconds")
        arguments = [sys.executable, str(entrypoint)]
        if beat:
            arguments += ["beat", "--loglevel=WARNING", "--schedule", str(tmp_path / "beat-state")]
        else:
            arguments += [
                "worker",
                "--pool=solo",
                "--loglevel=WARNING",
                "--without-gossip",
                "--without-mingle",
                "--without-heartbeat",
                "-Q",
                queue,
                "-n",
                name + "@" + run_id,
            ]
        process = subprocess.Popen(
            arguments,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        output: list[str] = []

        def drain() -> None:
            assert process.stdout is not None
            for line in process.stdout:
                output.append(line)

        thread = Thread(target=drain, daemon=True)
        thread.start()
        processes.append((name, process, output, thread, started_at))
        return process

    application = Celery(run_id, broker=connection_url, backend=None)
    application.conf.update(
        task_default_queue=queue,
        task_serializer="json",
        accept_content=["json"],
        task_ignore_result=True,
        broker_connection_timeout=2,
        broker_transport_options={"socket_timeout": 2, "socket_connect_timeout": 2},
    )
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    try:
        yield application, start, run_id
    finally:
        for name, process, _output, _thread, _started_at in processes:
            if name == "beat" and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        drain_deadline = time.monotonic() + 15
        while processes and time.monotonic() < drain_deadline:
            if client.llen(queue) == 0 and client.hlen("unacked") == 0:
                break
            time.sleep(0.2)
        receipts = []
        for name, process, output, thread, started_at in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            thread.join(timeout=5)
            (EVIDENCE / (run_id + "_" + name + ".log")).write_text(
                scrub_process_output("".join(output)), encoding="utf-8"
            )
            receipts.append(
                {
                    "name": name,
                    "pid": process.pid,
                    "started_at": started_at,
                    "stopped_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "exit_code": process.returncode,
                    "pool": "native solo" if name != "beat" else "beat",
                }
            )
        cleanup = cleanup_owned_broker_state(client, run_id)
        (EVIDENCE / (run_id + "_processes.json")).write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "redis_db": 8,
                    "initial_key_count": len(initial_keys),
                    "cleanup": cleanup,
                    "processes": receipts,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        remaining = client.keys()
        assert remaining == [], "isolated Redis DB8 still has non-owned or unacked messages"
        application.close()
        client.close()


def enqueue_failure(
    engine: Engine, *, job_type: str = "record_source_fetch_failure"
) -> tuple[str, str]:
    now = datetime.now(UTC)
    source_id = str(uuid4())
    with Session(engine) as session, session.begin():
        session.execute(
            text(
                "INSERT INTO sources(source_id,name,category,base_origin,"
                "visibility,tenant_id,created_at) "
                "VALUES(:id,:name,'vendor_advisory','https://example.invalid','public',NULL,:at)"
            ),
            {"id": source_id, "name": "r03-celery-fixture-" + source_id, "at": now},
        )
        job_id = enqueue_job(
            session,
            None,
            job_type,
            json.dumps(
                {"source_id": source_id, "observed_at": now.isoformat(), "http_status": 503}
            ).encode(),
            now,
        )
    return source_id, job_id


def job_status(engine: Engine, job_id: str) -> str:
    with engine.connect() as connection:
        return connection.execute(
            select(job_runs.c.status).where(job_runs.c.job_id == job_id)
        ).scalar_one()


def test_two_actual_workers_and_beat_consume_duplicate_and_recover_killed_process(
    migrated_engine: Engine,
    queue_processes,
) -> None:
    application, start, _run_id = queue_processes
    dead_source, interrupted_job = enqueue_failure(
        migrated_engine, job_type="r03_fixture_interrupted"
    )
    dying_worker = start("interrupted_worker")
    application.send_task("ai_intel.jobs.execute", args=[interrupted_job], retry=False)
    wait_for(lambda: job_status(migrated_engine, interrupted_job) == "running")
    dying_worker.terminate()
    dying_worker.wait(timeout=10)
    with migrated_engine.connect() as connection:
        assert (
            connection.execute(
                select(func.count())
                .select_from(fetch_attempts)
                .where(fetch_attempts.c.source_id == dead_source)
            ).scalar_one()
            == 0
        )
        lease_expires_at = connection.execute(
            select(job_runs.c.lease_expires_at).where(job_runs.c.job_id == interrupted_job)
        ).scalar_one()
    start("worker_a")
    start("worker_b")
    start("beat", beat=True)
    source_id, job_id = enqueue_failure(migrated_engine)
    wait_for(lambda: job_status(migrated_engine, job_id) == "succeeded")
    for _ in range(3):
        application.send_task("ai_intel.jobs.execute", args=[job_id], retry=False)
    recovery_timeout = max(5, (lease_expires_at - datetime.now(UTC)).total_seconds()) + 30
    wait_for(
        lambda: job_status(migrated_engine, interrupted_job) == "succeeded",
        timeout=recovery_timeout,
    )
    with migrated_engine.connect() as connection:
        effects = (
            connection.execute(
                select(fetch_attempts.c.source_id).where(
                    fetch_attempts.c.source_id.in_([source_id, dead_source])
                )
            )
            .scalars()
            .all()
        )
        assert sorted(effects) == sorted([source_id, dead_source])
        assert (
            connection.execute(
                select(job_runs.c.attempt_count).where(job_runs.c.job_id == interrupted_job)
            ).scalar_one()
            == 2
        )
        assert (
            connection.execute(
                select(job_runs.c.attempt_count).where(job_runs.c.job_id == job_id)
            ).scalar_one()
            == 1
        )


def test_real_broker_disconnect_preserves_outbox_then_publish_replay_has_one_effect(
    migrated_engine: Engine,
    queue_processes,
) -> None:
    application, start, _run_id = queue_processes
    source_id, job_id = enqueue_failure(migrated_engine)
    bad_url = (
        make_url(os.environ["TEST_REDIS_URL"]).set(port=49199).render_as_string(hide_password=False)
    )
    unavailable = Celery("r03_unavailable", broker=bad_url, backend=None)
    unavailable.conf.update(
        broker_connection_timeout=1,
        broker_transport_options={"socket_timeout": 1, "socket_connect_timeout": 1},
    )

    def broken_publisher(event: dict[str, str]) -> None:
        unavailable.send_task("ai_intel.jobs.execute", args=[event["job_id"]], retry=False)

    with Session(migrated_engine) as session, session.begin():
        relay_pending_events(session, datetime.now(UTC), publisher=broken_publisher, limit=1000)
        row = (
            session.execute(select(outbox_events).where(outbox_events.c.job_id == job_id))
            .mappings()
            .one()
        )
        assert row["published_at"] is None and row["last_error_code"] == "broker_publish_failed"
        retry_at = row["next_delivery_at"]
    unavailable.close()
    start("worker_a")
    start("worker_b")
    wait_for(lambda: datetime.now(UTC) >= retry_at, timeout=10)

    def publisher(event: dict[str, str]) -> None:
        application.send_task("ai_intel.jobs.execute", args=[event["job_id"]], retry=False)

    with Session(migrated_engine) as session:
        relay_pending_events(session, datetime.now(UTC), publisher=publisher, limit=1000)
        session.rollback()
    with Session(migrated_engine) as session, session.begin():
        relay_pending_events(session, datetime.now(UTC), publisher=publisher, limit=1000)
    wait_for(lambda: job_status(migrated_engine, job_id) == "succeeded")
    with migrated_engine.connect() as connection:
        assert (
            connection.execute(
                select(func.count())
                .select_from(fetch_attempts)
                .where(fetch_attempts.c.source_id == source_id)
            ).scalar_one()
            == 1
        )
