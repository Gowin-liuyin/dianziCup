"""Linux 实际 API/prefork worker/beat 的有界运行段，固定 SHA 与仓外配置。"""

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path, PureWindowsPath
from zoneinfo import ZoneInfo

ROOT = Path("/mnt/c/Users/yinha/.codex/worktrees/r04-real-pipeline/dianzi")
RUN = Path("/mnt/d/dianzi/reports/runs/recovery_r04_source_jobs_20261015/live_segment_1")
CONFIG = Path("/tmp/dianzi-r04-live-20261015/private/runtime.json")
CLOCK = ZoneInfo("Asia/Shanghai")


def now():
    return datetime.now(CLOCK).isoformat(timespec="seconds")


def main():
    configuration = json.loads(CONFIG.read_text())
    metadata_reference = (ROOT / ".git").read_text().removeprefix("gitdir: ").strip()
    assert metadata_reference.replace("\\", "/").startswith("D:/dianzi/.git/worktrees/")
    metadata = Path("/mnt/d/dianzi/.git/worktrees") / PureWindowsPath(metadata_reference).name
    assert subprocess.check_output(["git", "--git-dir", str(metadata), "--work-tree", str(ROOT), "rev-parse", "HEAD"], text=True).strip() == configuration["code_sha"]
    RUN.mkdir(exist_ok=False)
    group = Path("/sys/fs/cgroup/dianzi-r01-20261014/r04-app-runtime-20261015")
    group.mkdir(exist_ok=False)
    for field, value in {"memory.max": "1073741824", "memory.swap.max": "0", "pids.max": "256", "cpu.max": "150000 100000"}.items():
        (group / field).write_text(value)
    (group / "cgroup.procs").write_text(str(os.getpid()))
    environment = dict(os.environ, **configuration["environment"])
    environment.update(PYTHONPATH=str(ROOT / "backend/src"), PYTHONUNBUFFERED="1", PYTHONUTF8="1")
    patterns = set()
    for value in configuration["secret_values"]:
        if value:
            patterns.add(value.encode())
            fragment_source = value.removeprefix("dianzi-r02-")
            patterns.update(fragment_source[i:i + 8].encode() for i in range(max(0, len(fragment_source) - 7)))
    redaction = re.compile(b"|".join(re.escape(value) for value in sorted(patterns, key=len, reverse=True)))
    commands = {
        "api": [sys.executable, "-m", "uvicorn", "ai_intel.api.app:app", "--host", "127.0.0.1", "--port", "28000", "--log-level", "warning"],
        "worker": [sys.executable, "-m", "celery", "-A", "ai_intel.workers.runtime:celery_app", "worker", "--pool=prefork", "--concurrency=1", "--loglevel=WARNING", "--without-gossip", "--without-mingle"],
        "scheduler": [sys.executable, "-m", "celery", "-A", "ai_intel.workers.runtime:celery_app", "beat", "--schedule", "/tmp/dianzi-r04-live-20261015/private/celerybeat", "--loglevel=WARNING"],
    }
    processes = {}
    readers = []
    log_overflow = threading.Event()

    def drain(name, process):
        size = 0
        with (RUN / (name + ".log")).open("wb") as target:
            while chunk := process.stdout.readline(65536):
                size += len(chunk)
                if size > 16 * 1024 * 1024:
                    log_overflow.set()
                    return
                target.write(redaction.sub(b"[REDACTED]", chunk))
                target.flush()

    started = now()
    deadline = time.monotonic() + 3600
    reason = "deadline"
    try:
        for name, command in commands.items():
            processes[name] = subprocess.Popen(command, cwd=ROOT / "backend", env=environment,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        for name, process in processes.items():
            thread = threading.Thread(target=drain, args=(name, process), daemon=True)
            thread.start()
            readers.append(thread)
        (RUN / "runtime_start.json").write_text(json.dumps({"started_at": started, "code_sha": configuration["code_sha"],
            "supervisor_pid": os.getpid(), "children": {name: process.pid for name, process in processes.items()},
            "commands": commands, "maximum_seconds": 3600, "cgroup": str(group),
            "memory_bytes": 1073741824, "cpu_quota": 1.5, "pid_limit": 256, "redis_database": 14,
            "worker_pool": "Linux prefork; soft25/hard30 seconds", "source_observation_started": False}, indent=2))
        while time.monotonic() < deadline:
            if (RUN / "stop.request").exists():
                reason = "requested_stop"
                break
            if log_overflow.is_set() or any(process.poll() is not None for process in processes.values()):
                reason = "child_exit_or_log_limit"
                break
            time.sleep(0.5)
    finally:
        for process in processes.values():
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for process in processes.values():
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        for thread in readers:
            thread.join(timeout=2)
        (RUN / "runtime_end.json").write_text(json.dumps({"started_at": started, "ended_at": now(),
            "reason": reason, "exit_codes": {name: process.returncode for name, process in processes.items()},
            "cgroup_events": (group / "memory.events").read_text()}, indent=2))


if __name__ == "__main__":
    main()
