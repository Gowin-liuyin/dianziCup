"""Twenty-minute default beat/live sources/browser run with owned descendant budgets."""

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
from ai_intel.infrastructure.settings import load_application_settings

from runtime_limits import CPU_SECONDS_TOTAL, OwnedJob

ROOT = Path("D:/wt/r06-integrated-live-1156")
RUN = Path(__file__).resolve().parent
CODE_SHA = "1156b2ed6616e3a4297215c2893d2cbe633f5215"
CLOCK = ZoneInfo("Asia/Shanghai")


def now():
    return datetime.now(CLOCK).isoformat(timespec="seconds")


def write(name, value):
    (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def main():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == CODE_SHA
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    settings = load_application_settings()
    assert settings.source_polling_enabled and settings.data_mode == "live"
    assert settings.generation_api_key is None or not settings.generation_api_key.get_secret_value()
    assert settings.content_store_backend == "minio"
    job = OwnedJob()
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"})
    with engine.connect() as connection:
        assert connection.scalar(text("select current_database()")) == "test_dianzi_r06_integrated_live_20261015"
        assert connection.scalar(text("select version_num from alembic_version")) == "0015_catalog_document_metadata"
        assert connection.scalar(text("select count(*) from job_runs")) == 0
    cache = Redis.from_url(os.environ["REDIS_URL"], socket_timeout=3, socket_connect_timeout=3)
    assert cache.connection_pool.connection_kwargs["db"] == 15 and cache.dbsize() == 0
    cache.close()
    secrets = tuple(value for value in json.loads(os.environ.pop("DIANZI_LOG_SECRET_VALUES")) if value)
    commands = {
        "api": [sys.executable, "-B", "-m", "uvicorn", "ai_intel.api.app:app", "--host", "127.0.0.1", "--port", "28012", "--log-level", "warning", "--no-access-log"],
        "worker": [sys.executable, "-B", "-m", "celery", "-A", "runtime_entry:celery_app", "worker", "--pool=solo", "--concurrency=1", "--queues=r06_integrated_live_1156", "--hostname=r06_integrated_live_1156@%h", "--loglevel=WARNING", "--without-gossip", "--without-mingle"],
        "scheduler": [sys.executable, "-B", "-m", "celery", "-A", "runtime_entry:celery_app", "beat", "--schedule", os.environ["DIANZI_BEAT_SCHEDULE_PATH"], "--loglevel=WARNING"],
        "frontend": ["node.exe", str(ROOT / "frontend/node_modules/vite/bin/vite.js"), "--host", "127.0.0.1", "--port", "25175", "--strictPort"],
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
    browser_process = None
    browser_started = None
    recheck_process = None
    recheck_started = None
    try:
        for name, command in commands.items():
            processes[name] = subprocess.Popen(command, cwd=ROOT / ("frontend" if name == "frontend" else "backend"), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=0x08000000)
            thread = threading.Thread(target=drain, args=(name, processes[name]), daemon=True)
            thread.start()
            threads.append(thread)
        write("runtime_start.json", {"started_at": started.isoformat(timespec="seconds"), "hard_deadline": (started + timedelta(seconds=1200)).isoformat(timespec="seconds"), "code_sha": CODE_SHA, "root": str(ROOT), "supervisor_pid": os.getpid(), "children": {name: process.pid for name, process in processes.items()}, "commands": commands, "maximum_seconds": 1200, "api_port": 28012, "frontend_port": 25175, "redis_database": 15, "queue": "r06_integrated_live_1156", "job_memory_bytes": 2 * 1024**3, "process_memory_bytes": 512 * 1024**2, "cpu_percent_of_host": 20, "cpu_seconds_budget": CPU_SECONDS_TOTAL, "source_job_budget": 80, "source_attempt_budget": 160, "source_running_watchdog_seconds": 35, "model_requests_permitted": 0, "source_polling_enabled": True, "beat_poll_interval_seconds": 60, "formal_observation": False})
        deadline = time.monotonic() + 1200
        last_heartbeat = 0
        while time.monotonic() < deadline:
            if (RUN / "stop.request").exists():
                reason = "owned_stop_request"
                break
            if log_limit.is_set() or any(process.poll() is not None for process in processes.values()):
                reason = "log_budget_or_child_exit"
                break
            if (RUN / "browser.request").exists() and browser_process is None:
                browser_command = ["node.exe", str(ROOT / "frontend/node_modules/@playwright/test/cli.js"), "test", "--config", str(RUN / "playwright.config.cjs")]
                browser_started = now()
                browser_process = subprocess.Popen(browser_command, cwd=ROOT / "frontend", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=0x08000000)
                thread = threading.Thread(target=drain, args=("browser", browser_process), daemon=True)
                thread.start()
                threads.append(thread)
                write("browser_start.json", {"started_at": browser_started, "pid": browser_process.pid, "command": browser_command, "cwd": str(ROOT / "frontend"), "inherited_owned_job_limits": True, "code_sha": CODE_SHA})
            if browser_process is not None and browser_process.poll() is not None and not (RUN / "browser_command.json").exists():
                write("browser_command.json", {"started_at": browser_started, "ended_at": now(), "exit_code": browser_process.returncode, "code_sha": CODE_SHA, "scope": "actual PG auth, source jobs and documents, no route interception; inherited owned resource limits"})
            if (RUN / "browser-recheck.request").exists() and browser_process is not None and browser_process.poll() is not None and recheck_process is None:
                recheck_command = ["node.exe", str(ROOT / "frontend/node_modules/@playwright/test/cli.js"), "test", "--config", str(RUN / "playwright.v2.config.cjs")]
                recheck_started = now()
                recheck_process = subprocess.Popen(recheck_command, cwd=ROOT / "frontend", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=0x08000000)
                thread = threading.Thread(target=drain, args=("browser_v2", recheck_process), daemon=True)
                thread.start()
                threads.append(thread)
                write("browser_start_v2.json", {"started_at": recheck_started, "pid": recheck_process.pid, "command": recheck_command, "cwd": str(ROOT / "frontend"), "inherited_owned_job_limits": True, "code_sha": CODE_SHA})
            if recheck_process is not None and recheck_process.poll() is not None and not (RUN / "browser_command_v2.json").exists():
                write("browser_command_v2.json", {"started_at": recheck_started, "ended_at": now(), "exit_code": recheck_process.returncode, "code_sha": CODE_SHA, "scope": "same product code; corrected selector/filter instrument in a new copy; first red preserved"})
            usage = job.usage()
            with engine.connect() as connection:
                stats = connection.execute(text("select count(*) jobs,coalesce(sum(attempt_count),0) attempts,min(started_at) filter(where status='running') running_since from job_runs where job_type='collect_public_source_page'")).mappings().one()
            age = (datetime.now(UTC) - stats["running_since"]).total_seconds() if stats["running_since"] else 0
            if age > 35 or stats["jobs"] >= 80 or stats["attempts"] >= 160 or usage["cpu_seconds"] >= CPU_SECONDS_TOTAL:
                reason = "source_or_cpu_budget"
                break
            if time.monotonic() - last_heartbeat >= 30:
                write("runtime_heartbeat.json", {"observed_at": now(), "code_sha": CODE_SHA, "children_alive": {name: process.poll() is None for name, process in processes.items()}, "source_jobs": stats["jobs"], "source_attempts": stats["attempts"], "usage": usage})
                last_heartbeat = time.monotonic()
            time.sleep(1)
    finally:
        if browser_process is not None:
            processes["browser"] = browser_process
        if recheck_process is not None:
            processes["browser_v2"] = recheck_process
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
