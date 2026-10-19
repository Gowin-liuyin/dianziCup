"""Run an isolated offline review command with queried Job caps and full exec ancestry."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import datetime, timedelta, timezone
from pathlib import Path

import importlib.util
metadata_path = Path("D:/dianzi/reports/runs/recovery_reviewed_integration_20261016/batch13_process_metadata.py")
metadata_spec = importlib.util.spec_from_file_location("diagnosis_metadata", metadata_path)
metadata = importlib.util.module_from_spec(metadata_spec)
metadata_spec.loader.exec_module(metadata)

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
BASE_PYTHON = "C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe"
SITE = "D:/dianzi/backend/.venv/Lib/site-packages"


def timestamp() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def main() -> None:
    label, *arguments = sys.argv[1:]
    receipt_path = RUN / (label + ".command.json")
    if receipt_path.exists():
        raise RuntimeError("review evidence already exists")
    sys.path.insert(0, "D:/wt/r06-bcr1f2/reports/runs/r06_failed_bootstrap_control_review1_recheck_20261017/public_control_scope/core")
    from runtime_limits import CpuRate, ExtendedLimits, OwnedJob

    control, chain = metadata.control_root(metadata.current_identity())
    preexisting = metadata.descendants(control)
    job = OwnedJob()
    limits = job.query(9, ExtendedLimits)
    limits.basic.flags |= 0x8
    limits.basic.active_limit = 10
    limits.job_memory = 1024**3
    kernel = job.kernel
    kernel.GetActiveProcessorCount.argtypes = [wintypes.WORD]
    kernel.GetActiveProcessorCount.restype = wintypes.DWORD
    cpus = kernel.GetActiveProcessorCount(0xFFFF)
    if cpus <= 0:
        raise RuntimeError("processor count unavailable")
    rate = CpuRate(5, min(10000, 20000 // cpus))
    for kind, value in ((9, limits), (15, rate)):
        if not kernel.SetInformationJobObject(job.handle, kind, ctypes.byref(value), ctypes.sizeof(value)):
            raise OSError("offline native limits unavailable")
    actual_limits = job.query(9, ExtendedLimits)
    actual_rate = job.query(15, CpuRate)
    if not (
        actual_limits.basic.active_limit == 10
        and actual_limits.job_memory == 1024**3
        and actual_limits.process_memory == 512 * 1024**2
        and actual_limits.basic.flags & 0x2308 == 0x2308
        and actual_rate.flags == 5
        and actual_rate.rate * cpus <= 20000
    ):
        raise RuntimeError("offline native limits query differs")
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith(("TEST_", "DIANZI_")) or any(word in key.upper() for word in ("TOKEN", "SECRET", "PASSWORD", "API_KEY")) or key in {"DATABASE_URL", "REDIS_URL"}:
            environment.pop(key)
    environment.update(
        APP_ENV="test", DATA_MODE="fixture", SOURCE_POLLING_ENABLED="false",
        ENRICHMENT_GENERATION_ENABLED="false", PYTHONDONTWRITEBYTECODE="1",
        PYTHONIOENCODING="utf-8", PYTHONPATH=os.pathsep.join([SITE, str(ROOT / "backend/src"), str(ROOT)]),
    )
    command = [BASE_PYTHON, "-B", *arguments]
    started = timestamp()
    clock = time.monotonic()
    peak, seen = preexisting, dict(preexisting)
    errors = []
    failure = None
    with (RUN / (label + ".stdout.log")).open("xb") as stdout, (RUN / (label + ".stderr.log")).open("xb") as stderr:
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=stdout, stderr=stderr, creationflags=0x08000000)
        member = wintypes.BOOL()
        if not kernel.IsProcessInJob(int(process._handle), job.handle, ctypes.byref(member)) or not member.value:
            raise RuntimeError("offline child Job membership unavailable")
        timeout_seconds = 16
        deadline = time.monotonic() + timeout_seconds
        while process.poll() is None:
            try:
                tree = metadata.descendants(control)
                seen.update(tree)
                if len(tree) > len(peak):
                    peak = tree
                if len(tree) > 10:
                    failure = "full_windows_process_cap_exceeded"
            except OSError as error:
                errors.append(type(error).__name__)
                failure = "ancestry_sampling_failed"
            if time.monotonic() >= deadline:
                failure = "deadline_exceeded"
            if failure:
                process.kill()
                break
            time.sleep(0.02)
        process.wait(timeout=3)
        ack = kernel.WaitForSingleObject(int(process._handle), 0) == 0
    after = metadata.descendants(control)
    remaining = [row for pid, row in after.items() if pid not in preexisting]
    usage = job.usage()
    record = {
        "started_at": started, "ended_at": timestamp(), "wall_seconds": time.monotonic() - clock,
        "command": command, "cwd": str(ROOT), "exit_code": process.returncode,
        "failure": failure, "timeout_seconds": timeout_seconds, "held_child_kernel_exit_ack": ack,
        "control_chain": chain, "full_windows_peak": len(peak), "full_windows_peak_chain": list(peak.values()),
        "full_windows_after": list(after.values()), "remaining_owned": remaining,
        "linux_processes_started": 0, "sampling_errors": errors,
        "native_limits": {
            "active_limit": actual_limits.basic.active_limit, "job_memory_bytes": actual_limits.job_memory,
            "process_memory_bytes": actual_limits.process_memory, "logical_cpu_count": cpus,
            "cpu_rate": actual_rate.rate, "cpu_cores_upper_bound": actual_rate.rate * cpus / 10000,
            "kill_on_close": bool(actual_limits.basic.flags & 0x2000), "usage_after": usage,
        },
        "stdout_sha256": hashlib.sha256((RUN / (label + ".stdout.log")).read_bytes()).hexdigest(),
        "stderr_sha256": hashlib.sha256((RUN / (label + ".stderr.log")).read_bytes()).hexdigest(),
        "service_credentials_loaded": False, "paid_requests": 0, "wire_cost": "unknown",
    }
    receipt_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"label": label, "exit_code": process.returncode, "failure": failure, "windows_peak": len(peak), "remaining_owned": len(remaining), "kernel_ack": ack}))
    raise SystemExit(process.returncode or bool(failure or errors or remaining or not ack or usage["active_processes"] != 1))


if __name__ == "__main__":
    main()
