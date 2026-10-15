"""Windows 真实出网运行段；复用已测 Job 内存硬限额并独立看守 PG 任务期限。"""

import json
import os
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text

from ai_intel.ingestion.parsing._pdf_worker import _bound_memory

ROOT = Path("C:/Users/yinha/.codex/worktrees/r04-real-pipeline/dianzi")
RUN = Path(__file__).resolve().parent / "live_segment_4_link_cursor"
CLOCK = ZoneInfo("Asia/Shanghai")


def now():
    return datetime.now(CLOCK).isoformat(timespec="seconds")


def main():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == "8f6bd9f62b4bfb91c61ba47caaa7d6414fe6ecce"
    limit_handle = _bound_memory()
    assert limit_handle is not None
    RUN.mkdir(exist_ok=False)
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"})
    secrets = tuple(value for value in json.loads(os.environ.pop("DIANZI_LOG_SECRET_VALUES")) if value)
    log_limit = threading.Event()
    commands = {
        "api": [sys.executable, "-m", "uvicorn", "ai_intel.api.app:app", "--host", "127.0.0.1", "--port", "28000", "--log-level", "warning"],
        "worker": [sys.executable, "-m", "celery", "-A", "ai_intel.workers.runtime:celery_app", "worker", "--pool=solo", "--concurrency=1", "--loglevel=WARNING", "--without-gossip", "--without-mingle"],
        "scheduler": [sys.executable, "-m", "celery", "-A", "ai_intel.workers.runtime:celery_app", "beat", "--schedule", os.environ["DIANZI_BEAT_SCHEDULE_PATH"], "--loglevel=WARNING"],
    }
    processes = {}
    threads = []

    def drain(name, process):
        total = 0
        with (RUN / (name + ".log")).open("wb") as target:
            while chunk := process.stdout.readline(65536):
                total += len(chunk)
                if total > 16 * 1024 * 1024:
                    log_limit.set()
                    return
                for secret in secrets:
                    chunk = chunk.replace(secret.encode(), b"[REDACTED]")
                target.write(chunk)
                target.flush()

    started = now()
    reason = "deadline"
    try:
        for name, command in commands.items():
            processes[name] = subprocess.Popen(command, cwd=ROOT / "backend", stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, creationflags=0x08000000)
            thread = threading.Thread(target=drain, args=(name, processes[name]), daemon=True)
            thread.start()
            threads.append(thread)
        (RUN / "runtime_start.json").write_text(json.dumps({"started_at": started,
            "code_sha": "8f6bd9f62b4bfb91c61ba47caaa7d6414fe6ecce", "supervisor_pid": os.getpid(),
            "children": {name: process.pid for name, process in processes.items()}, "commands": commands,
            "maximum_seconds": 900, "memory_hard_limit_per_process": 536870912,
            "memory_limit_source": "frozen PDF Windows Job Object helper; inherited by children",
            "worker_pool": "solo; native Celery time limits unavailable; independent PG watchdog stops segment at running source page age35s plus <=3s DB timeout and polling",
            "redis_database": 14, "continuous_monitoring_claim": False}, indent=2))
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            if (RUN / "stop.request").exists():
                reason = "requested_stop"
                break
            if log_limit.is_set() or any(process.poll() is not None for process in processes.values()):
                reason = "child_exit_or_log_limit"
                break
            try:
                with engine.connect() as connection:
                    running_since = connection.scalar(text("SELECT min(started_at) FROM job_runs WHERE job_type='collect_public_source_page' AND status='running'"))
                if running_since is not None and (datetime.now(UTC) - running_since).total_seconds() > 35:
                    reason = "source_job_watchdog"
                    break
            except Exception:
                reason = "watchdog_database_unavailable"
                break
            time.sleep(0.5)
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
        (RUN / "runtime_end.json").write_text(json.dumps({"started_at": started, "ended_at": now(),
            "reason": reason, "exit_codes": {name: process.returncode for name, process in processes.items()}}, indent=2))


if __name__ == "__main__":
    main()
