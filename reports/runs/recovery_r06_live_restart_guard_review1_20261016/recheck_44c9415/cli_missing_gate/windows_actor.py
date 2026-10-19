"""Bind an actual owned actor and descendants to kernel handles before termination."""

from __future__ import annotations

import ctypes
import json
import subprocess
from ctypes import wintypes
from datetime import UTC, datetime


class OwnershipError(RuntimeError):
    """An uncertain process must not receive a PID-based signal."""


def process_tree() -> dict[int, dict[str, object]]:
    script = (
        "Get-CimInstance Win32_Process | ForEach-Object { "
        "[ordered]@{pid=$_.ProcessId;parent=$_.ParentProcessId;"
        "created=$_.CreationDate.ToUniversalTime().ToString('o')} } | ConvertTo-Json -Compress"
    )
    output = subprocess.check_output(
        ["powershell.exe", "-NoProfile", "-Command", script], text=True, timeout=3
    )
    return {row["pid"]: row for row in json.loads(output)}


def _creation_ticks(kernel, handle) -> int:
    created, exited, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
    if not kernel.GetProcessTimes(
        handle,
        ctypes.byref(created),
        ctypes.byref(exited),
        ctypes.byref(kernel_time),
        ctypes.byref(user_time),
    ):
        raise OwnershipError("owned process creation unavailable")
    return created.dwLowDateTime + (created.dwHighDateTime << 32)


def _snapshot_ticks(value: str) -> int:
    difference = datetime.fromisoformat(value) - datetime(1601, 1, 1, tzinfo=UTC)
    return (difference.days * 86400 + difference.seconds) * 10000000 + difference.microseconds * 10


class WindowsOwnedActor:
    """The launcher ancestry and exact creation ticks bind the actual interpreter."""

    def __init__(self, actual_pid: int, creation_ticks: int, launcher_pid: int):
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [
            ctypes.POINTER(wintypes.FILETIME)
        ] * 4
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.pid = actual_pid
        self.creation_ticks = creation_ticks
        self.handle = self.kernel.OpenProcess(0x100000 | 0x1000 | 0x100 | 1, False, actual_pid)
        if not self.handle:
            raise OwnershipError("actual owned actor unavailable")
        try:
            if _creation_ticks(self.kernel, self.handle) != creation_ticks:
                raise OwnershipError("owned actor creation changed")
            tree = process_tree()
            parent = tree.get(actual_pid, {}).get("parent")
            if actual_pid == launcher_pid or parent != launcher_pid:
                raise OwnershipError("actual interpreter is not the owned launcher child")
        except Exception:
            self.close()
            raise

    def exited(self) -> bool:
        return self.kernel.WaitForSingleObject(self.handle, 0) == 0

    def kill_owned_tree(self) -> None:
        if not self.exited() and not self.kernel.TerminateProcess(self.handle, 70):
            raise OwnershipError("actual owned actor termination rejected")
        if self.kernel.WaitForSingleObject(self.handle, 1000) != 0:
            raise OwnershipError("actual owned actor exit was not confirmed")
        tree = process_tree()
        selected = {self.pid}
        while (
            additions := {pid for pid, row in tree.items() if row["parent"] in selected} - selected
        ):
            selected.update(additions)
        handles = []
        try:
            for pid in selected - {self.pid}:
                handle = self.kernel.OpenProcess(0x100000 | 0x1000 | 0x100 | 1, False, pid)
                if not handle:
                    raise OwnershipError("owned descendant exit could not be confirmed")
                handles.append(handle)
                ticks = _creation_ticks(self.kernel, handle)
                expected = _snapshot_ticks(str(tree[pid]["created"]))
                if ticks // 10 != expected // 10:
                    raise OwnershipError("owned descendant creation changed")
            for handle in handles:
                if self.kernel.WaitForSingleObject(handle, 0) != 0:
                    if (
                        not self.kernel.TerminateProcess(handle, 70)
                        and self.kernel.WaitForSingleObject(handle, 1000) != 0
                    ):
                        raise OwnershipError("owned descendant termination rejected")
                    if self.kernel.WaitForSingleObject(handle, 1000) != 0:
                        raise OwnershipError("owned descendant exit not confirmed")
        finally:
            for handle in handles:
                self.kernel.CloseHandle(handle)

    def close(self) -> None:
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
