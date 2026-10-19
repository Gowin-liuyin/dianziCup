"""Measure an independent stdlib subprocess control before testing a failed guard."""

import ctypes
from ctypes import wintypes
import gc
import json
import os
import subprocess
import sys

from ai_intel.infrastructure import process_limits

kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.GetCurrentProcess.restype = wintypes.HANDLE
kernel.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.c_void_p]


def count():
    value = wintypes.DWORD()
    assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), ctypes.byref(value))
    return value.value


before = count()
subprocess.run([os.path.join(sys.base_prefix, "python.exe"), "-I", "-S", "-c", "pass"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=3)
gc.collect()
control = count()
process_limits._WINDOWS_CPU_GUARD_CODE = "import time; time.sleep(20)"
try:
    process_limits.bound_process_resources(memory_bytes=100*1024**2, cpu_seconds=5)
except OSError:
    pass
gc.collect()
print(json.dumps({"before": before, "after_independent_subprocess_control": control, "after_guard_failure": count()}))
