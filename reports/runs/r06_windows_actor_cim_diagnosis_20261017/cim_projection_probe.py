"""Run one original and two projected full-process CIM queries without retries."""

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

from cim_probe import ACTOR_HASH, FIXED_SCRIPT, SCOPE

RUN = Path(__file__).resolve().parent


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def main():
    actor_path = SCOPE / "windows_actor.py"
    if hashlib.sha256(actor_path.read_bytes()).hexdigest() != ACTOR_HASH:
        raise RuntimeError("fixed actor bytes differ")
    sys.path.insert(0, str(SCOPE))
    from runtime_limits import CpuRate, ExtendedLimits, OwnedJob
    from windows_actor import _creation_ticks

    destination = RUN / "projection_incremental.json"
    if destination.exists():
        raise RuntimeError("projection evidence already exists")
    job = OwnedJob()
    kernel = job.kernel
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    kernel.GetActiveProcessorCount.argtypes = [wintypes.WORD]
    kernel.GetActiveProcessorCount.restype = wintypes.DWORD
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    cpus = kernel.GetActiveProcessorCount(0xFFFF)
    if cpus <= 0:
        raise RuntimeError("processor count unavailable")
    limits = job.query(9, ExtendedLimits)
    limits.basic.flags |= 0x8
    limits.basic.active_limit = 10
    limits.job_memory = 1024**3
    rate = CpuRate(5, min(10000, 20000 // cpus))
    for kind, value in ((9, limits), (15, rate)):
        if not kernel.SetInformationJobObject(job.handle, kind, ctypes.byref(value), ctypes.sizeof(value)):
            raise RuntimeError("projection limits unavailable")
    actual, actual_rate = job.query(9, ExtendedLimits), job.query(15, CpuRate)
    if not (actual.basic.active_limit == 10 and actual.basic.flags & 0x2308 == 0x2308
            and actual.process_memory == 512 * 1024**2 and actual.job_memory == 1024**3
            and actual_rate.flags == 5 and actual_rate.rate * cpus <= 20000):
        raise RuntimeError("queried projection limits differ")
    clock = time.monotonic()
    deadline = clock + 11
    record = {
        "started_at": now(), "data_mode": "harmless_native_readonly_projection_diagnosis",
        "maximum_internal_seconds": 11, "cases": [], "pid_filter_used": False,
        "source_actor_sha256": ACTOR_HASH, "source_modified": False,
        "business_source_started": False, "service_credentials_loaded": False, "paid_requests": 0,
        "observer": {"pid": os.getpid(), "parent_pid": os.getppid(), "creation_ticks": _creation_ticks(kernel, int(kernel.GetCurrentProcess()))},
        "native_limits": {"active_limit": 10, "process_memory_bytes": actual.process_memory,
                          "job_memory_bytes": actual.job_memory, "logical_cpu_count": cpus,
                          "cpu_rate": actual_rate.rate, "cpu_cores_upper_bound": actual_rate.rate * cpus / 10000,
                          "kill_on_close": bool(actual.basic.flags & 0x2000)},
    }

    def save():
        destination.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    def measure(label, script, expected_keys):
        if deadline - time.monotonic() < 3.25:
            record["cases"].append({"label": label, "status": "not_run", "reason": "bounded_window_remaining_below_three_seconds"})
            save()
            return
        entry = {"label": label, "started_at": now(), "script": script, "cim_timeout_seconds": 3,
                 "requested_executable": "powershell.exe", "flags": ["-NoProfile", "-Command"],
                 "creation_flags": 0, "status": "unknown"}
        phase = time.monotonic()
        process = subprocess.Popen(["powershell.exe", "-NoProfile", "-Command", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        entry["create_process_wall_seconds"] = time.monotonic() - phase
        birth = _creation_ticks(kernel, int(process._handle))
        member = wintypes.BOOL()
        if not kernel.IsProcessInJob(int(process._handle), job.handle, ctypes.byref(member)) or not member.value:
            raise RuntimeError("projected query child outside own Job")
        image_buffer = ctypes.create_unicode_buffer(32768)
        image_size = wintypes.DWORD(len(image_buffer))
        if not kernel.QueryFullProcessImageNameW(int(process._handle), 0, image_buffer, ctypes.byref(image_size)):
            raise RuntimeError("projected query held image unavailable")
        entry.update(pid=process.pid, creation_ticks=birth, actual_executable_image=image_buffer.value)
        communicate_clock = time.monotonic()
        try:
            stdout, stderr = process.communicate(timeout=3)
            entry["status"] = "completed" if process.returncode == 0 else "failed_exit"
        except subprocess.TimeoutExpired:
            entry["status"] = "timeout"
            process.kill()
            stdout, stderr = process.communicate(timeout=1)
        entry.update(ended_at=now(), wall_seconds=time.monotonic() - phase,
                     communicate_and_cleanup_wall_seconds=time.monotonic() - communicate_clock,
                     exit_code=process.returncode, held_kernel_exit_ack=kernel.WaitForSingleObject(int(process._handle), 0) == 0,
                     stdout_bytes=len(stdout.encode()), stdout_sha256=hashlib.sha256(stdout.encode()).hexdigest(),
                     stderr_bytes=len(stderr.encode()), stderr_sha256=hashlib.sha256(stderr.encode()).hexdigest())
        created, exited, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
        if not kernel.GetProcessTimes(int(process._handle), ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel_time), ctypes.byref(user_time)):
            raise RuntimeError("query child CPU unavailable")
        entry["child_cpu_seconds"] = ((kernel_time.dwHighDateTime << 32) + kernel_time.dwLowDateTime + (user_time.dwHighDateTime << 32) + user_time.dwLowDateTime) / 10_000_000
        if entry["status"] == "completed":
            rows = json.loads(stdout)
            if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) and set(row) == expected_keys and type(row["pid"]) is int for row in rows):
                entry["status"] = "failed_snapshot_shape"
            else:
                pids = {row["pid"] for row in rows}
                entry.update(process_row_count=len(rows), distinct_pid_count=len(pids),
                             pid_set_sha256=hashlib.sha256(json.dumps(sorted(pids)).encode()).hexdigest(),
                             observer_present=os.getpid() in pids, query_child_present=process.pid in pids,
                             ordered_json_keys=tuple(rows[0].keys()))
                if "created" in expected_keys:
                    entry["observer_row"] = next((row for row in rows if row["pid"] == os.getpid()), None)
                if len(pids) != len(rows) or os.getpid() not in pids:
                    entry["status"] = "failed_snapshot_identity"
        record["cases"].append(entry)
        save()

    save()
    measure("system_original_full_cim", FIXED_SCRIPT, {"pid", "parent", "created"})
    projected = FIXED_SCRIPT.replace("Get-CimInstance Win32_Process", "Get-CimInstance Win32_Process -Property ProcessId,ParentProcessId,CreationDate")
    measure("system_three_property_full_cim", projected, {"pid", "parent", "created"})
    names = "Get-CimInstance Win32_Process -Property ProcessId,Name | ForEach-Object { [ordered]@{pid=$_.ProcessId;name=$_.Name} } | ConvertTo-Json -Compress"
    measure("system_two_property_full_names", names, {"pid", "name"})
    record.update(ended_at=now(), wall_seconds=time.monotonic() - clock,
                  job_usage_after=job.usage(), source_after_sha256=hashlib.sha256(actor_path.read_bytes()).hexdigest())
    save()
    print(json.dumps({"cases_attempted": len(record["cases"]), "source_modified": False}))
    return int(any(row["status"] != "completed" for row in record["cases"]))


if __name__ == "__main__":
    raise SystemExit(main())
