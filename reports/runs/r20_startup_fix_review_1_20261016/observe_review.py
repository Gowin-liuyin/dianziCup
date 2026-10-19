"""Observe only this review process' descendants while retaining original test assertions."""

from __future__ import annotations

import ctypes
import datetime
import json
import os
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

import _winapi
import pytest

RUN = Path(__file__).resolve().parent
KERNEL = ctypes.WinDLL("kernel32", use_last_error=True)
KERNEL.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
KERNEL.OpenProcess.restype = wintypes.HANDLE
KERNEL.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.c_void_p] * 4
KERNEL.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
KERNEL.CloseHandle.argtypes = [wintypes.HANDLE]
KERNEL.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
KERNEL.CreateToolhelp32Snapshot.restype = wintypes.HANDLE


class ProcessEntry(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t), ("module", wintypes.DWORD), ("threads", wintypes.DWORD), ("parent_pid", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD), ("name", wintypes.WCHAR * 260)]


KERNEL.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
KERNEL.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]


def cpu_snapshot(handle: int) -> dict[str, float]:
    fields = [ctypes.c_ulonglong() for _ in range(4)]
    if not KERNEL.GetProcessTimes(handle, *(ctypes.byref(value) for value in fields)):
        raise OSError("review process CPU query unavailable")
    return {"kernel_cpu_seconds": fields[2].value / 10_000_000, "user_cpu_seconds": fields[3].value / 10_000_000, "total_cpu_seconds": (fields[2].value + fields[3].value) / 10_000_000}


class DescendantObserver:
    def __init__(self) -> None:
        self.records: dict[int, dict[str, object]] = {}
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.scan_loop, daemon=True)
        self.original_create_process = _winapi.CreateProcess
        self.started = time.monotonic()
        self.current_case = "explicit_review_harness"

    def add(self, pid: int, parent: int, *, command: str | None = None) -> None:
        with self.lock:
            if pid in self.records:
                return
            handle = KERNEL.OpenProcess(0x100000 | 0x1000, False, pid)
            if not handle:
                return
            self.records[pid] = {"pid": pid, "parent_pid": parent, "handle": handle, "first_seen_wall_seconds": time.monotonic() - self.started, "actual_case_id": self.current_case, "root_child": parent == os.getpid(), "command": command}

    def create_process(self, *args: object, **kwargs: object) -> object:
        result = self.original_create_process(*args, **kwargs)
        self.add(result[2], os.getpid(), command=args[1])
        return result

    def scan_once(self) -> None:
        snapshot = KERNEL.CreateToolhelp32Snapshot(2, 0)
        if snapshot == ctypes.c_void_p(-1).value:
            raise OSError("review descendant snapshot unavailable")
        entry = ProcessEntry()
        entry.size = ctypes.sizeof(entry)
        parents: dict[int, int] = {}
        try:
            found = KERNEL.Process32FirstW(snapshot, ctypes.byref(entry))
            while found:
                parents[entry.pid] = entry.parent_pid
                found = KERNEL.Process32NextW(snapshot, ctypes.byref(entry))
        finally:
            KERNEL.CloseHandle(snapshot)
        owned = {os.getpid(), *self.records}
        changed = True
        while changed:
            changed = False
            for pid, parent in parents.items():
                if parent in owned and pid not in owned:
                    self.add(pid, parent)
                    owned.add(pid)
                    changed = True

    def scan_loop(self) -> None:
        while not self.stop.wait(0.01):
            self.scan_once()

    def __enter__(self) -> DescendantObserver:
        _winapi.CreateProcess = self.create_process
        self.thread.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.scan_once()
        self.stop.set()
        self.thread.join(timeout=1)
        _winapi.CreateProcess = self.original_create_process
        for record in self.records.values():
            handle = record.pop("handle")
            record["signaled"] = KERNEL.WaitForSingleObject(handle, 1000) == 0
            record["final_cpu"] = cpu_snapshot(handle)
            KERNEL.CloseHandle(handle)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item: object) -> object:
        self.current_case = item.nodeid
        yield


def run() -> None:
    name, *arguments = sys.argv[1:]
    with DescendantObserver() as observer:
        exit_code = pytest.main(arguments, plugins=[observer])
    payload = {"command_exit_code": int(exit_code), "records": list(observer.records.values()), "observed_descendant_cpu_seconds": sum(record["final_cpu"]["total_cpu_seconds"] for record in observer.records.values()), "tree_all_signaled": all(record["signaled"] for record in observer.records.values()), "scanner_interval_seconds": 0.01, "scanner_limitation": "A descendant that exits between snapshots before an OpenProcess handle is retained may be missed; root CreateProcess children are also captured synchronously.", "ended_shanghai": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="seconds")}
    (RUN / f"{name}.observations.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    raise SystemExit(exit_code)


if __name__ == "__main__":
    run()
