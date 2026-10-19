"""Query handles only for a launched process and verified descendants."""

from __future__ import annotations

import ctypes
import datetime
import json
import os
import subprocess
import threading
import time
from ctypes import wintypes
from pathlib import Path

KERNEL = ctypes.WinDLL("kernel32", use_last_error=True)
KERNEL.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
KERNEL.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
KERNEL.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
KERNEL.OpenProcess.restype = wintypes.HANDLE
KERNEL.CloseHandle.argtypes = [wintypes.HANDLE]
KERNEL.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
KERNEL.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.c_void_p] * 4
KERNEL.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
KERNEL.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]


class ProcessEntry(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD),
                ("heap", ctypes.c_size_t), ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
                ("parent_pid", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD),
                ("executable", wintypes.WCHAR * 260)]


KERNEL.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
KERNEL.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]


def snapshot() -> list[dict]:
    handle = KERNEL.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    rows = []
    try:
        entry = ProcessEntry()
        entry.size = ctypes.sizeof(entry)
        valid = KERNEL.Process32FirstW(handle, ctypes.byref(entry))
        while valid:
            rows.append({"pid": entry.pid, "parent_pid": entry.parent_pid, "executable": entry.executable})
            valid = KERNEL.Process32NextW(handle, ctypes.byref(entry))
    finally:
        KERNEL.CloseHandle(handle)
    return rows


def process_times(handle: int) -> dict:
    values = [ctypes.c_ulonglong() for _ in range(4)]
    ctypes.set_last_error(0)
    success = KERNEL.GetProcessTimes(handle, *(ctypes.byref(value) for value in values))
    error = ctypes.get_last_error()
    exit_code = wintypes.DWORD()
    exit_success = KERNEL.GetExitCodeProcess(handle, ctypes.byref(exit_code))
    return {"success": bool(success), "win32_error": error,
            "creation_ticks": values[0].value, "exit_ticks": values[1].value,
            "kernel_ticks": values[2].value, "user_ticks": values[3].value,
            "cpu_seconds": (values[2].value + values[3].value) / 10_000_000,
            "process_exit_code": exit_code.value if exit_success else None,
            "signaled": KERNEL.WaitForSingleObject(handle, 0) == 0}


def observe(name: str, command: list[str], *, cwd: Path, run: Path,
            environment: dict[str, str] | None = None, timeout: float = 8,
            input_bytes: bytes | None = None) -> dict:
    started = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    begin = time.monotonic()
    processes = {}
    errors = []
    samples = []
    timed_out = False
    with subprocess.Popen(command, cwd=cwd, env=environment, stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE) as root:
        output_buffers = {"stdout": bytearray(), "stderr": bytearray()}
        def drain(stream, buffer):
            while chunk := stream.read(4096):
                buffer.extend(chunk)
        readers = [threading.Thread(target=drain, args=(getattr(root, kind), output_buffers[kind]), daemon=True)
                   for kind in ("stdout", "stderr")]
        for reader in readers:
            reader.start()
        if input_bytes is not None:
            def write_input():
                try:
                    root.stdin.write(input_bytes)
                    root.stdin.close()
                except BrokenPipeError:
                    pass
            threading.Thread(target=write_input, daemon=True).start()
        root_handle = KERNEL.OpenProcess(0x100000 | 0x1000 | 1, False, root.pid)
        if not root_handle:
            raise ctypes.WinError(ctypes.get_last_error())
        processes[root.pid] = {"pid": root.pid, "parent_pid": os.getpid(), "executable": command[0], "handle": root_handle,
                               "discovered_wall": 0.0, "initial": process_times(root_handle)}
        try:
            while True:
                elapsed = time.monotonic() - begin
                for row in snapshot():
                    if row["pid"] in processes or row["parent_pid"] not in processes:
                        continue
                    handle = KERNEL.OpenProcess(0x100000 | 0x1000 | 1, False, row["pid"])
                    if not handle:
                        errors.append({**row, "operation": "OpenProcess", "win32_error": ctypes.get_last_error()})
                        continue
                    initial = process_times(handle)
                    if not initial["success"] or initial["creation_ticks"] < processes[row["parent_pid"]]["initial"]["creation_ticks"]:
                        KERNEL.CloseHandle(handle)
                        errors.append({**row, "operation": "creation identity guard"})
                        continue
                    processes[row["pid"]] = {**row, "handle": handle, "discovered_wall": elapsed, "initial": initial}
                rows = {str(pid): process_times(row["handle"]) for pid, row in processes.items()}
                samples.append({"wall_seconds": elapsed, "processes": rows})
                if all(row["signaled"] for row in rows.values()):
                    break
                if elapsed >= timeout:
                    timed_out = True
                    for row in reversed(list(processes.values())):
                        if not process_times(row["handle"])["signaled"]:
                            KERNEL.TerminateProcess(row["handle"], 98)
                    break
                time.sleep(0.005)
            root.wait(timeout=1)
            for reader in readers:
                reader.join(timeout=1)
            stdout, stderr = bytes(output_buffers["stdout"]), bytes(output_buffers["stderr"])
            for row in processes.values():
                KERNEL.WaitForSingleObject(row["handle"], 1000)
                row["final"] = process_times(row["handle"])
                KERNEL.CloseHandle(row.pop("handle"))
        finally:
            for row in processes.values():
                if "handle" in row:
                    if not process_times(row["handle"])["signaled"]:
                        KERNEL.TerminateProcess(row["handle"], 98)
                    KERNEL.CloseHandle(row.pop("handle"))
    result = {"sample_id": name, "argv": command, "cwd": str(cwd), "started_at": started,
              "ended_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
              "wall_seconds": time.monotonic() - begin, "exit_code": root.returncode, "outer_timeout": timed_out,
              "stdout": stdout.decode("utf-8", "replace"), "stderr": stderr.decode("utf-8", "replace"),
              "observed_process_count": len(processes), "observed_cpu_seconds": sum(row["final"]["cpu_seconds"] for row in processes.values()),
              "processes": list(processes.values()), "discovery_errors": errors, "samples": samples}
    (run / f"{name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("sample_id", "exit_code", "wall_seconds", "outer_timeout", "observed_process_count", "observed_cpu_seconds")}))
    return result
