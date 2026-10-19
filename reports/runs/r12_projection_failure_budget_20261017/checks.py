"""Bound owned offline commands without opening external resources or credentials."""

import ctypes
import hashlib
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
SOURCE_PATHS = (
    "backend/src/ai_intel/retrieval/opensearch_client.py",
    "backend/src/ai_intel/retrieval/runtime_policy.py",
    "backend/src/ai_intel/retrieval/indexing.py",
    "backend/src/ai_intel/infrastructure/settings.py",
    "backend/tests/contract/test_r12_projection_total_budget_fix2.py",
    "backend/tests/contract/test_r12_projection_failure_budget.py",
)


class ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("size", wintypes.DWORD),
        ("usage", wintypes.DWORD),
        ("pid", wintypes.DWORD),
        ("heap", ctypes.c_size_t),
        ("module", wintypes.DWORD),
        ("threads", wintypes.DWORD),
        ("parent", wintypes.DWORD),
        ("priority", wintypes.LONG),
        ("flags", wintypes.DWORD),
        ("name", wintypes.WCHAR * 260),
    ]


def windows_processes():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    entry = ProcessEntry()
    entry.size = ctypes.sizeof(entry)
    rows = {}
    try:
        present = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while present:
            rows[entry.pid] = entry.parent
            present = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    owned = {os.getpid()}
    while True:
        added = {pid for pid, parent in rows.items() if parent in owned} - owned
        if not added:
            return owned
        owned.update(added)


def birth(handle):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.c_void_p] * 4
    times = [ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in times)):
        raise OSError("owned process birth unavailable")
    return times[0].value


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    label, *arguments = sys.argv[1:]
    assert label.replace("_", "").isalnum() and not (RUN / (label + ".json")).exists()
    environment = dict(
        os.environ,
        PYTHONPATH=str(ROOT / "backend/src") + os.pathsep + str(ROOT / "backend/tests/integration"),
        PYTHONUTF8="1",
    )
    command = arguments if arguments[0] == "wsl" else [sys.executable, *arguments]
    started = datetime.now(UTC).isoformat()
    with (RUN / (label + ".log")).open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command, cwd=ROOT / "backend", env=environment, stdout=log, stderr=subprocess.STDOUT
        )
        owner = {"pid": process.pid, "birth_ticks": birth(process._handle)}
        peak = len(windows_processes())
        deadline = time.monotonic() + 58
        stopped = None
        while process.poll() is None:
            peak = max(peak, len(windows_processes()))
            if peak > 10 or time.monotonic() >= deadline:
                stopped = "process_cap" if peak > 10 else "wall_cap"
                assert birth(process._handle) == owner["birth_ticks"]
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=2,
                    check=False,
                )
                break
            time.sleep(0.05)
        code = process.wait(timeout=2)
    receipt = {
        "argv": command,
        "cwd": str(ROOT / "backend"),
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
        "exit_code": code,
        "windows_root": owner,
        "windows_process_peak": peak,
        "wall_cap_seconds": 58,
        "process_cap": 10,
        "wsl_processes": "0 for offline commands; CBM separately sampled",
        "stopped": stopped,
        "remaining_descendants": sorted(windows_processes() - {os.getpid()}),
        "source_sha256": {
            relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            for relative in SOURCE_PATHS
            if (ROOT / relative).exists()
        },
        "log_sha256": hashlib.sha256((RUN / (label + ".log")).read_bytes()).hexdigest(),
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
    }
    (RUN / (label + ".json")).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt))
    print((RUN / (label + ".log")).read_text(encoding="utf-8", errors="replace")[-1800:])
    return code


if __name__ == "__main__":
    raise SystemExit(main())
