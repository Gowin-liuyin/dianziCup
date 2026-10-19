"""Bounded fixture-only probes for R07 console ancestry and stdin deadlines."""

import ctypes
import hashlib
import importlib.util
import json
import msvcrt
import os
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

RUN = Path(__file__).parent
SOURCE = Path("D:/wt/r07-io-deadline")
PYTHON = "C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe"
METADATA = SOURCE / "reports/runs/r07_source_io_deadline_20261017/batch13_process_metadata.py"
LIMITS = RUN / "runtime_limits.original.py"
records = []
seen = {}
peak = {}
stop_monitor = threading.Event()
failed = []


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


metadata = load_module("diagnostic_metadata", METADATA)
limits = load_module("diagnostic_limits", LIMITS)
assert os.cpu_count() == 24
limits.MEMORY_TOTAL = 1024**3
limits.CPU_RATE = 833
job = limits.OwnedJob()
control, chain = metadata.control_root(metadata.current_identity())
preexisting = metadata.descendants(control)
started = time.monotonic()
watchdog = threading.Timer(20, os._exit, args=(124,))
watchdog.daemon = True
watchdog.start()


def observe():
    global peak
    while not stop_monitor.is_set():
        tree = metadata.descendants(control)
        seen.update(tree)
        if len(tree) > len(peak):
            peak = tree
        if len(tree) > 10:
            failed.append("full_windows_process_cap_exceeded")
            os._exit(124)
        stop_monitor.wait(0.005)


monitor = threading.Thread(target=observe)
monitor.start()
environment = {name: os.environ[name] for name in ("SYSTEMROOT", "WINDIR") if name in os.environ}
environment.update(
    PYTHONUTF8="1",
    PYTHONIOENCODING="utf-8",
    PYTHONPATH=os.pathsep.join((str(SOURCE / "backend/src"), "D:/dianzi/backend/.venv/Lib/site-packages")),
)


def join_observed(before):
    """Wait for every birth-matched child observed in this segment before advancing."""
    deadline = time.monotonic() + 1
    owned = {pid: value for pid, value in seen.items() if pid not in before}
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    for pid, identity in owned.items():
        try:
            actual = metadata.identity(pid)
        except OSError:
            continue
        assert actual == {"pid": pid, "birth_utc": identity["birth_utc"]}
        handle = kernel.OpenProcess(0x100000, False, pid)
        if handle:
            try:
                assert kernel.WaitForSingleObject(handle, max(0, int((deadline - time.monotonic()) * 1000))) == 0
            finally:
                kernel.CloseHandle(handle)
    return list(owned.values())


def flags_case(label, flags):
    before = set(seen) | set(preexisting)
    code = (
        "import os,time,subprocess\n"
        "from ai_intel.infrastructure import process_limits as limits\n"
        "original=limits.subprocess.Popen\n"
        "def fixed_guard(*args,**kwargs):\n"
        f"    kwargs['creationflags']={flags}\n"
        "    return original(*args,**kwargs)\n"
        "limits.subprocess.Popen=fixed_guard\n"
        "handle=limits.bound_process_resources(memory_bytes=512*1024**2,cpu_seconds=5)\n"
        "print('READY',os.getpid(),limits._WINDOWS_CPU_GUARDS[0].pid,flush=True)\n"
        "time.sleep(0.4)\n"
        "print('OK',flush=True)\n"
    )
    process = subprocess.Popen([PYTHON, "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=environment, creationflags=flags)
    local_start = time.monotonic()
    output, error = process.communicate(b"", timeout=4)
    worker_done = time.monotonic()
    immediately_remaining = [value for pid, value in metadata.descendants(control).items() if pid not in before]
    owned = join_observed(before)
    assert process.returncode == 0 and not error and output.rstrip().endswith(b"\nOK")
    records.append({"label": label, "flags": flags, "duration_seconds": worker_done - local_start,
                    "returncode": process.returncode, "valid_pipe_result": True,
                    "worker_exit_remaining": immediately_remaining, "joined_births": owned,
                    "joined_at_seconds": time.monotonic() - local_start})


try:
    flags_case("original_create_no_window", 0x08000000)
    flags_case("detached_worker_and_guard", 0x00000008)
    before = set(seen) | set(preexisting)
    process = subprocess.Popen([PYTHON, "-I", "-S", "-c", "import time; time.sleep(0.3)"],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               env=environment, creationflags=8)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetNamedPipeInfo.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.DWORD)] * 4
    pipe_out, pipe_in = wintypes.DWORD(), wintypes.DWORD()
    pipe_ok = bool(kernel.GetNamedPipeInfo(msvcrt.get_osfhandle(process.stdin.fileno()), None,
                                         ctypes.byref(pipe_out), ctypes.byref(pipe_in), None))
    local_start = time.monotonic()
    outcome = "returned"
    try:
        process.communicate(b"x" * 32768, timeout=0.05)
    except subprocess.TimeoutExpired:
        outcome = "TimeoutExpired"
    elapsed = time.monotonic() - local_start
    if process.poll() is None:
        process.kill()
    process.wait(timeout=1)
    for stream in (process.stdin, process.stdout):
        if stream is not None:
            stream.close()
    records.append({"label": "actual_cpython_communicate_stdin", "timeout_seconds": 0.05,
                    "elapsed_seconds": elapsed, "outcome": outcome, "input_bytes": 32768,
                    "get_named_pipe_info_succeeded": pipe_ok, "out_buffer_bytes": pipe_out.value,
                    "in_buffer_bytes": pipe_in.value, "deadline_overrun_reproduced": elapsed > 0.2,
                    "joined_births": join_observed(before)})
    assert elapsed > 0.2
    before = set(seen) | set(preexisting)
    sys.path[:0] = [str(SOURCE / "backend/src"), "D:/dianzi/backend/.venv/Lib/site-packages"]
    from ai_intel.infrastructure.content_store import _read_with_deadline

    request = json.dumps({"storage": "local", "root_directory": "D:/" + "x" * 8192,
                          "content_hash": "a" * 64, "remaining_seconds": 0.15, "byte_limit": 1}).encode()
    local_start = time.monotonic()
    outcome = "returned"
    try:
        _read_with_deadline(request, local_start + 0.15, 1)
    except (TimeoutError, OSError, ValueError) as error:
        outcome = type(error).__name__
    elapsed = time.monotonic() - local_start
    records.append({"label": "actual_frozen_r07_large_private_config", "deadline_seconds": 0.15,
                    "input_bytes": len(request), "elapsed_seconds": elapsed, "outcome": outcome,
                    "deadline_overrun_reproduced": elapsed > 0.15,
                    "joined_births": join_observed(before)})
    assert elapsed > 0.15
finally:
    stop_monitor.set()
    monitor.join(timeout=1)
    watchdog.cancel()
    watchdog.join(timeout=1)
    assert not monitor.is_alive() and not watchdog.is_alive()
    residual = [value for pid, value in metadata.descendants(control).items() if pid not in preexisting]
    final = {"records": records, "elapsed_seconds": time.monotonic() - started,
             "cpu_rate": limits.CPU_RATE, "logical_cpu_count": os.cpu_count(),
             "process_memory_bytes": limits.MEMORY_PER_PROCESS, "job_memory_bytes": limits.MEMORY_TOTAL,
             "kill_on_close": True, "full_windows_peak_count": len(peak), "full_windows_peak": list(peak.values()),
             "preexisting_control_processes": list(preexisting.values()), "control_chain": chain,
             "remaining_owned_processes": residual, "job_usage": job.usage(), "failures": failed,
             "source_sha": "4d85343a6117f1be215313aacd4652a554e334e4",
             "input_hashes": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in
                              (Path(__file__), LIMITS, METADATA, Path(PYTHON).parent / "Lib/subprocess.py")}}
    (RUN / "native_probe_result.json").write_text(json.dumps(final, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(records), "elapsed_seconds": final["elapsed_seconds"],
                      "full_windows_peak_count": len(peak), "remaining_owned": len(residual),
                      "failures": failed}), flush=True)
    assert not residual and not failed
