"""A singleton source producer must pass the owned stop and PG row budget first."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

from celery.exceptions import WorkerShutdown
from owned_stop_watcher import owned_control_path, read_stop_request
from runtime_controls import SOURCE_JOB_PRESTOP
from sqlalchemy import Engine, text


def producer_admitted(source_jobs: int, maximum_attempts: int) -> bool:
    """One poll transaction can add nine roots; one page transaction adds one successor."""
    return (
        type(source_jobs) is int
        and 0 <= source_jobs < SOURCE_JOB_PRESTOP
        and type(maximum_attempts) is int
        and 1 <= maximum_attempts <= 3
    )


def request_owned_worker_stop() -> None:
    path = owned_control_path("worker", "stop")
    if not path.exists():
        pending = path.with_suffix(".pending")
        with pending.open("xb") as output:
            output.write(json.dumps({"role": "worker", "owned_stop": True}).encode() + b"\n")
            output.flush()
            os.fsync(output.fileno())
        pending.replace(path)
    elif not read_stop_request("worker"):
        raise RuntimeError("owned stop request differs")


def require_producer_slot(engine: Engine) -> None:
    """Stop before the original task claims PG or performs source IO; errors stop the actor."""
    if read_stop_request("worker"):
        raise WorkerShutdown(0)
    try:
        with engine.connect() as connection, connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout=3000"))
            row = (
                connection.execute(
                    text(
                        "select count(*) source_jobs,"
                        "coalesce(max(max_attempts),3) maximum_attempts "
                        "from job_runs where job_type='collect_public_source_page'"
                    )
                )
                .mappings()
                .one()
            )
        admitted = producer_admitted(row["source_jobs"], row["maximum_attempts"])
    except Exception as error:
        failure_path = owned_control_path("worker", "ready").parent / (
            f"fence_failure_{os.getpid()}.json"
        )
        with failure_path.open("xb") as output:
            output.write(
                json.dumps(
                    {
                        "actual_pid": os.getpid(),
                        "observed_at": datetime.now(UTC).isoformat(),
                        "phase": "producer_slot_pg_read",
                        "error_type": type(error).__name__,
                        "details": "withheld",
                    }
                ).encode()
                + b"\n"
            )
        request_owned_worker_stop()
        raise WorkerShutdown(70) from None
    if not admitted or read_stop_request("worker"):
        request_owned_worker_stop()
        raise WorkerShutdown(0)
