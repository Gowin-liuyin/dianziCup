"""Bounded frozen-version services and authenticated two-source observation."""

import json
import os
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text

from runtime_limits import CPU_SECONDS_TOTAL, MEMORY_PER_PROCESS, MEMORY_TOTAL, OwnedJob

ROOT = Path("D:/wt/gb-controlled-collection-1927")
RUN = Path(__file__).resolve().parent
CODE_SHA = "1927eeb00a7e0c1335f76340b0382f46102f08f2"
MAXIMUM_SECONDS = 21600
MAXIMUM_SOURCE_JOBS = 480
MAXIMUM_SOURCE_ATTEMPTS = 1440
CLOCK = ZoneInfo("Asia/Shanghai")


def now():
    return datetime.now(CLOCK).isoformat(timespec="seconds")


def write(name, value):
    path = RUN / name
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def watchdog_reason(running_age, job_count, attempts, cpu_seconds):
    if running_age is not None and running_age > 35:
        return "source_job_watchdog"
    if job_count >= MAXIMUM_SOURCE_JOBS or attempts >= MAXIMUM_SOURCE_ATTEMPTS:
        return "source_call_budget"
    if cpu_seconds >= CPU_SECONDS_TOTAL:
        return "aggregate_cpu_budget"
    return None


def main():
    assert not (RUN / "runtime_start.json").exists(), "run already used"
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == CODE_SHA
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    job = OwnedJob()
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"})
    with engine.connect() as connection:
        assert connection.scalar(text("select current_database()")) == "test_dianzi_r04_pipeline_20261015"
        assert connection.scalar(text("select version_num from alembic_version")) == "0014_grounded_answer_vectors"
        assert connection.scalar(text("select count(*) from job_runs where status in ('queued','running','retry_wait')")) == 0
    secrets = tuple(value for value in json.loads(os.environ.pop("DIANZI_LOG_SECRET_VALUES")) if value)
    log_limit = threading.Event()
    commands = {
        "api": [sys.executable, "-B", "-m", "uvicorn", "ai_intel.api.app:app", "--host", "127.0.0.1", "--port", "28010", "--log-level", "warning", "--no-access-log"],
        "worker": [sys.executable, "-B", "-m", "celery", "-A", "runtime_entry:celery_app", "worker", "--pool=solo", "--concurrency=1", "--queues=gb_collection_1927", "--hostname=gb_collection_1927@%h", "--loglevel=WARNING", "--without-gossip", "--without-mingle"],
        "scheduler": [sys.executable, "-B", "-m", "celery", "-A", "runtime_entry:celery_app", "beat", "--schedule", os.environ["DIANZI_BEAT_SCHEDULE_PATH"], "--loglevel=WARNING"],
        "collector": [sys.executable, "-B", str(RUN / "collect.py")],
    }
    processes = {}
    threads = []

    def drain(name, process):
        total = 0
        with (RUN / (name + ".log")).open("xb") as target:
            while chunk := process.stdout.readline(65536):
                for secret in sorted(secrets, key=len, reverse=True):
                    chunk = chunk.replace(secret.encode(), b"[REDACTED]")
                total += len(chunk)
                if total > 16 * 1024**2:
                    log_limit.set()
                    return
                target.write(chunk)
                target.flush()

    started = now()
    started_datetime = datetime.fromisoformat(started)
    os.environ["DIANZI_COLLECTION_STARTED_AT"] = started
    reason = "deadline"
    final_usage = job.usage()
    try:
        for name, command in commands.items():
            processes[name] = subprocess.Popen(command, cwd=ROOT / "backend", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=0x08000000)
            thread = threading.Thread(target=drain, args=(name, processes[name]), daemon=True)
            thread.start()
            threads.append(thread)
        write("runtime_start.json", {"run_id": RUN.name, "started_at": started, "hard_deadline": (started_datetime + timedelta(seconds=MAXIMUM_SECONDS)).isoformat(timespec="seconds"), "code_sha": CODE_SHA, "root": str(ROOT), "supervisor_pid": os.getpid(), "children": {name: process.pid for name, process in processes.items()}, "commands": commands, "maximum_seconds": MAXIMUM_SECONDS, "per_process_memory_hard_limit_bytes": MEMORY_PER_PROCESS, "job_memory_hard_limit_bytes": MEMORY_TOTAL, "job_cpu_rate_hard_cap_percent_of_host": 20, "aggregate_cpu_budget_seconds": CPU_SECONDS_TOTAL, "cpu_watchdog_poll_seconds": 1, "source_running_watchdog_seconds": 35, "watchdog_database_timeout_seconds": 3, "maximum_source_jobs": MAXIMUM_SOURCE_JOBS, "maximum_source_attempts": MAXIMUM_SOURCE_ATTEMPTS, "log_limit_bytes_per_process": 16 * 1024**2, "redis_database": 12, "queue": "gb_collection_1927", "port": 28010, "formal_t54_claim": False, "broad_r06_coverage_claim": False})
        deadline = time.monotonic() + MAXIMUM_SECONDS
        last_heartbeat = 0
        while time.monotonic() < deadline:
            if (RUN / "stop.request").exists():
                reason = "requested_stop"
                break
            if log_limit.is_set():
                reason = "log_limit"
                break
            if any(process.poll() is not None for process in processes.values()):
                reason = "child_exit"
                break
            final_usage = job.usage()
            try:
                with engine.connect() as connection:
                    stats = connection.execute(text("select count(*) as jobs,coalesce(sum(attempt_count),0) as attempts,min(started_at) filter (where status='running') as running_since from job_runs where job_type='collect_public_source_page' and created_at>=:started"), {"started": started_datetime}).mappings().one()
                age = (datetime.now(UTC) - stats["running_since"]).total_seconds() if stats["running_since"] else None
                reason_candidate = watchdog_reason(age, stats["jobs"], stats["attempts"], final_usage["cpu_seconds"])
                if reason_candidate:
                    reason = reason_candidate
                    break
            except Exception as error:
                write("watchdog_failure.json", {"observed_at": now(), "error_type": type(error).__name__, "details": "withheld"})
                reason = "watchdog_database_unavailable"
                break
            if time.monotonic() - last_heartbeat >= 30:
                write("runtime_heartbeat.json", {"observed_at": now(), "code_sha": CODE_SHA, "children_alive": {name: process.poll() is None for name, process in processes.items()}, "source_jobs": stats["jobs"], "source_attempts": int(stats["attempts"]), "maximum_running_age_seconds": age, "usage": final_usage})
                last_heartbeat = time.monotonic()
            time.sleep(1)
    finally:
        write("collector_stop.request", {"requested_at": now(), "reason": reason})
        for process in processes.values():
            if process.poll() is None:
                process.terminate()
        for process in processes.values():
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for thread in threads:
            thread.join(timeout=2)
        engine.dispose()
        write("runtime_end.json", {"started_at": started, "ended_at": now(), "code_sha": CODE_SHA, "reason": reason, "exit_codes": {name: process.returncode for name, process in processes.items()}, "final_usage_before_cleanup": final_usage, "formal_t54_claim": False, "observation_completed_does_not_mean_passed": True})


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        write("runtime_failure.json", {"observed_at": now(), "error_type": type(error).__name__, "details": "withheld"})
        raise SystemExit(1) from None
