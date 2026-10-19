"""Own the fixed e310 live source processes; a reviewed root gate is mandatory."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from authorization import ORIGINAL_OBSERVER_RELATIVE, RUN, TOOL_ROOT, verify_live_authorization
from owned_stop_watcher import owned_control_path, reject_previous_control_files
from runtime_controls import (
    CPU_SECONDS_CAP,
    MAXIMUM_SECONDS,
    RunningSourceLease,
    resource_guard_reason,
    running_lease_guard_reason,
)
from runtime_limits import OwnedJob
from stop_controller import read_actor_receipt, stop_actor
from windows_actor import WindowsOwnedActor

PRODUCT_ROOT = Path("D:/wt/r06-live-e310-20261016")
PRODUCT_SHA = "e310f7735bd499c4d9fbcefe8a644e2309a16a62"
OBSERVER = TOOL_ROOT / ORIGINAL_OBSERVER_RELATIVE
RUN_ID = "r06_live_e310_restart_20261016"
QUEUE = "r06_live_8a_20261016"


def write(name: str, value: object) -> None:
    (RUN / name).write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")


def main() -> None:
    gate = verify_live_authorization()
    if gate["product_sha"] != PRODUCT_SHA or Path(str(gate["product_root"])) != PRODUCT_ROOT:
        raise RuntimeError("fixed e310 product identity differs")
    reject_previous_control_files("worker")
    reject_previous_control_files("beat")
    if (RUN / "runtime_start.json").exists() or (RUN / "stop.request").exists():
        raise RuntimeError("new segment control files required")

    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    job = OwnedJob()
    url = make_url(os.environ["DATABASE_URL"])
    if (
        url.database != "test_dianzi_r06_catalog_live_8a_20261016"
        or url.port != 25432
        or url.host not in ("127.0.0.1", "localhost")
    ):
        raise RuntimeError("owned isolated PG required")
    engine = create_engine(
        url,
        hide_parameters=True,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"},
    )
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        if (
            connection.scalar(text("select version_num from alembic_version"))
            != "0016_source_response_receipts"
        ):
            raise RuntimeError("schema differs from root frozen e310 product")
        baseline_count = connection.scalar(
            text("select count(*) from job_runs where job_type='collect_public_source_page'")
        )
        baseline_counts = {
            name: connection.scalar(text("select count(*) from " + name))
            for name in (
                "documents",
                "document_revisions",
                "evidence",
                "source_response_receipts",
                "fetch_attempts",
            )
        }
    if not isinstance(baseline_count, int) or baseline_count >= 410:
        raise RuntimeError("insufficient source job slots before segment")
    secrets = tuple(
        value for value in json.loads(os.environ.pop("DIANZI_LOG_SECRET_VALUES")) if value
    )
    processes = {}
    actors = {}
    actor_receipts = {}
    threads = []
    log_budget = threading.Event()
    log_bytes = {}

    def drain(name, process):
        count = 0
        with (RUN / f"{name}.log").open("xb") as output:
            while chunk := process.stdout.readline(65536):
                for secret in sorted(secrets, key=len, reverse=True):
                    chunk = chunk.replace(secret.encode(), b"[REDACTED]")
                if count + len(chunk) > 8 * 1024**2:
                    log_budget.set()
                    break
                output.write(chunk)
                output.flush()
                count += len(chunk)
                log_bytes[name] = count

    started = datetime.now(ZoneInfo("Asia/Shanghai"))
    wall_deadline = min(
        started + timedelta(seconds=MAXIMUM_SECONDS),
        datetime.fromisoformat("2026-10-17T21:49:15+08:00"),
    )
    observer_run = OBSERVER / ("live_" + RUN_ID)
    observer_gate = {
        "root_live_authorized": True,
        "product_sha": PRODUCT_SHA,
        "observer_sha": gate["tool_sha"],
        "product_root": str(PRODUCT_ROOT),
        "run_id": RUN_ID,
        "segment_id": "segment_1",
        "started_at": started.isoformat(timespec="seconds"),
        "supervisor_limits_verified": True,
        "source_scope": [
            "nvd_ollama",
            "vllm_vendor",
            "osv_ollama",
            "avid_community",
            "ollama_releases",
            "trailofbits_blog",
            "arxiv_security",
            "nist_ai_rmf",
            "cac_generative_ai",
        ],
        "maximum_seconds": 21600,
        "postgres_port": 25432,
        "redis_port": 26379,
        "opensearch_port": 29200,
    }
    if (OBSERVER / "root_live_gate.json").exists() or observer_run.exists():
        raise RuntimeError("original observer requires a new run and gate")
    (OBSERVER / "root_live_gate.json").write_text(json.dumps(observer_gate, indent=2) + "\n")
    commands = {
        "api": [
            sys.executable,
            "-B",
            "-m",
            "uvicorn",
            "ai_intel.api.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            "28013",
            "--log-level",
            "warning",
            "--no-access-log",
        ],
        "worker": [
            sys.executable,
            "-B",
            "-m",
            "celery",
            "-A",
            "deploy_runtime_entry:celery_app",
            "worker",
            "--pool=solo",
            "--concurrency=1",
            "--queues=" + QUEUE,
            "--hostname=r06_live_e310_restart@%h",
            "--loglevel=WARNING",
            "--without-gossip",
            "--without-mingle",
        ],
        "beat": [
            sys.executable,
            "-B",
            "-m",
            "celery",
            "-A",
            "deploy_runtime_entry:celery_app",
            "beat",
            "--schedule",
            os.environ["DIANZI_BEAT_SCHEDULE_PATH"],
            "--loglevel=WARNING",
        ],
        "observer": [sys.executable, "-B", str(OBSERVER / "observe.py")],
    }
    reason = "bounded_deadline"
    current_lease = None
    usage = job.usage()
    stop_receipts = []
    try:
        for name, command in commands.items():
            environment = dict(os.environ)
            if name in ("worker", "beat"):
                environment["DIANZI_OWNED_PROCESS_ROLE"] = name
            processes[name] = subprocess.Popen(
                command,
                env=environment,
                cwd=PRODUCT_ROOT / "backend",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=0x08000000,
            )
            thread = threading.Thread(target=drain, args=(name, processes[name]), daemon=True)
            thread.start()
            threads.append(thread)
        ready_deadline = time.monotonic() + 15
        for role in ("worker", "beat"):
            while not owned_control_path(role, "ready").exists():
                if time.monotonic() >= ready_deadline or processes[role].poll() is not None:
                    raise RuntimeError("actual source actor ready identity unavailable")
                time.sleep(0.05)
            receipt = read_actor_receipt(role, "ready")
            actor_receipts[role] = receipt
            actors[role] = WindowsOwnedActor(
                receipt["actual_pid"], receipt["creation_ticks"], processes[role].pid
            )
        write(
            "runtime_start.json",
            {
                "started_at": started,
                "hard_deadline": wall_deadline,
                "product_sha": PRODUCT_SHA,
                "tool_sha": gate["tool_sha"],
                "original_observer_scripts_sha": "1c4cce9770bfa29d08728a0131f7fc7fe714f9bc",
                "supervisor_pid": os.getpid(),
                "launchers": {role: process.pid for role, process in processes.items()},
                "actual_actors": actor_receipts,
                "initial_source_jobs": baseline_count,
                "initial_history_counts": baseline_counts,
                "source_job_cap": 450,
                "prestop": 410,
                "wire_https_upper_bound": 35100,
                "actual_wire_count": "unknown",
                "cpu_seconds_cap": CPU_SECONDS_CAP,
                "source_actor_fence": True,
                "formal_six_hour_pass": False,
            },
        )
        deadline = time.monotonic() + max(
            0, (wall_deadline - datetime.now(wall_deadline.tzinfo)).total_seconds()
        )
        last_heartbeat = 0
        while time.monotonic() < deadline and datetime.now(wall_deadline.tzinfo) < wall_deadline:
            if (RUN / "stop.request").exists():
                reason = "owned_stop_request"
                break
            if log_budget.is_set():
                reason = "component_log_budget"
                break
            if any(process.poll() is not None for process in processes.values()):
                reason = "owned_child_exit"
                break
            usage = job.usage()
            with engine.connect() as connection:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                snapshot_time = connection.scalar(text("select transaction_timestamp()"))
                count = connection.scalar(
                    text(
                        "select count(*) from job_runs where job_type='collect_public_source_page'"
                    )
                )
                running = (
                    connection.execute(
                        text(
                            "select job_id,started_at,lease_expires_at from job_runs "
                            "where job_type='collect_public_source_page' and status='running' "
                            "order by started_at limit 3"
                        )
                    )
                    .mappings()
                    .all()
                )
            running_jobs = tuple(
                RunningSourceLease(row["job_id"], row["started_at"], row["lease_expires_at"])
                for row in running
            )
            current = [row for row in running_jobs if row.started_at >= started]
            current_lease = current[0].lease_expires_at if len(current) == 1 else None
            journal = observer_run / "collection_observations.jsonl"
            reason = (
                resource_guard_reason(
                    count,
                    usage["cpu_seconds"],
                    max(log_bytes.values(), default=0),
                    journal.stat().st_size if journal.exists() else 0,
                    (datetime.now(UTC) - snapshot_time).total_seconds(),
                )
                or running_lease_guard_reason(running_jobs, started, datetime.now(UTC))
                or "bounded_deadline"
            )
            if reason != "bounded_deadline":
                break
            if time.monotonic() - last_heartbeat >= 60:
                write(
                    "runtime_heartbeat.json",
                    {
                        "observed_at": datetime.now(UTC),
                        "source_jobs_total": count,
                        "source_jobs_new": count - baseline_count,
                        "running_current": [row.job_id for row in current],
                        "usage": usage,
                        "actual_wire_count": "unknown",
                        "tool_sha": gate["tool_sha"],
                        "product_sha": PRODUCT_SHA,
                    },
                )
                last_heartbeat = time.monotonic()
            time.sleep(0.25)
    except Exception as error:
        reason = "supervisor_error_" + type(error).__name__
    finally:
        hard_guard = reason not in (
            "bounded_deadline",
            "owned_stop_request",
            "source_job_headroom_stop",
        )
        for role in ("beat", "worker"):
            if role in actors:
                try:
                    stop_receipts.append(
                        stop_actor(
                            role,
                            actors[role],
                            actor_receipts[role],
                            current_lease if role == "worker" else None,
                            hard_guard,
                        )
                    )
                except Exception as error:
                    stop_receipts.append(
                        {
                            "role": role,
                            "stop_error_type": type(error).__name__,
                            "actual_stop_confirmed": False,
                        }
                    )
                    hard_guard = True
        if any(
            role in processes and processes[role].poll() is None and role not in actors
            for role in ("beat", "worker")
        ) or any(receipt.get("actual_stop_confirmed") is False for receipt in stop_receipts):
            write(
                "owned_stop_failure.json",
                {
                    "reason": reason,
                    "actual_actor_stop": stop_receipts,
                    "observer_terminal_guaranteed": False,
                    "formal_six_hour_pass": False,
                },
            )
            from ctypes import wintypes

            job.kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
            if not job.kernel.TerminateJobObject(job.handle, 70):
                raise RuntimeError("owned supervisor group could not fail closed")
        if "api" in processes and processes["api"].poll() is None:
            processes["api"].terminate()
        observer_run.mkdir(exist_ok=True)
        (observer_run / "collector_stop.request").write_text(
            "owned producers stopped or failed closed\n"
        )
        for name, process in processes.items():
            try:
                process.wait(timeout=40 if name == "observer" else 2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        for actor in actors.values():
            actor.close()
        for thread in threads:
            thread.join(timeout=1)
        engine.dispose()
        write(
            "runtime_end.json",
            {
                "started_at": started,
                "ended_at": datetime.now(UTC),
                "product_sha": PRODUCT_SHA,
                "tool_sha": gate["tool_sha"],
                "reason": reason,
                "actual_actor_stop": stop_receipts,
                "exit_codes": {name: process.returncode for name, process in processes.items()},
                "last_usage": usage,
                "formal_six_hour_pass": False,
            },
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        write(
            "startup_failure.json",
            {"error_type": type(error).__name__, "details": "withheld", "started": False},
        )
        raise SystemExit(1) from None
