"""Native memory limits and sampled CPU enforcement for disposable trusted workers."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys

_WINDOWS_CPU_GUARDS: list[subprocess.Popen[bytes]] = []
_WINDOWS_CPU_GUARD_CODE = """
import ctypes
import sys
from ctypes import wintypes

target_handle, ready_handle, cpu_ticks = map(int, sys.argv[1:])
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel.WaitForSingleObject.restype = wintypes.DWORD
kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.c_void_p] * 4
kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel.SetEvent.argtypes = [wintypes.HANDLE]
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
times = [ctypes.c_ulonglong() for _ in range(4)]
try:
    if not kernel.GetProcessTimes(target_handle, *(ctypes.byref(value) for value in times)):
        raise OSError('CPU accounting unavailable')
    if not kernel.SetEvent(ready_handle):
        raise OSError('CPU guard readiness unavailable')
    kernel.CloseHandle(ready_handle)
    ready_handle = 0
    while True:
        state = kernel.WaitForSingleObject(target_handle, 50)
        if state == 0:
            break
        if state != 258:
            raise OSError('CPU guard process wait unavailable')
        if not kernel.GetProcessTimes(target_handle, *(ctypes.byref(value) for value in times)):
            raise OSError('CPU accounting unavailable')
        if times[2].value + times[3].value >= cpu_ticks:
            if not kernel.TerminateProcess(target_handle, 0xC0000044):
                if kernel.WaitForSingleObject(target_handle, 0) != 0:
                    raise OSError('CPU guard termination unavailable')
            break
except BaseException:
    kernel.TerminateProcess(target_handle, 0xC0000044)
    raise
finally:
    if ready_handle:
        kernel.CloseHandle(ready_handle)
    kernel.CloseHandle(target_handle)
"""


def _start_windows_cpu_guard(cpu_seconds: int) -> subprocess.Popen[bytes]:
    """A separate stdlib process counts all worker threads even while its GIL is held."""
    if sys.platform != "win32":
        raise OSError("process resource limit unavailable")
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateEventW.restype = wintypes.HANDLE
    kernel.DuplicateHandle.argtypes = [
        wintypes.HANDLE,
        wintypes.HANDLE,
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    ready_handle = kernel.CreateEventW(None, False, False, None)
    if ready_handle is None:
        raise OSError("process resource limit unavailable")
    target_handle = wintypes.HANDLE()
    guard: subprocess.Popen[bytes] | None = None
    try:
        current_process = kernel.GetCurrentProcess()
        if not kernel.DuplicateHandle(
            current_process,
            current_process,
            current_process,
            ctypes.byref(target_handle),
            0x100000 | 0x1000 | 0x1,
            True,
            0,
        ):
            raise OSError("process resource limit unavailable")
        os.set_handle_inheritable(ready_handle, True)
        startup = subprocess.STARTUPINFO(
            lpAttributeList={"handle_list": [ready_handle, target_handle.value]}
        )
        environment = {
            name: os.environ[name] for name in ("SYSTEMROOT", "WINDIR") if name in os.environ
        }
        guard = subprocess.Popen(
            [
                os.path.join(sys.base_prefix, "python.exe"),
                "-I",
                "-S",
                "-c",
                _WINDOWS_CPU_GUARD_CODE,
                str(target_handle.value),
                str(ready_handle),
                str(cpu_seconds * 10_000_000),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            startupinfo=startup,
            creationflags=0x08000000,
            env=environment,
        )
        if kernel.WaitForSingleObject(ready_handle, 3000) != 0 or guard.poll() is not None:
            raise OSError("process resource limit unavailable")
        return guard
    except (OSError, ValueError, subprocess.SubprocessError):
        if guard is not None:
            guard.kill()
            guard.wait(timeout=1)
        raise OSError("process resource limit unavailable") from None
    finally:
        kernel.CloseHandle(ready_handle)
        if target_handle.value is not None:
            kernel.CloseHandle(target_handle)


def bound_process_resources(*, memory_bytes: int, cpu_seconds: int) -> int | None:
    """Keep the Job handle until worker exit; CPU includes user and kernel across its threads.

    Windows polls CPU every 50ms in a separate process; scheduling can delay termination.
    Job memory and native CPU limits remain as a fallback. Parent wall deadlines still apply.
    """
    if type(memory_bytes) is not int or not 1 <= memory_bytes <= 2 * 1024**3:
        raise ValueError("memory_bytes must be an integer between one byte and two GiB")
    if type(cpu_seconds) is not int or not 1 <= cpu_seconds <= 30:
        raise ValueError("cpu_seconds must be an integer between one and thirty")
    if sys.platform == "linux":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        return None

    if os.name != "nt":
        raise OSError("process resource limit unavailable")

    from ctypes import wintypes

    class IoCounters(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_ulonglong)
            for name in (
                "read_operations",
                "write_operations",
                "other_operations",
                "read_bytes",
                "write_bytes",
                "other_bytes",
            )
        ]

    class BasicLimits(ctypes.Structure):
        _fields_ = [
            ("process_time", ctypes.c_longlong),
            ("job_time", ctypes.c_longlong),
            ("flags", wintypes.DWORD),
            ("minimum_working_set", ctypes.c_size_t),
            ("maximum_working_set", ctypes.c_size_t),
            ("active_processes", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority", wintypes.DWORD),
            ("scheduling", wintypes.DWORD),
        ]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("basic", BasicLimits),
            ("io", IoCounters),
            ("process_memory", ctypes.c_size_t),
            ("job_memory", ctypes.c_size_t),
            ("peak_process_memory", ctypes.c_size_t),
            ("peak_job_memory", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateJobObjectW(None, None)
    if handle is None:
        raise OSError("process resource limit unavailable")
    limits = ExtendedLimits()
    limits.basic.flags = 0x100 | 0x2
    limits.basic.process_time = cpu_seconds * 10_000_000
    limits.process_memory = memory_bytes
    if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        kernel.CloseHandle(handle)
        raise OSError("process resource limit unavailable")
    if not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess()):
        kernel.CloseHandle(handle)
        raise OSError("process resource limit unavailable")
    guard: subprocess.Popen[bytes] | None = None
    try:
        guard = _start_windows_cpu_guard(cpu_seconds)
        limits.basic.flags |= 0x2000
        if not kernel.SetInformationJobObject(
            handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            raise OSError("process resource limit unavailable")
    except OSError:
        if guard is not None:
            guard.kill()
            guard.wait(timeout=1)
        kernel.CloseHandle(handle)
        raise
    _WINDOWS_CPU_GUARDS.append(guard)
    return int(handle)
