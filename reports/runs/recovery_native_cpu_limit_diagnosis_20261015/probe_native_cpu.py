"""Bounded Windows diagnosis; all targets are disposable children from this driver."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
PYTHON = Path("D:/wt/r06-feeds/backend/.venv/Scripts/python.exe")
KERNEL = ctypes.WinDLL("kernel32", use_last_error=True)
KERNEL.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
KERNEL.OpenProcess.restype = wintypes.HANDLE
KERNEL.GetCurrentProcess.restype = wintypes.HANDLE
KERNEL.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.c_void_p] * 4
KERNEL.DuplicateHandle.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
KERNEL.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
KERNEL.CloseHandle.argtypes = [wintypes.HANDLE]
KERNEL.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]


class Accounting(ctypes.Structure):
    _fields_ = [(name, ctypes.c_longlong) for name in ("user", "kernel", "period_user", "period_kernel")] + [(name, wintypes.DWORD) for name in ("faults", "processes", "active", "terminated")]


class Entry(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t), ("module", wintypes.DWORD), ("threads", wintypes.DWORD), ("parent", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD), ("executable", wintypes.WCHAR * 260)]


KERNEL.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
KERNEL.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
KERNEL.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
KERNEL.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]


EXACT = "from ai_intel.infrastructure.process_limits import bound_process_resources\nhandle = bound_process_resources(memory_bytes=100*1024**2,cpu_seconds=1)\nprint('LIMIT_APPLIED',flush=True)\nwhile True:\n    pass\n"
INSTRUMENTED = EXACT.replace("print('LIMIT_APPLIED',flush=True)", "import json,os\nprint('LIMIT_APPLIED',flush=True)\nprint('DIAG '+json.dumps({'pid':os.getpid(),'job_handle':handle}),flush=True)")


def descendants(root_pid: int) -> list[dict[str, object]]:
    snapshot = KERNEL.CreateToolhelp32Snapshot(2, 0)
    entry = Entry()
    entry.size = ctypes.sizeof(entry)
    entries = []
    try:
        valid = KERNEL.Process32FirstW(snapshot, ctypes.byref(entry))
        while valid:
            entries.append({"pid": entry.pid, "parent": entry.parent, "executable": entry.executable})
            valid = KERNEL.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        KERNEL.CloseHandle(snapshot)
    selected = {root_pid}
    for _ in range(5):
        selected.update(int(item["pid"]) for item in entries if item["parent"] in selected)
    return [item for item in entries if item["pid"] in selected]


def process_times(handle: int) -> dict[str, float | int]:
    values = [ctypes.c_ulonglong() for _ in range(4)]
    if not KERNEL.GetProcessTimes(handle, *(ctypes.byref(value) for value in values)):
        return {"error": ctypes.get_last_error()}
    return {"user_seconds": values[3].value / 10_000_000, "kernel_seconds": values[2].value / 10_000_000}


def job_accounting(handle: int) -> dict[str, object]:
    accounting = Accounting()
    if not KERNEL.QueryInformationJobObject(handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None):
        return {"error": ctypes.get_last_error()}
    return {"user_seconds": accounting.user / 10_000_000, "kernel_seconds": accounting.kernel / 10_000_000, "processes": accounting.processes, "active": accounting.active, "terminated": accounting.terminated}


def stream_lines(stream, values: list[str], notifications: queue.Queue) -> None:
    for line in iter(stream.readline, b""):
        decoded = line.decode("utf-8", errors="replace")
        values.append(decoded)
        if decoded.startswith("DIAG "):
            notifications.put(json.loads(decoded[5:]))
    stream.close()


def attempt(number: int, mode: str) -> dict[str, object]:
    started = time.perf_counter()
    command = [str(PYTHON), "-c", EXACT if mode == "exact" else INSTRUMENTED]
    result = {"attempt": number, "mode": mode, "started_at": datetime.now(timezone.utc).isoformat(), "command": command, "timeout_seconds": 8, "samples": []}
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "backend/src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    process = subprocess.Popen(command, cwd=ROOT / "backend", env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    notifications = queue.Queue()
    stdout, stderr = [], []
    readers = [threading.Thread(target=stream_lines, args=(stream, values, notifications), daemon=True) for stream, values in ((process.stdout, stdout), (process.stderr, stderr))]
    for reader in readers:
        reader.start()
    handles = {process.pid: int(process._handle)}
    owned_handles = []
    job_handle = None
    observed_tree = []
    try:
        while True:
            wall = time.perf_counter() - started
            try:
                metadata = notifications.get_nowait()
                result["child_metadata"] = metadata
                child_handle = KERNEL.OpenProcess(0x0040 | 0x1000 | 0x0001, False, metadata["pid"])
                if child_handle:
                    handles[metadata["pid"]] = int(child_handle)
                    owned_handles.append(child_handle)
                    duplicated = wintypes.HANDLE()
                    if KERNEL.DuplicateHandle(child_handle, metadata["job_handle"], KERNEL.GetCurrentProcess(), ctypes.byref(duplicated), 0, False, 2):
                        job_handle = duplicated.value
                        owned_handles.append(job_handle)
                    else:
                        result["duplicate_error"] = ctypes.get_last_error()
            except queue.Empty:
                pass
            tree = descendants(process.pid)
            for item in tree:
                if item not in observed_tree:
                    observed_tree.append(item)
                pid = int(item["pid"])
                if pid not in handles:
                    handle = KERNEL.OpenProcess(0x1000 | 0x0001, False, pid)
                    if handle:
                        handles[pid] = int(handle)
                        owned_handles.append(handle)
            sample = {"wall_seconds": wall, "processes": {str(pid): process_times(handle) for pid, handle in handles.items()}, "launcher_returncode": process.poll(), "stdout_reader_alive": readers[0].is_alive(), "stderr_reader_alive": readers[1].is_alive()}
            if job_handle:
                sample["job"] = job_accounting(job_handle)
            result["samples"].append(sample)
            if process.poll() is not None and not any(reader.is_alive() for reader in readers):
                result["outcome"] = "exited"
                break
            if wall >= 8:
                result["outcome"] = "timeout"
                result["pre_cleanup_returncode"] = process.poll()
                for pid, handle in reversed(list(handles.items())):
                    if pid != process.pid:
                        KERNEL.TerminateProcess(handle, 77)
                if process.poll() is None:
                    process.kill()
                break
            time.sleep(min(0.2, max(0, 8 - wall)))
        process.wait(timeout=2)
        for reader in readers:
            reader.join(timeout=1)
        result.update({"wall_seconds": time.perf_counter() - started, "returncode": process.returncode, "stdout": "".join(stdout), "stderr": "".join(stderr), "observed_tree": observed_tree, "final_process_times": {str(pid): process_times(handle) for pid, handle in handles.items()}})
        if job_handle:
            result["final_job"] = job_accounting(job_handle)
    finally:
        for handle in owned_handles:
            KERNEL.CloseHandle(handle)
    (OUTPUT / f"attempt_{number:02d}_{mode}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: result.get(key) for key in ("attempt", "mode", "outcome", "wall_seconds", "returncode", "final_job", "final_process_times")}), flush=True)
    return result


def main() -> None:
    started = time.perf_counter()
    results = []
    for number in range(1, 5):
        results.append(attempt(number, "exact"))
    for number in range(5, 9):
        results.append(attempt(number, "instrumented"))
    with ThreadPoolExecutor(max_workers=4) as executor:
        results.extend(executor.map(lambda number: attempt(number, "parallel4"), range(9, 13)))
    summary = {"attempts": len(results), "wall_seconds": time.perf_counter() - started, "deadline_seconds": 180, "timeouts": sum(item["outcome"] == "timeout" for item in results), "max_target_processes": 4, "per_target_memory_bytes": 100 * 1024**2, "per_target_cpu_seconds": 1, "python": str(PYTHON), "source_root": str(ROOT / "backend/src"), "results": [{key: item.get(key) for key in ("attempt", "mode", "outcome", "wall_seconds", "returncode", "final_job", "final_process_times")} for item in results]}
    (OUTPUT / "probe_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}), flush=True)


if __name__ == "__main__":
    main()
