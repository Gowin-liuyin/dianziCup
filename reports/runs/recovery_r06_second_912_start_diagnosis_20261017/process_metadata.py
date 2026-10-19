"""Observe Windows PID birth using native APIs, without reading command lines or secrets."""

import ctypes
import os
from ctypes import wintypes
from datetime import UTC, datetime


def identity(pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.c_void_p] * 4
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        raise OSError("process identity unavailable")
    try:
        values = [ctypes.c_ulonglong() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in values)):
            raise OSError("process creation time unavailable")
        birth = datetime.fromtimestamp((values[0].value - 116444736000000000) / 10000000, UTC)
        return {"pid": pid, "birth_utc": birth.isoformat(timespec="microseconds")}
    finally:
        kernel.CloseHandle(handle)


def descendants(pid):
    class ProcessEntry(ctypes.Structure):
        _fields_ = [
            ("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD),
            ("heap", ctypes.c_size_t), ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
            ("parent", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD),
            ("executable", wintypes.WCHAR * 260),
        ]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        raise OSError("process tree snapshot unavailable")
    try:
        entry = ProcessEntry()
        entry.size = ctypes.sizeof(entry)
        entries = {}
        success = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while success:
            entries[entry.pid] = entry.parent
            success = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        tree = {pid}
        while True:
            expanded = tree | {child for child, parent in entries.items() if parent in tree}
            if expanded == tree:
                break
            tree = expanded
        return tree
    finally:
        kernel.CloseHandle(snapshot)


def current_identity():
    return identity(os.getpid())
