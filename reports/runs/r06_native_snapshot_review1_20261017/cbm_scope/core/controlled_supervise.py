"""Own the single new live source run; the complete reviewed binding is mandatory."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from authorization import (
    ORIGINAL_OBSERVER_RELATIVE,
    RUN,
    TOOL_ROOT,
    verify_live_authorization,
)
from guard_observability import GuardObservation, aware_utc_timestamp
from owned_stop_watcher import owned_control_path, reject_previous_control_files
from run_binding import (
    DATABASE,
    NONCE,
    OBSERVER_SHA,
    PRODUCT_ROOT,
    PRODUCT_SHA,
    QUEUE,
    RUN_ID,
    cumulative_source_jobs,
    require_start_window,
    validate_service_urls,
    verify_database_connection,
)
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

OBSERVER = TOOL_ROOT / ORIGINAL_OBSERVER_RELATIVE


def write(name: str, value: object) -> None:
    (RUN / name).write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")


def producers_acknowledged(receipts: list[dict[str, object]]) -> bool:
    return (
        len(receipts) == 2
        and {row.get("role") for row in receipts} == {"beat", "worker"}
        and all(
            row.get("ack_present") is True
            and row.get("actual_pid_exited") is True
            and row.get("owned_descendants_exited") is True
            for row in receipts
        )
    )


def main() -> None:
    gate = verify_live_authorization()
    require_start_window(datetime.now(UTC))
    from configuration import read_launch_state

    launch_state = read_launch_state()
    if (
        launch_state["runtime_binding_sha256"]
        != hashlib.sha256((RUN / "runtime_binding.json").read_bytes()).hexdigest()
    ):
        raise RuntimeError("launch budget state differs from frozen runtime binding")
    prior_logs = launch_state["component_log_bytes"]
    roles: tuple[Literal["worker"], Literal["beat"]] = ("worker", "beat")
    stop_roles: tuple[Literal["beat"], Literal["worker"]] = ("beat", "worker")
    if (
        gate["product_sha"] != PRODUCT_SHA
        or Path(str(gate["product_root"])) != PRODUCT_ROOT
    ):
        raise RuntimeError("fixed new source product identity differs")
    reject_previous_control_files("worker")
    reject_previous_control_files("beat")
    if (RUN / "runtime_start.json").exists() or (RUN / "stop.request").exists():
        raise RuntimeError("new segment control files required")

    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    validate_service_urls(os.environ.get("DATABASE_URL"), os.environ.get("REDIS_URL"))
    url = make_url(os.environ["DATABASE_URL"])
    if (
        url.database != DATABASE
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
        verify_database_connection(connection, gate)
        baseline_count = connection.scalar(
            text(
                "select count(*) from job_runs where job_type='collect_public_source_page'"
            )
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
    baseline_count = cumulative_source_jobs(baseline_count, gate)
    if baseline_count >= 410:
        raise RuntimeError("insufficient source job slots before segment")
    job = OwnedJob()
    secrets = tuple(
        value
        for value in json.loads(os.environ.pop("DIANZI_LOG_SECRET_VALUES"))
        if value
    )
    processes = {}
    launcher_births = {}
    actors = {}
    actor_receipts = {}
    threads = []
    log_budget = threading.Event()
    log_bytes = {}

    def drain(name: str, process: subprocess.Popen[bytes]) -> None:
        count = 0
        if process.stdout is None:
            raise RuntimeError("owned process output pipe required")
        with (RUN / f"{name}.log").open("xb") as output:
            while chunk := process.stdout.readline(65536):
                for secret in sorted(secrets, key=len, reverse=True):
                    chunk = chunk.replace(secret.encode(), b"[REDACTED]")
                if prior_logs.get(name, 0) + count + len(chunk) > 8 * 1024**2:
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
        "segment_id": "segment_" + NONCE,
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
    (OBSERVER / "root_live_gate.json").write_text(
        json.dumps(observer_gate, indent=2) + "\n"
    )
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
            "--hostname=" + RUN_ID + "@%h",
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
    guard_observation: GuardObservation | None = None
    guard_rounds_attempted = 0
    startup_phase = "actor_launch"
    startup_role = None
    startup_failure_reason = "bootstrap_error"

    def record_startup_failure(error: Exception) -> None:
        process = processes.get(startup_role)
        write(
            "startup_failure.json",
            {
                "error_type": type(error).__name__,
                "failure_reason": startup_failure_reason,
                "phase": startup_phase,
                "actual_phase": "ready_identity_published"
                if startup_role in actor_receipts
                else "unknown_before_ready",
                "actual_identity": actor_receipts.get(startup_role)
                if startup_role in actors
                else None,
                "role": startup_role,
                "launcher_pid": process.pid if process is not None else None,
                "launcher_creation_ticks": launcher_births.get(startup_role),
                "launcher_poll": process.poll() if process is not None else None,
                "launchers": {
                    role: {
                        "pid": actor_process.pid,
                        "creation_ticks": launcher_births.get(role),
                        "poll": actor_process.poll(),
                    }
                    for role, actor_process in processes.items()
                },
                "registered_roles": sorted(actors),
                "run_id": RUN_ID,
                "nonce": NONCE,
                "product_sha": PRODUCT_SHA,
                "core_source_sha": gate["core_source_sha"],
                "operations_source_sha": gate["operations_source_sha"],
                "runtime_binding_sha256": launch_state["runtime_binding_sha256"],
                "observation_id": launch_state.get("observation_id"),
                "formal_six_hour_pass": False,
            },
        )

    try:
        import ctypes
        from ctypes import wintypes

        from windows_actor import _creation_ticks

        job.kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [
            ctypes.POINTER(wintypes.FILETIME)
        ] * 4
        for name, command in commands.items():
            if name == "observer":
                continue
            startup_role = name
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
            launcher_births[name] = _creation_ticks(
                job.kernel, int(processes[name]._handle)
            )
            thread = threading.Thread(
                target=drain, args=(name, processes[name]), daemon=True
            )
            thread.start()
            threads.append(thread)
        ready_deadline = time.monotonic() + 15
        startup_phase = "actor_ready_wait"
        for role in roles:
            startup_role = role
            while not owned_control_path(role, "ready").exists():
                if processes[role].poll() is not None:
                    startup_failure_reason = "launcher_exit"
                    raise RuntimeError("owned actor launcher exited before ready")
                if time.monotonic() >= ready_deadline:
                    startup_failure_reason = "ready_timeout"
                    raise RuntimeError("owned actor ready deadline expired")
                time.sleep(0.05)
            startup_phase = "actor_registration"
            receipt = read_actor_receipt(role, "ready")
            actor_receipts[role] = receipt
            actual_pid, creation_ticks = (
                receipt["actual_pid"],
                receipt["creation_ticks"],
            )
            if type(actual_pid) is not int or type(creation_ticks) is not int:
                raise RuntimeError("actual actor integer identity required")
            actors[role] = WindowsOwnedActor(
                actual_pid, creation_ticks, processes[role].pid, job.handle
            )
            startup_phase = "actor_ready_wait"
        startup_role = "observer"
        startup_phase = "observer_launch"
        processes["observer"] = subprocess.Popen(
            commands["observer"],
            env=dict(os.environ),
            cwd=PRODUCT_ROOT / "backend",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=0x08000000,
        )
        launcher_births["observer"] = _creation_ticks(
            job.kernel, int(processes["observer"]._handle)
        )
        thread = threading.Thread(
            target=drain, args=("observer", processes["observer"]), daemon=True
        )
        thread.start()
        threads.append(thread)
        startup_phase = "runtime_start_publication"
        write(
            "runtime_start.json",
            {
                "started_at": started,
                "hard_deadline": wall_deadline,
                "product_sha": PRODUCT_SHA,
                "tool_sha": gate["tool_sha"],
                "core_source_sha": gate["core_source_sha"],
                "operations_source_sha": gate["operations_source_sha"],
                "original_observer_scripts_sha": OBSERVER_SHA,
                "supervisor_pid": os.getpid(),
                "launchers": {role: process.pid for role, process in processes.items()},
                "actual_actors": actor_receipts,
                "initial_source_jobs": baseline_count,
                "source_job_ledger_offset": gate["source_job_ledger_offset"],
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
        last_heartbeat: float = 0
        while (
            time.monotonic() < deadline
            and datetime.now(wall_deadline.tzinfo) < wall_deadline
        ):
            if (RUN / "stop.request").exists():
                reason = "owned_stop_request"
                break
            if log_budget.is_set():
                reason = "component_log_budget"
                break
            if any(process.poll() is not None for process in processes.values()):
                reason = "owned_child_exit"
                break
            guard_rounds_attempted += 1
            guard_observation = GuardObservation(guard_rounds_attempted)
            guard_observation.begin("job_usage")
            usage = job.usage()
            guard_observation.end()
            guard_observation.begin("connect")
            connection_context = engine.connect()
            guard_observation.end()
            guard_observation.begin("context_enter")
            with connection_context as connection:
                guard_observation.end()
                try:
                    guard_observation.begin("set_read_only")
                    connection.execute(text("SET TRANSACTION READ ONLY"))
                    guard_observation.end()
                    guard_observation.begin("timestamp_query")
                    snapshot_time = connection.scalar(
                        text("select transaction_timestamp()")
                    )
                    guard_observation.end()
                    guard_observation.pg_transaction_timestamp_utc = (
                        aware_utc_timestamp(snapshot_time)
                    )
                    guard_observation.begin("count_query")
                    count = connection.scalar(
                        text(
                            "select count(*) from job_runs "
                            "where job_type='collect_public_source_page'"
                        )
                    )
                    count = cumulative_source_jobs(count, gate)
                    guard_observation.end()
                    guard_observation.begin("running_query")
                    running_result = connection.execute(
                        text(
                            "select job_id,started_at,lease_expires_at from job_runs "
                            "where job_type='collect_public_source_page' and status='running' "
                            "order by started_at limit 3"
                        )
                    )
                    guard_observation.end()
                    guard_observation.begin("row_mapping")
                    running_mappings = running_result.mappings()
                    guard_observation.end()
                    guard_observation.begin("row_materialization")
                    running = running_mappings.all()
                    guard_observation.end()
                finally:
                    guard_observation.end(
                        "failed" if sys.exc_info()[0] is not None else "completed"
                    )
                    guard_observation.begin("context_exit")
            guard_observation.end()
            guard_observation.begin("lease_projection")
            running_jobs = tuple(
                RunningSourceLease(
                    row["job_id"], row["started_at"], row["lease_expires_at"]
                )
                for row in running
            )
            current = [row for row in running_jobs if row.started_at >= started]
            current_lease = current[0].lease_expires_at if len(current) == 1 else None
            journal = observer_run / "collection_observations.jsonl"
            guard_observation.end()
            guard_observation.begin("component_log")
            guard_source_jobs = count
            guard_cpu_seconds = launch_state["cpu_seconds_used"] + usage["cpu_seconds"]
            guard_component_log_bytes = max(
                (
                    prior_logs.get(role, 0) + log_bytes.get(role, 0)
                    for role in ("api", "worker", "beat", "observer")
                ),
                default=0,
            )
            guard_observation.end()
            guard_observation.begin("journal_exists")
            journal_present = journal.exists()
            guard_observation.end()
            if journal_present:
                guard_observation.begin("journal_stat")
                guard_journal_bytes = journal.stat().st_size
                guard_observation.end()
            else:
                guard_journal_bytes = 0
            guard_journal_bytes += launch_state["journal_bytes_used"]
            guard_observation.begin("host_utc_evaluation")
            guard_host_utc = datetime.now(UTC)
            guard_snapshot_age_seconds = (
                guard_host_utc - snapshot_time
            ).total_seconds()
            guard_observation.end()
            guard_observation.record_age(guard_host_utc, guard_snapshot_age_seconds)
            guard_observation.begin("resource_and_lease_decision")
            reason = (
                resource_guard_reason(
                    guard_source_jobs,
                    guard_cpu_seconds,
                    guard_component_log_bytes,
                    guard_journal_bytes,
                    guard_snapshot_age_seconds,
                )
                or running_lease_guard_reason(running_jobs, started, datetime.now(UTC))
                or "bounded_deadline"
            )
            guard_observation.finish()
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
        if not (RUN / "runtime_start.json").exists():
            record_startup_failure(error)
        if guard_observation is not None:
            guard_observation.finish(failed=True)
    finally:
        hard_guard = reason not in (
            "bounded_deadline",
            "owned_stop_request",
            "source_job_headroom_stop",
        )
        for role in stop_roles:
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
        ) or any(
            receipt.get("actual_stop_confirmed") is False for receipt in stop_receipts
        ):
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
        if producers_acknowledged(stop_receipts):
            (observer_run / "collector_stop.request").write_bytes(
                b"owned producers stopped or failed closed\n"
            )
        for name, process in processes.items():
            try:
                shutdown_end = min(
                    wall_deadline + timedelta(seconds=900),
                    datetime.now(UTC) + timedelta(seconds=900),
                    datetime.fromisoformat(str(gate["parent_deadline"])),
                )
                process.wait(
                    timeout=max(0.1, (shutdown_end - datetime.now(UTC)).total_seconds())
                    if name == "observer"
                    else 2
                )
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
                "core_source_sha": gate["core_source_sha"],
                "operations_source_sha": gate["operations_source_sha"],
                "reason": reason,
                "actual_actor_stop": stop_receipts,
                "exit_codes": {
                    name: process.returncode for name, process in processes.items()
                },
                "last_usage": usage,
                "guard_observation": (
                    guard_observation.as_dict()
                    if guard_observation is not None
                    else {"guard_rounds_attempted": 0, "outcome": "not_started"}
                ),
                "formal_six_hour_pass": False,
            },
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        write(
            "startup_failure.json",
            {
                "error_type": type(error).__name__,
                "details": "withheld",
                "started": False,
            },
        )
        raise SystemExit(1) from None
