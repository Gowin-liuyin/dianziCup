"""受控本地集成进程；一小时到期收尾，只启动项目固定入口。"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

backend = Path(__file__).resolve().parents[3] / "backend"
run_directory = Path(__file__).resolve().parent
clock = ZoneInfo("Asia/Shanghai")
schedule_path = os.environ["DIANZI_BEAT_SCHEDULE_PATH"]
process_commands = {
    "api": [
        sys.executable,
        "-m",
        "uvicorn",
        "ai_intel.api.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        "28000",
        "--log-level",
        "warning",
    ],
    "worker": [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "ai_intel.workers.runtime:celery_app",
        "worker",
        "--pool=solo",
        "--concurrency=1",
        "--loglevel=WARNING",
        "--without-gossip",
        "--without-mingle",
    ],
    "scheduler": [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "ai_intel.workers.runtime:celery_app",
        "beat",
        "--schedule",
        schedule_path,
        "--loglevel=WARNING",
    ],
}
launched_at = datetime.now(clock).isoformat(timespec="seconds")
processes: dict[str, subprocess.Popen[bytes]] = {}
logs = []
deadline = time.monotonic() + 3600
try:
    for name, arguments in process_commands.items():
        output = (run_directory / f"runtime_{name}.log").open("ab")
        logs.append(output)
        processes[name] = subprocess.Popen(
            arguments,
            cwd=backend,
            stdout=output,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    receipt = {
        "started_at": launched_at,
        "supervisor_pid": os.getpid(),
        "children": {name: process.pid for name, process in processes.items()},
        "commands": process_commands,
        "maximum_duration_seconds": 3600,
        "pool": "solo on Windows integration; Linux container validation remains separate",
        "credential_source": "authorized environment; no credentials in arguments or receipt",
        "code_sha": os.environ["DIANZI_RUNTIME_CODE_SHA"],
        "deadline_control": "monotonic supervisor; stop marker supported",
    }
    (run_directory / "runtime_start.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    while time.monotonic() < deadline:
        if (run_directory / "runtime_stop.request").exists():
            break
        if any(process.poll() is not None for process in processes.values()):
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
    for output in logs:
        output.close()
    (run_directory / "runtime_end.json").write_text(
        json.dumps(
            {
                "started_at": launched_at,
                "ended_at": datetime.now(clock).isoformat(timespec="seconds"),
                "children_exit_codes": {
                    name: process.returncode for name, process in processes.items()
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
