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


def _creation_ticks(kernel: ctypes.WinDLL, handle: int) -> int:
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

    def __init__(
        self, actual_pid: int, creation_ticks: int, launcher_pid: int, owned_job_handle: int
    ) -> None:
        if type(owned_job_handle) is not int or owned_job_handle <= 0:
            raise OwnershipError("explicit owned Job handle required")
        self.owned_job_handle = owned_job_handle
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [
            ctypes.POINTER(wintypes.FILETIME)
        ] * 4
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel.IsProcessInJob.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.BOOL),
        ]
        self.pid = actual_pid
        self.creation_ticks = creation_ticks
        self.handle = self.kernel.OpenProcess(0x100000 | 0x1000 | 0x100 | 1, False, actual_pid)
        if not self.handle:
            raise OwnershipError("actual owned actor unavailable")
        try:
            if _creation_ticks(self.kernel, self.handle) != creation_ticks:
                raise OwnershipError("owned actor creation changed")
            if not self.in_owned_job(self.handle):
                raise OwnershipError("actual actor is outside owned Job")
            tree = process_tree()
            parent = tree.get(actual_pid, {}).get("parent")
            if actual_pid == launcher_pid or parent != launcher_pid:
                raise OwnershipError("actual interpreter is not the owned launcher child")
            launcher = self.kernel.OpenProcess(0x100000 | 0x1000, False, launcher_pid)
            if not launcher:
                raise OwnershipError("owned launcher generation unavailable")
            try:
                launcher_ticks = _creation_ticks(self.kernel, launcher)
                if (
                    not self.in_owned_job(launcher)
                    or creation_ticks < launcher_ticks
                    or launcher_ticks // 10
                    != _snapshot_ticks(str(tree[launcher_pid]["created"])) // 10
                ):
                    raise OwnershipError("owned launcher generation differs")
            finally:
                self.kernel.CloseHandle(launcher)
        except Exception:
            self.close()
            raise

    def exited(self) -> bool:
        return bool(self.kernel.WaitForSingleObject(self.handle, 0) == 0)

    def in_owned_job(self, handle: int) -> bool:
        membership = wintypes.BOOL()
        if not self.kernel.IsProcessInJob(handle, self.owned_job_handle, ctypes.byref(membership)):
            raise OwnershipError("owned Job membership unavailable")
        return bool(membership.value)

    def bind_descendant(
        self, pid: int, row: dict[str, object], parent_ticks: int
    ) -> tuple[int, int] | None:
        expected = _snapshot_ticks(str(row["created"]))
        if expected // 10 < parent_ticks // 10:
            return None
        handle = self.kernel.OpenProcess(0x100000 | 0x1000 | 0x100 | 1, False, pid)
        if not handle:
            raise OwnershipError("owned descendant exit could not be confirmed")
        try:
            ticks = _creation_ticks(self.kernel, handle)
            if ticks // 10 != expected // 10:
                raise OwnershipError("owned descendant creation changed")
            if ticks < parent_ticks or not self.in_owned_job(handle):
                self.kernel.CloseHandle(handle)
                return None
        except Exception:
            self.kernel.CloseHandle(handle)
            raise
        return handle, ticks

    def kill_owned_tree(self) -> None:
        if _creation_ticks(
            self.kernel, self.handle
        ) != self.creation_ticks or not self.in_owned_job(self.handle):
            raise OwnershipError("actual actor ownership changed")
        tree = process_tree()
        if (
            self.pid in tree
            and _snapshot_ticks(str(tree[self.pid]["created"])) // 10 != self.creation_ticks // 10
        ):
            raise OwnershipError("actual actor PID generation reused")
        generations = {self.pid: self.creation_ticks}
        handles = []
        try:
            while True:
                additions = 0
                for pid, row in tree.items():
                    parent = row["parent"]
                    if pid in generations or type(parent) is not int or parent not in generations:
                        continue
                    bound = self.bind_descendant(pid, row, generations[parent])
                    if bound is not None:
                        handle, ticks = bound
                        handles.append(handle)
                        generations[pid] = ticks
                        additions += 1
                if not additions:
                    break
            if not self.exited() and not self.kernel.TerminateProcess(self.handle, 70):
                raise OwnershipError("actual owned actor termination rejected")
            if self.kernel.WaitForSingleObject(self.handle, 1000) != 0:
                raise OwnershipError("actual owned actor exit was not confirmed")
            for handle in handles:
                if self.kernel.WaitForSingleObject(handle, 0) != 0:
                    if (
                        not self.kernel.TerminateProcess(handle, 70)
                        and self.kernel.WaitForSingleObject(handle, 1000) != 0
                    ):
                        raise OwnershipError("owned descendant termination rejected")
                    if self.kernel.WaitForSingleObject(handle, 1000) != 0:
                        raise OwnershipError("owned descendant exit not confirmed")
            remaining = process_tree()
            for pid, row in remaining.items():
                parent = row["parent"]
                if (
                    pid != self.pid
                    and type(parent) is int
                    and parent not in remaining
                    and _snapshot_ticks(str(row["created"])) // 10 >= self.creation_ticks // 10
                ):
                    bound = self.bind_descendant(pid, row, self.creation_ticks)
                    if bound is not None:
                        handle, _ = bound
                        handles.append(handle)
                        if self.kernel.WaitForSingleObject(handle, 0) != 0:
                            raise OwnershipError("unbound owned orphan remains; close owned Job")
                    continue
                if pid == self.pid or type(parent) is not int or parent not in generations:
                    continue
                if (
                    parent in remaining
                    and _snapshot_ticks(str(remaining[parent]["created"])) // 10
                    != generations[parent] // 10
                ):
                    raise OwnershipError("owned parent generation changed during termination")
                bound = self.bind_descendant(pid, row, generations[parent])
                if bound is not None:
                    handle, _ = bound
                    handles.append(handle)
                    if self.kernel.WaitForSingleObject(handle, 0) != 0:
                        raise OwnershipError("new owned descendant remains; close owned Job")
        finally:
            for handle in handles:
                self.kernel.CloseHandle(handle)

    def close(self) -> None:
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
