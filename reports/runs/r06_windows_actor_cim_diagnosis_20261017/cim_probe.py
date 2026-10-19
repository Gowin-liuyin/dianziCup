"""Measure fixed three-second CIM paths using only two harmless owned children."""

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

RUN = Path(__file__).resolve().parent
SCOPE = Path("D:/wt/r06-bcr1f2/reports/runs/r06_failed_bootstrap_control_review1_recheck_20261017/public_control_scope/core")
ACTOR_HASH = "d7472af2a53b4f126448cb2a5999de12fa80dabd000670fdf4c81ca8efd9dabc"
PWSH = "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe"
SYSTEM_PS = "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
FIXED_SCRIPT = (
    "Get-CimInstance Win32_Process | ForEach-Object { "
    "[ordered]@{pid=$_.ProcessId;parent=$_.ParentProcessId;"
    "created=$_.CreationDate.ToUniversalTime().ToString('o')} } | ConvertTo-Json -Compress"
)


def now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def main() -> int:
    actor_path = SCOPE / "windows_actor.py"
    if hashlib.sha256(actor_path.read_bytes()).hexdigest() != ACTOR_HASH:
        raise RuntimeError("fixed actor raw bytes differ")
    sys.path.insert(0, str(SCOPE))
    from runtime_limits import CpuRate, ExtendedLimits, OwnedJob
    from windows_actor import OwnershipError, WindowsOwnedActor, _creation_ticks

    record: dict[str, object] = {
        "started_at": now(), "data_mode": "harmless_native_diagnosis",
        "source_actor_sha256": ACTOR_HASH, "source_modified": False,
        "commands": [], "identity_cases": [], "children": [],
        "business_source_started": False, "service_credentials_loaded": False,
        "paid_requests": 0,
    }
    destination = RUN / "probe_incremental.json"
    if destination.exists():
        raise RuntimeError("diagnosis evidence already exists")

    def save() -> None:
        destination.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    job = OwnedJob()
    kernel = job.kernel
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    kernel.GetActiveProcessorCount.argtypes = [wintypes.WORD]
    kernel.GetActiveProcessorCount.restype = wintypes.DWORD
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    cpus = kernel.GetActiveProcessorCount(0xFFFF)
    if cpus <= 0:
        raise RuntimeError("logical processor count unavailable")
    limits = job.query(9, ExtendedLimits)
    limits.basic.flags |= 0x8
    limits.basic.active_limit = 10
    limits.job_memory = 1024**3
    rate = CpuRate(5, min(10000, 20000 // cpus))
    for kind, value in ((9, limits), (15, rate)):
        if not kernel.SetInformationJobObject(job.handle, kind, ctypes.byref(value), ctypes.sizeof(value)):
            raise OSError("diagnosis hard limits unavailable")
    actual = job.query(9, ExtendedLimits)
    actual_rate = job.query(15, CpuRate)
    if not (actual.basic.flags & 0x2308 == 0x2308 and actual.basic.active_limit == 10
            and actual.process_memory == 512 * 1024**2 and actual.job_memory == 1024**3
            and actual_rate.flags == 5 and actual_rate.rate * cpus <= 20000):
        raise RuntimeError("queried native limits differ")
    record["native_limits"] = {
        "active_limit": 10, "process_memory_bytes": actual.process_memory,
        "job_memory_bytes": actual.job_memory, "cpu_rate": actual_rate.rate,
        "logical_cpu_count": cpus, "cpu_cores_upper_bound": actual_rate.rate * cpus / 10000,
        "kill_on_close": bool(actual.basic.flags & 0x2000),
    }
    started_clock = time.monotonic()
    diagnostic_deadline = started_clock + 16
    dummy = subprocess.Popen(
        [sys.executable, "-I", "-B", "-c", "import time;time.sleep(18)"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000,
    )
    dummy_birth = _creation_ticks(kernel, int(dummy._handle))
    observer_birth = _creation_ticks(kernel, int(kernel.GetCurrentProcess()))
    foreign = kernel.CreateJobObjectW(None, None)
    if not foreign:
        raise OSError("foreign empty Job unavailable")
    record["observer"] = {"pid": os.getpid(), "parent_pid": os.getppid(), "creation_ticks": observer_birth}
    record["dummy"] = {"pid": dummy.pid, "parent_pid": os.getpid(), "creation_ticks": dummy_birth}
    save()

    def available(label: str) -> bool:
        if diagnostic_deadline - time.monotonic() >= 3.25:
            return True
        record["commands"].append({"label": label, "status": "not_run", "reason": "bounded_window_remaining_below_three_seconds"})
        save()
        return False

    def actor_case(label: str, birth: int, parent: int, handle: int, expected: str) -> None:
        if label in {"cold_wrong_ancestry", "actual_parent_membership"} and not available(label):
            return
        began = now()
        clock = time.monotonic()
        entry = {"label": label, "started_at": began, "expected": expected, "signal_sent": False}
        actor = None
        try:
            actor = WindowsOwnedActor(dummy.pid, birth, parent, handle)
            entry["status"] = "accepted"
            entry["held_exit_poll"] = actor.exited()
        except OwnershipError as error:
            entry["status"] = "refused"
            entry["error_label"] = str(error)
        except subprocess.TimeoutExpired:
            entry["status"] = "failed_unknown"
            entry["error_type"] = "TimeoutExpired"
            entry["fixed_cim_timeout_seconds"] = 3
        except Exception as error:
            entry["status"] = "failed_unknown"
            entry["error_type"] = type(error).__name__
        finally:
            if actor is not None:
                actor.close()
        entry.update(ended_at=now(), wall_seconds=time.monotonic() - clock, child_alive_after=dummy.poll() is None)
        record["identity_cases"].append(entry)
        save()

    def command_case(label: str, executable: str, script: str, parse_snapshot: bool) -> None:
        if not available(label):
            return
        entry = {"label": label, "started_at": now(), "requested_executable": executable,
                 "flags": ["-NoProfile", "-Command"], "creation_flags": 0,
                 "communicate_timeout_seconds": 3, "status": "unknown"}
        clock = time.monotonic()
        process = subprocess.Popen([executable, "-NoProfile", "-Command", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        entry["create_process_wall_seconds"] = time.monotonic() - clock
        process_birth = _creation_ticks(kernel, int(process._handle))
        membership = wintypes.BOOL()
        if not kernel.IsProcessInJob(int(process._handle), job.handle, ctypes.byref(membership)) or not membership.value:
            raise RuntimeError("diagnostic child is outside own Job")
        image_buffer = ctypes.create_unicode_buffer(32768)
        image_size = wintypes.DWORD(len(image_buffer))
        if not kernel.QueryFullProcessImageNameW(int(process._handle), 0, image_buffer, ctypes.byref(image_size)):
            raise RuntimeError("held executable image unavailable")
        entry.update(pid=process.pid, creation_ticks=process_birth, actual_executable_image=image_buffer.value)
        phase_clock = time.monotonic()
        try:
            stdout, stderr = process.communicate(timeout=3)
            entry["status"] = "completed" if process.returncode == 0 else "failed_exit"
        except subprocess.TimeoutExpired:
            entry["status"] = "timeout"
            process.kill()
            stdout, stderr = process.communicate(timeout=1)
        entry.update(communicate_and_cleanup_wall_seconds=time.monotonic() - phase_clock,
                     ended_at=now(), wall_seconds=time.monotonic() - clock,
                     exit_code=process.returncode, held_kernel_exit_ack=kernel.WaitForSingleObject(int(process._handle), 0) == 0,
                     stdout_bytes=len(stdout.encode()), stdout_sha256=hashlib.sha256(stdout.encode()).hexdigest(),
                     stderr_bytes=len(stderr.encode()), stderr_sha256=hashlib.sha256(stderr.encode()).hexdigest())
        created, exited, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
        if not kernel.GetProcessTimes(int(process._handle), ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel_time), ctypes.byref(user_time)):
            raise RuntimeError("held child CPU time unavailable")
        entry["child_cpu_seconds"] = ((kernel_time.dwHighDateTime << 32) + kernel_time.dwLowDateTime + (user_time.dwHighDateTime << 32) + user_time.dwLowDateTime) / 10_000_000
        if parse_snapshot and entry["status"] == "completed":
            rows = json.loads(stdout)
            if isinstance(rows, dict):
                rows = [rows]
            selected = [row for row in rows if row.get("pid") in {os.getpid(), dummy.pid}]
            entry["process_row_count"] = len(rows)
            entry["owned_parent_child_snapshot"] = selected
            entry["owned_child_parent_matches"] = any(row.get("pid") == dummy.pid and row.get("parent") == os.getpid() for row in selected)
        record["commands"].append(entry)
        save()

    try:
        actor_case("wrong_birth", dummy_birth + 1, os.getpid(), int(job.handle), "refused")
        actor_case("foreign_job", dummy_birth, os.getpid(), int(foreign), "refused")
        actor_case("cold_wrong_ancestry", dummy_birth, os.getppid(), int(job.handle), "refused")
        command_case("system_powershell_noop", "powershell.exe", "[Console]::Write('ok')", False)
        actor_case("actual_parent_membership", dummy_birth, os.getpid(), int(job.handle), "accepted")
        targeted_script = FIXED_SCRIPT.replace("Get-CimInstance Win32_Process", f"Get-CimInstance Win32_Process -Filter 'ProcessId={os.getpid()} OR ProcessId={dummy.pid}'")
        command_case("system_targeted_cim", "powershell.exe", targeted_script, True)
        command_case("bundled_pwsh_same_full_cim", PWSH, FIXED_SCRIPT, True)
        command_case("system_exact_full_cim_warm", "powershell.exe", FIXED_SCRIPT, True)
    finally:
        if _creation_ticks(kernel, int(dummy._handle)) != dummy_birth:
            raise RuntimeError("owned dummy generation changed before cleanup")
        member = wintypes.BOOL()
        if not kernel.IsProcessInJob(int(dummy._handle), job.handle, ctypes.byref(member)) or not member.value:
            raise RuntimeError("owned dummy Job identity changed before cleanup")
        if dummy.poll() is None:
            dummy.terminate()
        dummy.wait(timeout=1)
        record["children"].append({"pid": dummy.pid, "creation_ticks": dummy_birth, "exit_code": dummy.returncode,
                                  "held_kernel_exit_ack": kernel.WaitForSingleObject(int(dummy._handle), 0) == 0})
        if not kernel.CloseHandle(foreign):
            raise OSError("foreign Job close unavailable")
        save()
    early = subprocess.Popen([sys.executable, "-I", "-B", "-c", "raise SystemExit(23)"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
    early_birth = _creation_ticks(kernel, int(early._handle))
    early.wait(timeout=1)
    record["children"].append({"pid": early.pid, "creation_ticks": early_birth, "exit_code": early.returncode,
                              "held_kernel_exit_ack": kernel.WaitForSingleObject(int(early._handle), 0) == 0,
                              "held_birth_unchanged": _creation_ticks(kernel, int(early._handle)) == early_birth})
    record.update(ended_at=now(), wall_seconds=time.monotonic() - started_clock, job_usage_after=job.usage(),
                  source_after_sha256=hashlib.sha256(actor_path.read_bytes()).hexdigest())
    save()
    if early.returncode != 23 or record["job_usage_after"]["active_processes"] != 1:
        return 1
    unknown = any(row.get("status") == "failed_unknown" for row in record["identity_cases"])
    failed_expected = any(row.get("status") != row["expected"] for row in record["identity_cases"])
    print(json.dumps({"diagnosis_written": True, "identity_unknown": unknown, "actual_exit23": early.returncode == 23}))
    return int(unknown or failed_expected)


if __name__ == "__main__":
    raise SystemExit(main())
