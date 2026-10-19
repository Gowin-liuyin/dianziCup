"""Three controls and three normal workers measure limiter startup and guard resources."""

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time


OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[2]
BASELINE = OUTPUT / "frozen_baseline_process_limits.py"


class MemoryCounters(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("faults", wintypes.DWORD)] + [(name, ctypes.c_size_t) for name in ("peak_working_set", "working_set", "peak_paged", "paged", "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile", "private_bytes")]


kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.GetCurrentProcess.restype = wintypes.HANDLE
kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel.OpenProcess.restype = wintypes.HANDLE
kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.c_void_p] * 4
kernel.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
kernel.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
kernel.CloseHandle.argtypes = [wintypes.HANDLE]


def native_stats(handle):
    memory = MemoryCounters()
    memory.size = ctypes.sizeof(memory)
    assert kernel.K32GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.size)
    times = [ctypes.c_ulonglong() for _ in range(4)]
    assert kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in times))
    count = wintypes.DWORD()
    assert kernel.GetProcessHandleCount(handle, ctypes.byref(count))
    return {"private_bytes": memory.private_bytes, "working_set_bytes": memory.working_set, "peak_working_set_bytes": memory.peak_working_set, "user_cpu_seconds": times[3].value/10_000_000, "kernel_cpu_seconds": times[2].value/10_000_000, "handles": count.value}


def worker(mode):
    if mode == "baseline":
        namespace = {}
        exec(compile(BASELINE.read_text(encoding="utf-8"), str(BASELINE), "exec"), namespace)
        bound = namespace["bound_process_resources"]
        guards = []
    else:
        from ai_intel.infrastructure import process_limits
        bound = process_limits.bound_process_resources
        guards = process_limits._WINDOWS_CPU_GUARDS
    process = kernel.GetCurrentProcess()
    before = native_stats(process)
    started_cpu, started_wall = time.process_time(), time.perf_counter()
    job_handle = bound(memory_bytes=100*1024**2, cpu_seconds=1)
    startup_wall, startup_cpu = time.perf_counter()-started_wall, time.process_time()-started_cpu
    guardian = None
    if guards:
        guard_handle = kernel.OpenProcess(0x1000, False, guards[0].pid)
        assert guard_handle is not None
        try:
            guardian = {"pid": guards[0].pid, **native_stats(guard_handle)}
        finally:
            kernel.CloseHandle(guard_handle)
    result = {"mode": mode, "pid": os.getpid(), "job_handle": job_handle, "startup_wall_seconds": startup_wall, "startup_worker_cpu_seconds": startup_cpu, "worker_before": before, "worker_after": native_stats(process), "guard": guardian}
    print(json.dumps(result), flush=True)


if len(sys.argv) == 2:
    worker(sys.argv[1])
else:
    BASELINE.write_bytes(subprocess.check_output(["git", "show", "45ee2d0d3bb007f0dbf5d753ee4b8c06d322758b:backend/src/ai_intel/infrastructure/process_limits.py"], cwd=ROOT))
    results = []
    for mode in ("baseline", "guard"):
        for attempt in range(3):
            result = subprocess.run([os.path.join(sys.base_prefix, "python.exe"), "-B", str(Path(__file__).resolve()), mode], capture_output=True, timeout=8, check=False)
            assert result.returncode == 0, result.stderr
            record = json.loads(result.stdout)
            record.update(attempt=attempt+1, returncode=result.returncode)
            results.append(record)
    summary = {"normal_worker_attempts": 6, "results": results, "median_startup_seconds": {mode: statistics.median(item["startup_wall_seconds"] for item in results if item["mode"] == mode) for mode in ("baseline", "guard")}}
    (OUTPUT / "overhead_measurement.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary), flush=True)
