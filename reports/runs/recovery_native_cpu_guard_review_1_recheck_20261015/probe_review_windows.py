"""Real bounded children test CPU accounting, lifecycle and injected guardian failures."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import ctypes
from ctypes import wintypes
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import queue
import statistics
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
KERNEL = ctypes.WinDLL("kernel32", use_last_error=True)
KERNEL.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
KERNEL.OpenProcess.restype = wintypes.HANDLE
KERNEL.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.c_void_p] * 4
KERNEL.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
KERNEL.WaitForSingleObject.restype = wintypes.DWORD
KERNEL.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
KERNEL.CloseHandle.argtypes = [wintypes.HANDLE]


class MemoryCounters(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in (
            "peak_working_set", "working_set", "peak_paged", "paged", "peak_nonpaged",
            "nonpaged", "pagefile", "peak_pagefile", "private",
        )
    ]


PSAPI = ctypes.WinDLL("psapi", use_last_error=True)
PSAPI.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]


def sample(handle: int) -> dict[str, object]:
    values = [ctypes.c_ulonglong() for _ in range(4)]
    result: dict[str, object] = {"signaled": KERNEL.WaitForSingleObject(handle, 0) == 0}
    if KERNEL.GetProcessTimes(handle, *(ctypes.byref(value) for value in values)):
        result.update(user_seconds=values[3].value / 10_000_000,
                      kernel_seconds=values[2].value / 10_000_000,
                      cpu_seconds=(values[3].value + values[2].value) / 10_000_000)
    counters = MemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    if PSAPI.GetProcessMemoryInfo(handle, ctypes.byref(counters), ctypes.sizeof(counters)):
        result.update(private_bytes=counters.private, working_set_bytes=counters.working_set)
    return result


def collect_lines(stream, lines: list[str], messages: queue.Queue[dict[str, object]]) -> None:
    for raw in iter(stream.readline, b""):
        line = raw.decode("utf-8", errors="replace").rstrip()
        lines.append(line)
        if line.startswith("READY ") or line.startswith("LEAF "):
            messages.put(json.loads(line.split(" ", 1)[1]))
    stream.close()


def attempt(name: str, body: str, *, baseline: bool = False, fault: str | None = None,
            cpu_seconds: int = 1) -> dict[str, object]:
    imports = (
        f"import importlib.util\nspec=importlib.util.spec_from_file_location('baseline',"
        f"{str(OUTPUT / 'baseline_process_limits.py')!r})\n"
        "limits=importlib.util.module_from_spec(spec)\nspec.loader.exec_module(limits)\n"
        if baseline else "from ai_intel.infrastructure import process_limits as limits\n"
    )
    injection = ""
    if fault == "abrupt_exit":
        injection = (
            "limits._WINDOWS_CPU_GUARD_CODE=limits._WINDOWS_CPU_GUARD_CODE.replace("
            "'    while True:\\n','    import time,os\\n    time.sleep(0.4)\\n"
            "    os._exit(99)\\n    while True:\\n')\n"
        )
    elif fault == "handled_exception":
        injection = (
            "limits._WINDOWS_CPU_GUARD_CODE=limits._WINDOWS_CPU_GUARD_CODE.replace("
            "'    while True:\\n','    import time\\n    time.sleep(0.4)\\n"
            "    raise RuntimeError(\\\"injected accounting error\\\")\\n    while True:\\n')\n"
        )
    code = (
        "import os,json,time,sys,subprocess,ctypes\n" + imports + injection
        + "started=time.perf_counter(); before=time.process_time()\n"
        + f"job_handle=limits.bound_process_resources(memory_bytes=100*1024**2,cpu_seconds={cpu_seconds})\n"
        + "print('READY '+json.dumps({'worker_pid':os.getpid(),"
        "'guard_pid':limits._WINDOWS_CPU_GUARDS[0].pid if hasattr(limits,'_WINDOWS_CPU_GUARDS') else None,"
        "'limit_wall_seconds':time.perf_counter()-started,"
        "'limit_cpu_seconds':time.process_time()-before}),flush=True)\n" + body
    )
    command = [sys.executable, "-B", "-c", code]
    result: dict[str, object] = {
        "name": name, "command": command, "timeout_seconds": 8,
        "cpu_budget_seconds": cpu_seconds, "memory_bytes": 100 * 1024**2,
        "started_at": datetime.now().astimezone().isoformat(), "samples": [], "fault": fault,
    }
    started = time.perf_counter()
    process = subprocess.Popen(command, cwd=ROOT / "backend", stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    stdout: list[str] = []
    stderr: list[str] = []
    messages: queue.Queue[dict[str, object]] = queue.Queue()
    readers = [threading.Thread(target=collect_lines, args=(stream, lines, messages), daemon=True)
               for stream, lines in ((process.stdout, stdout), (process.stderr, stderr))]
    for reader in readers:
        reader.start()
    handles: dict[str, int] = {}
    try:
        while True:
            try:
                while True:
                    metadata = messages.get_nowait()
                    result.setdefault("metadata", []).append(metadata)
                    for key in ("worker_pid", "guard_pid", "leaf_pid"):
                        if metadata.get(key) is not None:
                            handle = KERNEL.OpenProcess(0x100000 | 0x1000 | 0x10 | 0x1,
                                                        False, int(metadata[key]))
                            if handle:
                                handles[key] = int(handle)
            except queue.Empty:
                pass
            elapsed = time.perf_counter() - started
            result["samples"].append({"wall_seconds": elapsed,
                                      "processes": {key: sample(handle) for key, handle in handles.items()}})
            if process.poll() is not None and all(not reader.is_alive() for reader in readers):
                result["outcome"] = "exited"
                break
            if elapsed >= 8:
                result["outcome"] = "timeout"
                for handle in handles.values():
                    if KERNEL.WaitForSingleObject(handle, 0) != 0:
                        KERNEL.TerminateProcess(handle, 77)
                if process.poll() is None:
                    process.kill()
                break
            time.sleep(0.025)
        process.wait(timeout=2)
        for reader in readers:
            reader.join(timeout=1)
        for handle in handles.values():
            KERNEL.WaitForSingleObject(handle, 1000)
        result.update(returncode=process.returncode, wall_seconds=time.perf_counter() - started,
                      stdout=stdout, stderr=stderr,
                      final={key: sample(handle) for key, handle in handles.items()},
                      completed_at=datetime.now().astimezone().isoformat())
    finally:
        for handle in handles.values():
            if KERNEL.WaitForSingleObject(handle, 0) != 0:
                KERNEL.TerminateProcess(handle, 77)
            KERNEL.CloseHandle(handle)
    (OUTPUT / f"{name}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: result.get(key) for key in
                      ("name", "outcome", "returncode", "wall_seconds", "final", "stdout")}), flush=True)
    return result


def main() -> None:
    baseline = subprocess.check_output(
        ["git", "show", "45ee2d0d3bb007f0dbf5d753ee4b8c06d322758b:backend/src/ai_intel/infrastructure/process_limits.py"],
        cwd=ROOT,
    )
    (OUTPUT / "baseline_process_limits.py").write_bytes(baseline)
    results = []
    native = "import hashlib\nhashlib.pbkdf2_hmac('sha256',b'bounded',b'native',100_000_000)\n"
    busy = "sys.setswitchinterval(60)\nwhile True:\n    pass\n"
    for name, body in (("sample_gil", busy), ("sample_native", native)):
        results.append(attempt(name, body))
    with ThreadPoolExecutor(max_workers=2) as executor:
        results.extend(executor.map(lambda i: attempt(f"concurrent_native_{i}", native), range(2)))
    for mode in ("abrupt_exit", "handled_exception"):
        for index in range(2):
            bounded_hot = (
                "sys.setswitchinterval(60)\n"
                "while time.process_time()<2.25:\n    pass\n"
                "print('WORK_COMPLETED_AFTER_BUDGET',time.process_time(),flush=True)\n"
            )
            results.append(attempt(f"guard_{mode}_{index}", bounded_hot, fault=mode))
    leaf_setup = (
        "leaf=subprocess.Popen([os.path.join(sys.base_prefix,'python.exe'),'-I','-S','-c',"
        "'import time;time.sleep(30)'],creationflags=0x08000000)\n"
        "print('LEAF '+json.dumps({'leaf_pid':leaf.pid}),flush=True)\ntime.sleep(0.3)\n"
    )
    results.append(attempt("worker_crash_tree", leaf_setup + "os._exit(77)\n", cpu_seconds=5))
    results.append(attempt("job_close_tree", leaf_setup +
                           "from ctypes import wintypes\nk=ctypes.WinDLL('kernel32')\n"
                           "k.CloseHandle.argtypes=[wintypes.HANDLE]\nk.CloseHandle(job_handle)\n",
                           cpu_seconds=5))
    for prefix, old in (("baseline_start", True), ("guard_start", False)):
        for index in range(5):
            results.append(attempt(f"{prefix}_{index}", "time.sleep(0.3)\nprint('RESULT_OK',flush=True)\n",
                                   baseline=old, cpu_seconds=5))
    summary = {
        "attempts": len(results), "baseline_sha256": hashlib.sha256(baseline).hexdigest(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "timeouts": sum(item["outcome"] == "timeout" for item in results),
        "startup_medians_seconds": {
            prefix: statistics.median(item["metadata"][0]["limit_wall_seconds"]
                                      for item in results if str(item["name"]).startswith(prefix))
            for prefix in ("baseline_start", "guard_start")
        },
        "scope": "20 local disposable attempts, maximum two concurrent CPU workers, no model or network",
    }
    (OUTPUT / "probe_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
