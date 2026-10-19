"""Twenty-minute frozen document browser run with owned descendant and call budgets."""

import json
import os
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from redis import Redis
from sqlalchemy import create_engine, text

from runtime_limits import CPU_SECONDS_TOTAL, OwnedJob

ROOT = Path("D:/wt/r06-document-live-0a45185")
RUN = Path(__file__).resolve().parent
CODE_SHA = "0a45185ae3ffb73a6d186b98421e26a52f78bfc6"
CLOCK = ZoneInfo("Asia/Shanghai")


def now():
    return datetime.now(CLOCK).isoformat(timespec="seconds")


def write(name, value):
    (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def main():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == CODE_SHA
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    job = OwnedJob()
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"})
    with engine.connect() as connection:
        assert connection.scalar(text("select current_database()")) == "test_dianzi_r06_documents_live_20261015"
        assert connection.scalar(text("select version_num from alembic_version")) == "0015_catalog_document_metadata"
        assert connection.scalar(text("select count(*) from job_runs")) == 0
    cache = Redis.from_url(os.environ["REDIS_URL"], socket_timeout=3, socket_connect_timeout=3)
    assert cache.connection_pool.connection_kwargs["db"] == 13 and cache.dbsize() == 0
    cache.close()
    secrets = tuple(value for value in json.loads(os.environ.pop("DIANZI_LOG_SECRET_VALUES")) if value)
    commands = {
        "api": [sys.executable, "-B", "-m", "uvicorn", "ai_intel.api.app:app", "--host", "127.0.0.1", "--port", "28011", "--log-level", "warning", "--no-access-log"],
        "worker": [sys.executable, "-B", "-m", "celery", "-A", "runtime_entry:celery_app", "worker", "--pool=solo", "--concurrency=1", "--queues=r06_document_live_0a45185", "--hostname=r06_document_live_0a45185@%h", "--loglevel=WARNING", "--without-gossip", "--without-mingle"],
        "scheduler": [sys.executable, "-B", "-m", "celery", "-A", "runtime_entry:celery_app", "beat", "--schedule", os.environ["DIANZI_BEAT_SCHEDULE_PATH"], "--loglevel=WARNING"],
        "frontend": ["node.exe", str(ROOT / "frontend/node_modules/vite/bin/vite.js"), "--host", "127.0.0.1", "--port", "25174", "--strictPort"],
    }
    processes = {}
    threads = []
    log_limit = threading.Event()

    def drain(name, process):
        count = 0
        with (RUN / (name + ".log")).open("xb") as output:
            while chunk := process.stdout.readline(65536):
                for secret in sorted(secrets, key=len, reverse=True):
                    chunk = chunk.replace(secret.encode(), b"[REDACTED]")
                count += len(chunk)
                if count > 16 * 1024**2:
                    log_limit.set()
                    break
                output.write(chunk)
                output.flush()

    started = datetime.now(CLOCK)
    reason = "deadline"
    usage = job.usage()
    try:
        for name, command in commands.items():
            processes[name] = subprocess.Popen(command, cwd=ROOT / ("frontend" if name == "frontend" else "backend"), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=0x08000000)
            thread = threading.Thread(target=drain, args=(name, processes[name]), daemon=True)
            thread.start()
            threads.append(thread)
        write("runtime_start.json", {"started_at": started.isoformat(timespec="seconds"), "hard_deadline": (started + timedelta(seconds=1200)).isoformat(timespec="seconds"), "code_sha": CODE_SHA, "root": str(ROOT), "supervisor_pid": os.getpid(), "children": {name: process.pid for name, process in processes.items()}, "commands": commands, "maximum_seconds": 1200, "api_port": 28011, "frontend_port": 25174, "redis_database": 13, "queue": "r06_document_live_0a45185", "job_memory_bytes": 2 * 1024**3, "process_memory_bytes": 512 * 1024**2, "cpu_percent_of_host": 20, "cpu_seconds_budget": CPU_SECONDS_TOTAL, "source_job_budget": 40, "source_attempt_budget": 120, "source_running_watchdog_seconds": 35, "model_requests_permitted": 0, "formal_observation": False})
        deadline = time.monotonic() + 1200
        last_heartbeat = 0
        while time.monotonic() < deadline:
            if (RUN / "stop.request").exists():
                reason = "owned_stop_request"
                break
            if log_limit.is_set() or any(process.poll() is not None for process in processes.values()):
                reason = "log_budget_or_child_exit"
                break
            usage = job.usage()
            with engine.connect() as connection:
                stats = connection.execute(text("select count(*) jobs,coalesce(sum(attempt_count),0) attempts,min(started_at) filter(where status='running') running_since from job_runs where job_type='collect_public_source_page'")).mappings().one()
            age = (datetime.now(UTC) - stats["running_since"]).total_seconds() if stats["running_since"] else 0
            if age > 35 or stats["jobs"] >= 40 or stats["attempts"] >= 120 or usage["cpu_seconds"] >= CPU_SECONDS_TOTAL:
                reason = "source_or_cpu_budget"
                break
            if time.monotonic() - last_heartbeat >= 30:
                write("runtime_heartbeat.json", {"observed_at": now(), "code_sha": CODE_SHA, "children_alive": {name: process.poll() is None for name, process in processes.items()}, "source_jobs": stats["jobs"], "source_attempts": stats["attempts"], "usage": usage})
                last_heartbeat = time.monotonic()
            time.sleep(1)
    finally:
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
        write("runtime_end.json", {"started_at": started.isoformat(timespec="seconds"), "ended_at": now(), "code_sha": CODE_SHA, "reason": reason, "exit_codes": {name: process.returncode for name, process in processes.items()}, "last_usage": usage, "observation_completed_does_not_mean_passed": True})


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        write("runtime_failure.json", {"observed_at": now(), "error_type": type(error).__name__, "details": "withheld"})
        raise SystemExit(1) from None
