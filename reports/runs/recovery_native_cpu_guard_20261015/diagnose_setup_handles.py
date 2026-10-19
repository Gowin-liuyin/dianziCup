"""Inspect only handles created by this synthetic failed guard setup."""

import ctypes
from ctypes import wintypes
import gc
import json
import subprocess

from ai_intel.infrastructure import process_limits

kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.GetCurrentProcess.restype = wintypes.HANDLE
kernel.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
real_close = kernel.CloseHandle
close_events = []


def close_record(handle):
    outcome = real_close(handle)
    close_events.append({"handle": handle.value if hasattr(handle, "value") else handle, "closed": bool(outcome), "error": ctypes.get_last_error() if not outcome else 0})
    return outcome


def count():
    value = wintypes.DWORD()
    assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), ctypes.byref(value))
    return value.value


kernel.CloseHandle = close_record
process_limits.ctypes.WinDLL = lambda *args, **kwargs: kernel
real_popen = subprocess.Popen
guards = []


def record_guard(*args, **kwargs):
    guard = real_popen(*args, **kwargs)
    guards.append(guard)
    return guard


process_limits.subprocess.Popen = record_guard
process_limits._WINDOWS_CPU_GUARD_CODE = "import time; time.sleep(20)"
for attempt in range(3):
    before = count()
    try:
        process_limits.bound_process_resources(memory_bytes=100*1024**2, cpu_seconds=5)
    except OSError:
        pass
    print(json.dumps({"attempt": attempt, "before": before, "after_with_observer": count(), "close_events": close_events, "guard_handles": [int(guard._handle) for guard in guards], "guard_returncodes": [guard.poll() for guard in guards], "active_popen_count": len(subprocess._active or [])}), flush=True)
    guards.clear()
    close_events.clear()
    collected = gc.collect()
    print(json.dumps({"attempt": attempt, "after_observer_cleared": count(), "collected": collected, "active_popen_count": len(subprocess._active or [])}), flush=True)
