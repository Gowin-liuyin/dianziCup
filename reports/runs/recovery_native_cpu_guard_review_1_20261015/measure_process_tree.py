"""Measure the live worker, guardian and console helpers for four short local runs."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import datetime
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

from probe_review_windows import KERNEL, ROOT, OUTPUT, collect_lines, sample


class ProcessEntry(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD),
               ("heap", ctypes.c_size_t), ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
               ("parent", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD),
               ("executable", wintypes.WCHAR * 260)]


KERNEL.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
KERNEL.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
KERNEL.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
KERNEL.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]


def tree(root_pid: int) -> list[dict[str, object]]:
    snapshot = KERNEL.CreateToolhelp32Snapshot(2, 0)
    entry = ProcessEntry()
    entry.size = ctypes.sizeof(entry)
    entries: list[dict[str, object]] = []
    try:
        valid = KERNEL.Process32FirstW(snapshot, ctypes.byref(entry))
        while valid:
            entries.append({"pid": entry.pid, "parent": entry.parent,
                            "executable": entry.executable})
            valid = KERNEL.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        KERNEL.CloseHandle(snapshot)
    selected = {root_pid}
    for _ in range(5):
        selected.update(int(item["pid"]) for item in entries if item["parent"] in selected)
    return [item for item in entries if item["pid"] in selected]


def run_measurement(name: str, baseline: bool) -> dict[str, object]:
    imports = (
        "import importlib.util\nspec=importlib.util.spec_from_file_location('baseline',"
        f"{str(OUTPUT / 'baseline_process_limits.py')!r})\n"
        "limits=importlib.util.module_from_spec(spec)\nspec.loader.exec_module(limits)\n"
        if baseline else "from ai_intel.infrastructure import process_limits as limits\n"
    )
    code = (
        "import time,os,json\n" + imports
        + "job=limits.bound_process_resources(memory_bytes=100*1024**2,cpu_seconds=5)\n"
        "print('READY '+json.dumps({'worker_pid':os.getpid()}),flush=True)\n"
        "time.sleep(1)\nprint('RESULT_OK',flush=True)\n"
    )
    started = time.perf_counter()
    result: dict[str, object] = {"name": name, "started_at": datetime.now().astimezone().isoformat(),
                               "samples": [], "command": [sys.executable, "-B", "-c", code]}
    process = subprocess.Popen(result["command"], cwd=ROOT / "backend", stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    stdout: list[str] = []
    stderr: list[str] = []
    messages: queue.Queue[dict[str, object]] = queue.Queue()
    readers = [threading.Thread(target=collect_lines, args=(stream, lines, messages), daemon=True)
               for stream, lines in ((process.stdout, stdout), (process.stderr, stderr))]
    for reader in readers:
        reader.start()
    handles: dict[int, int] = {}
    metadata: dict[str, object] = {}
    try:
        while process.poll() is None and time.perf_counter() - started < 5:
            try:
                metadata.update(messages.get_nowait())
            except queue.Empty:
                pass
            processes = tree(process.pid)
            for item in processes:
                pid = int(item["pid"])
                if pid not in handles:
                    handle = KERNEL.OpenProcess(0x100000 | 0x1000 | 0x10 | 0x1, False, pid)
                    if handle:
                        handles[pid] = int(handle)
                item["metrics"] = sample(handles[pid]) if pid in handles else {
                    "error": ctypes.get_last_error(), "cost": "unknown",
                }
            result["samples"].append({"wall_seconds": time.perf_counter() - started,
                                      "processes": processes})
            time.sleep(0.1)
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)
        for reader in readers:
            reader.join(timeout=1)
        result.update(returncode=process.returncode, stdout=stdout, stderr=stderr, metadata=metadata,
                      final={str(pid): sample(handle) for pid, handle in handles.items()},
                      wall_seconds=time.perf_counter() - started,
                      completed_at=datetime.now().astimezone().isoformat())
    finally:
        for handle in handles.values():
            if KERNEL.WaitForSingleObject(handle, 0) != 0:
                KERNEL.TerminateProcess(handle, 77)
            KERNEL.CloseHandle(handle)
    return result


results = [run_measurement(f"{'baseline' if old else 'guard'}_{index}", old)
           for old in (True, False) for index in range(2)]
(OUTPUT / "process_tree_memory.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print(json.dumps({"runs": len(results), "returncodes": [item["returncode"] for item in results]}))
