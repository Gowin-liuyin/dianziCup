"""固定代码的单API受控验证段，硬限制模型进程资源与整段墙钟。"""

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_intel.infrastructure.process_limits import bound_process_resources

root = Path("C:/Users/yinha/.codex/worktrees/r04-real-pipeline/dianzi")
run = Path(__file__).resolve().parent / "product_live_23c1878"
sha = "23c18784d71f1ed788072e6b3f2af70bac94fcb1"
clock = ZoneInfo("Asia/Shanghai")


def now():
    return datetime.now(clock).isoformat(timespec="seconds")


def main():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip() == sha
    assert (run / "migration.json").is_file() and not (run / "runtime_start.json").exists()
    limit_handle = bound_process_resources(memory_bytes=2 * 1024**3, cpu_seconds=30)
    assert limit_handle is not None
    secrets = tuple(value for value in json.loads(os.environ.pop("DIANZI_LOG_SECRET_VALUES")) if value)
    fragments = {value[index:index + 8] for value in secrets for index in range(max(0, len(value) - 7))}
    redactions = sorted(set(secrets) | fragments, key=len, reverse=True)
    log_limit = threading.Event()
    command = [sys.executable, "-m", "uvicorn", "ai_intel.api.app:app", "--host", "127.0.0.1", "--port", "28000", "--log-level", "warning"]
    started = now()
    process = subprocess.Popen(command, cwd=root / "backend", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=0x08000000)

    def drain():
        total = 0
        with (run / "api.log").open("wb") as target:
            while chunk := process.stdout.readline(65536):
                total += len(chunk)
                if total > 16 * 1024**2:
                    log_limit.set()
                    return
                for secret in redactions:
                    chunk = chunk.replace(secret.encode(), b"[REDACTED]")
                target.write(chunk)
                target.flush()

    thread = threading.Thread(target=drain, daemon=True)
    thread.start()
    (run / "runtime_start.json").write_text(json.dumps({"started_at": started, "code_sha": sha, "supervisor_pid": os.getpid(), "api_pid": process.pid, "command": command, "maximum_seconds": 900, "memory_hard_limit_per_process": 2 * 1024**3, "cpu_hard_limit_seconds_per_process": 30, "api_workers": 1, "model_child_concurrency": 1, "worker_and_beat": "not_started; readiness may be degraded", "live_paid_requests": "only bounded explicit POST by probe; no automatic schedule", "continuous_monitoring_claim": False}, indent=2), encoding="utf-8")
    reason = "deadline"
    deadline = time.monotonic() + 900
    try:
        while time.monotonic() < deadline:
            if (run / "stop.request").exists():
                reason = "requested_stop"
                break
            if process.poll() is not None or log_limit.is_set():
                reason = "child_exit_or_log_limit"
                break
            time.sleep(0.5)
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        thread.join(timeout=2)
        (run / "runtime_end.json").write_text(json.dumps({"started_at": started, "ended_at": now(), "reason": reason, "exit_code": process.returncode}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
