"""Bind an actual owned actor and descendants to kernel handles before termination."""

from __future__ import annotations

import ctypes
import ntpath
import time
from ctypes import wintypes
from datetime import UTC, datetime, timedelta


class OwnershipError(RuntimeError):
    """An uncertain process must not receive a PID-based signal."""


class _ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("size", wintypes.DWORD),
        ("usage", wintypes.DWORD),
        ("pid", wintypes.DWORD),
        ("heap", ctypes.c_size_t),
        ("module", wintypes.DWORD),
        ("threads", wintypes.DWORD),
        ("parent", wintypes.DWORD),
        ("priority", wintypes.LONG),
        ("flags", wintypes.DWORD),
        ("name", wintypes.WCHAR * 260),
    ]


def _snapshot_birth(
    kernel: ctypes.WinDLL, pid: int, name: str, snapshot_started_ticks: int
) -> tuple[str | None, int | None]:
    """Keep denied or raced entries visible, without inventing a process generation."""
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return None, ctypes.get_last_error()
    try:
        try:
            ticks = _creation_ticks(kernel, handle)
        except OwnershipError:
            return None, ctypes.get_last_error()
        image = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(image))
        if not kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(length)):
            return None, ctypes.get_last_error()
        if ticks > snapshot_started_ticks or ntpath.basename(image.value).casefold() != name.casefold():
            return None, 13
        created = datetime(1601, 1, 1, tzinfo=UTC) + timedelta(microseconds=ticks // 10)
        return created.isoformat(timespec="microseconds"), None
    finally:
        if not kernel.CloseHandle(handle):
            raise OwnershipError("process snapshot read handle close failed")


def process_tree() -> dict[int, dict[str, object]]:
    """Preserve all Toolhelp rows; unknown birth never means an absent or exited PID."""
    deadline = time.monotonic() + 3
    snapshot_started_ticks = _snapshot_ticks(datetime.now(UTC).isoformat())
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
    kernel.Process32FirstW.restype = wintypes.BOOL
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
    kernel.Process32NextW.restype = wintypes.BOOL
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
    ]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value or not snapshot:
        raise OwnershipError("process snapshot unavailable")
    tree: dict[int, dict[str, object]] = {}
    try:
        entry = _ProcessEntry()
        entry.size = ctypes.sizeof(entry)
        if not kernel.Process32FirstW(snapshot, ctypes.byref(entry)):
            raise OwnershipError("process snapshot first entry unavailable")
        while True:
            if time.monotonic() >= deadline:
                raise OwnershipError("process snapshot exceeded three seconds")
            pid, parent, name = int(entry.pid), int(entry.parent), str(entry.name)
            if pid in tree or not name:
                raise OwnershipError("process snapshot entry is ambiguous")
            created, birth_error = _snapshot_birth(kernel, pid, name, snapshot_started_ticks)
            tree[pid] = {
                "pid": pid, "parent": parent, "created": created,
                "name": name, "birth_error": birth_error,
            }
            if not kernel.Process32NextW(snapshot, ctypes.byref(entry)):
                if ctypes.get_last_error() != 18:
                    raise OwnershipError("process snapshot enumeration incomplete")
                break
        if time.monotonic() >= deadline:
            raise OwnershipError("process snapshot exceeded three seconds")
    finally:
        if not kernel.CloseHandle(snapshot):
            raise OwnershipError("process snapshot handle close failed")
    if time.monotonic() >= deadline:
        raise OwnershipError("process snapshot exceeded three seconds")
    return tree


class _JobProcessIds(ctypes.Structure):
    _fields_ = [
        ("assigned", wintypes.DWORD),
        ("listed", wintypes.DWORD),
        ("pids", ctypes.c_size_t * 1024),
    ]


def _owned_job_process_ids(kernel: ctypes.WinDLL, job_handle: int) -> set[int]:
    """A complete current Job inventory excludes foreign PIDs only at query time."""
    kernel.QueryInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
    ]
    kernel.QueryInformationJobObject.restype = wintypes.BOOL
    process_ids = _JobProcessIds()
    returned = wintypes.DWORD()
    if not kernel.QueryInformationJobObject(
        job_handle, 3, ctypes.byref(process_ids), ctypes.sizeof(process_ids), ctypes.byref(returned)
    ):
        raise OwnershipError("owned Job remaining membership unavailable")
    minimum_length = _JobProcessIds.pids.offset + process_ids.listed * ctypes.sizeof(ctypes.c_size_t)
    if (
        process_ids.assigned != process_ids.listed
        or process_ids.listed > len(process_ids.pids)
        or not minimum_length <= returned.value <= ctypes.sizeof(process_ids)
    ):
        raise OwnershipError("owned Job remaining membership incomplete")
    pids = {int(pid) for pid in process_ids.pids[:process_ids.listed]}
    if len(pids) != process_ids.listed or any(pid <= 0 or pid > 0xFFFFFFFF for pid in pids):
        raise OwnershipError("owned Job remaining membership ambiguous")
    return pids


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
    try:
        difference = datetime.fromisoformat(value) - datetime(1601, 1, 1, tzinfo=UTC)
    except (ValueError, TypeError) as error:
        raise OwnershipError("process snapshot creation timestamp unavailable") from error
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
            remaining_owned_pids: set[int] | None = None
            for pid, row in remaining.items():
                parent = row["parent"]
                if row["created"] is None and (
                    pid in generations or (type(parent) is int and parent in generations)
                ):
                    raise OwnershipError("bound remaining process generation unavailable; close owned Job")
                if row["created"] is None and type(parent) is int and parent not in remaining:
                    if remaining_owned_pids is None:
                        remaining_owned_pids = _owned_job_process_ids(self.kernel, self.owned_job_handle)
                    if pid in remaining_owned_pids:
                        raise OwnershipError("owned orphan generation unavailable; close owned Job")
                    continue
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
            if remaining_owned_pids is not None and _owned_job_process_ids(
                self.kernel, self.owned_job_handle
            ) != remaining_owned_pids:
                raise OwnershipError("owned Job membership changed during orphan verification")
        finally:
            for handle in handles:
                self.kernel.CloseHandle(handle)

    def close(self) -> None:
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
