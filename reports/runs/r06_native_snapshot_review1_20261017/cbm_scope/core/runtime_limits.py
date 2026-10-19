"""Run-owned Windows Job limits with independent aggregate CPU accounting."""

import ctypes
from ctypes import wintypes
from typing import TypedDict, TypeVar

JobStructure = TypeVar("JobStructure", bound=ctypes.Structure)


class JobUsage(TypedDict):
    cpu_seconds: float
    active_processes: int
    peak_job_memory_bytes: int


MEMORY_PER_PROCESS = 512 * 1024**2
MEMORY_TOTAL = 2 * 1024**3
CPU_RATE = 2000
CPU_SECONDS_TOTAL = 1200


class BasicLimits(ctypes.Structure):
    _fields_ = [
        ("process_time", ctypes.c_longlong),
        ("job_time", ctypes.c_longlong),
        ("flags", wintypes.DWORD),
        ("min_ws", ctypes.c_size_t),
        ("max_ws", ctypes.c_size_t),
        ("active_limit", wintypes.DWORD),
        ("affinity", ctypes.c_size_t),
        ("priority", wintypes.DWORD),
        ("scheduling", wintypes.DWORD),
    ]


class IoCounters(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_ulonglong)
        for name in (
            "read_ops",
            "write_ops",
            "other_ops",
            "read_bytes",
            "write_bytes",
            "other_bytes",
        )
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


class CpuRate(ctypes.Structure):
    _fields_ = [("flags", wintypes.DWORD), ("rate", wintypes.DWORD)]


class Accounting(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_longlong) for name in ("user", "kernel", "period_user", "period_kernel")
    ] + [(name, wintypes.DWORD) for name in ("page_faults", "total", "active", "terminated")]


class OwnedJob:
    """The supervisor joins before spawning so every descendant inherits limits."""

    def __init__(self) -> None:
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.GetCurrentProcess.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        self.kernel.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_void_p,
        ]
        self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError("owned Job unavailable")
        limits = ExtendedLimits()
        limits.basic.flags = 0x100 | 0x200 | 0x2000
        limits.process_memory = MEMORY_PER_PROCESS
        limits.job_memory = MEMORY_TOTAL
        rate = CpuRate(0x1 | 0x4, CPU_RATE)
        for kind, value in ((9, limits), (15, rate)):
            if not self.kernel.SetInformationJobObject(
                self.handle, kind, ctypes.byref(value), ctypes.sizeof(value)
            ):
                raise OSError("owned Job limit unavailable")
        if not self.kernel.AssignProcessToJobObject(self.handle, self.kernel.GetCurrentProcess()):
            raise OSError("owned Job assignment unavailable")
        actual_limits = self.query(9, ExtendedLimits)
        actual_rate = self.query(15, CpuRate)
        assert actual_limits.process_memory == MEMORY_PER_PROCESS
        assert actual_limits.job_memory == MEMORY_TOTAL
        assert actual_limits.basic.flags & 0x2300 == 0x2300
        assert actual_rate.flags == 5 and actual_rate.rate == CPU_RATE

    def query(self, kind: int, structure: type[JobStructure]) -> JobStructure:
        value = structure()
        if not self.kernel.QueryInformationJobObject(
            self.handle, kind, ctypes.byref(value), ctypes.sizeof(value), None
        ):
            raise OSError("owned Job accounting unavailable")
        return value

    def usage(self) -> JobUsage:
        accounting = self.query(1, Accounting)
        limits = self.query(9, ExtendedLimits)
        return {
            "cpu_seconds": (accounting.user + accounting.kernel) / 10_000_000,
            "active_processes": accounting.active,
            "peak_job_memory_bytes": limits.peak_job_memory,
        }
