"""原文内容寻址存储: 临时写入排他发布、hash 校验、路径不取自用户输入。"""

from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from io import BufferedWriter
from pathlib import Path
from threading import BoundedSemaphore, Thread
from typing import Protocol

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
MAX_DEADLINE_CONTENT_BYTES = 64 * 1024 * 1024
MAX_CONTENT_REQUEST_BYTES = 4096
CONTENT_READ_CLEANUP_SECONDS = 0.05
_CONTENT_READ_CAPACITY = BoundedSemaphore(2)


class _WindowsContentReadOwner:
    """Hold the worker birth/exit and only its direct guardian's stable native handles."""

    def __init__(self, worker_pid: int) -> None:
        from ctypes import wintypes

        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        for name in ("OpenProcess", "CreateToolhelp32Snapshot"):
            getattr(self._kernel, name).restype = wintypes.HANDLE
        self._kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self._kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        self._kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.c_void_p] * 4
        self._kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self._kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self._worker_pid = worker_pid
        self._worker_handle: int = self._kernel.OpenProcess(0x101000, False, worker_pid)
        if not self._worker_handle:
            raise OSError("content_read_worker_identity_unavailable")
        self._handles = [self._worker_handle]

    def _process_times(self, handle: int) -> tuple[int, int]:
        values = [ctypes.c_ulonglong() for _ in range(4)]
        if not self._kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in values)):
            raise OSError("content_read_process_identity_unavailable")
        return values[0].value, values[1].value

    def confirm_terminal(self, deadline_monotonic: float) -> None:
        """Snapshot after the held worker exits, so it cannot start a later guardian."""
        from ctypes import wintypes

        class ProcessEntry(ctypes.Structure):
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
                ("executable", wintypes.WCHAR * 260),
            ]

        if self._kernel.WaitForSingleObject(self._worker_handle, 0) != 0:
            raise OSError("content_read_worker_terminal_unconfirmed")
        birth, exited = self._process_times(self._worker_handle)
        if not birth or not exited:
            raise OSError("content_read_worker_terminal_unconfirmed")
        self._kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        self._kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        snapshot = self._kernel.CreateToolhelp32Snapshot(2, 0)
        if snapshot in (None, wintypes.HANDLE(-1).value):
            raise OSError("content_read_guardian_snapshot_unavailable")
        guardians: list[int] = []
        try:
            entry = ProcessEntry()
            entry.size = ctypes.sizeof(entry)
            ctypes.set_last_error(0)
            present = self._kernel.Process32FirstW(snapshot, ctypes.byref(entry))
            if not present and ctypes.get_last_error() != 18:
                raise OSError("content_read_guardian_snapshot_unavailable")
            while present:
                if entry.parent == self._worker_pid:
                    handle = self._kernel.OpenProcess(0x101000, False, entry.pid)
                    if not handle:
                        if ctypes.get_last_error() != 87:
                            raise OSError("content_read_guardian_identity_unavailable")
                    else:
                        self._handles.append(handle)
                        guardian_birth, _ = self._process_times(handle)
                        if not birth <= guardian_birth <= exited or guardians:
                            raise OSError("content_read_guardian_identity_uncertain")
                        guardians.append(handle)
                ctypes.set_last_error(0)
                present = self._kernel.Process32NextW(snapshot, ctypes.byref(entry))
                if not present and ctypes.get_last_error() != 18:
                    raise OSError("content_read_guardian_snapshot_unavailable")
        finally:
            if not self._kernel.CloseHandle(snapshot):
                self._handles.append(snapshot)
                raise OSError("content_read_snapshot_close_failed")
        for handle in guardians:
            milliseconds = max(0, math.floor((deadline_monotonic - time.monotonic()) * 1000))
            if self._kernel.WaitForSingleObject(handle, milliseconds) != 0:
                raise OSError("content_read_guardian_terminal_unconfirmed")
        failures: list[int] = []
        for handle in self._handles:
            if not self._kernel.CloseHandle(handle):
                failures.append(handle)
        self._handles = failures
        if failures:
            raise OSError("content_read_native_handle_close_failed")


@dataclass
class _ContentReadOwner:
    process: subprocess.Popen[bytes] = field(repr=False)
    native: _WindowsContentReadOwner | None = field(default=None, repr=False)


_FAILED_CONTENT_READS: dict[int, _ContentReadOwner] = {}


class ContentPathValidationError(ValueError):
    """内容哈希非法: 路径仅由合法哈希导出, 拒绝任何用户可控路径成分。"""


def remaining_content_time(deadline_monotonic: float) -> float:
    """Validate a finite absolute deadline without extending a caller's remaining budget."""
    if type(deadline_monotonic) not in (int, float) or not math.isfinite(deadline_monotonic):
        raise ValueError("content read deadline must be finite")
    remaining = deadline_monotonic - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("content_read_deadline_exhausted")
    return remaining


def _require_fresh_request_pipe_capacity(stream: BufferedWriter, request_bytes: int) -> None:
    """The sole writer checks its new empty pipe before writing any config bytes.

    GetNamedPipeInfo gives capacity rather than free space; this check is valid only
    for this newly created pipe with no prefix, earlier write or additional writer.
    """
    if os.name != "nt":
        return
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetNamedPipeInfo.argtypes = [wintypes.HANDLE] + [ctypes.c_void_p] * 4
    kernel.GetNamedPipeInfo.restype = wintypes.BOOL
    flags, outgoing, incoming = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
    if not kernel.GetNamedPipeInfo(
        msvcrt.get_osfhandle(stream.fileno()),
        ctypes.byref(flags),
        ctypes.byref(outgoing),
        ctypes.byref(incoming),
        None,
    ):
        raise OSError("content_read_request_pipe_capacity_unavailable")
    capacity = outgoing.value if flags.value & 1 else incoming.value
    if capacity == 0 or request_bytes > capacity:
        raise ValueError("content_read_request_exceeds_fresh_pipe_capacity")


def _read_with_deadline(request: bytes, deadline_monotonic: float, byte_limit: int) -> bytes:
    """Run only the fixed object reader; reserve shutdown time and always reap its process.

    A socket read timeout can be renewed indefinitely by slow headers or a drip stream.
    This native process boundary also bounds filesystem stalls and SDK initialization.
    """
    if type(request) is not bytes or not 0 < len(request) <= MAX_CONTENT_REQUEST_BYTES:
        raise ValueError("content_read_request_byte_limit_exceeded")
    remaining = remaining_content_time(deadline_monotonic) - CONTENT_READ_CLEANUP_SECONDS
    if remaining <= 0 or not _CONTENT_READ_CAPACITY.acquire(timeout=remaining):
        raise TimeoutError("content_read_deadline_exhausted")
    process: subprocess.Popen[bytes] | None = None
    primary_error: BaseException | None = None
    owner: _ContentReadOwner | None = None
    native_owner_missing = False
    try:
        remaining_content_time(deadline_monotonic)
        environment = {
            key: value
            for key, value in os.environ.items()
            if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "PYTHONPATH", "TEMP", "TMP"}
        }
        environment.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        executable = sys.executable
        if os.name == "nt":
            executable = str(Path(sys.base_prefix) / "python.exe")
            environment["PYTHONPATH"] = os.pathsep.join(
                (
                    str(Path(sys.prefix) / "Lib" / "site-packages"),
                    environment.get("PYTHONPATH", ""),
                )
            )
        process = subprocess.Popen(
            [executable, "-m", "ai_intel.infrastructure._content_read_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=environment,
            creationflags=0x8 if os.name == "nt" else 0,
            close_fds=True,
        )
        owner = _ContentReadOwner(process)
        if os.name == "nt":
            native_owner_missing = True
            owner.native = _WindowsContentReadOwner(process.pid)
            native_owner_missing = False
        if not isinstance(process.stdin, BufferedWriter):
            raise OSError("content_read_request_pipe_not_buffered")
        _require_fresh_request_pipe_capacity(process.stdin, len(request))
        remaining = remaining_content_time(deadline_monotonic) - CONTENT_READ_CLEANUP_SECONDS
        if remaining <= 0:
            raise TimeoutError("content_read_deadline_exhausted")
        try:
            output, _ = process.communicate(request, timeout=remaining)
        except subprocess.TimeoutExpired:
            raise TimeoutError("content_read_deadline_exhausted") from None
        remaining_content_time(deadline_monotonic)
        if process.returncode != 0 or not output or len(output) > byte_limit + 1:
            raise OSError("content_read_worker_unavailable")
        status, payload = output[:1], output[1:]
        if status == b"M":
            raise FileNotFoundError("content object not found")
        if status == b"T":
            raise TimeoutError("content_read_deadline_exhausted")
        if status == b"V":
            raise ValueError("content object invalid or exceeded configured byte limit")
        if status != b"O":
            raise OSError("content_read_worker_unavailable")
        return payload
    except BaseException as error:
        primary_error = error
        raise
    finally:
        cleanup_errors: list[str] = []
        cleanup_cancellation: BaseException | None = None
        reaped = process is None

        def retain_cleanup_failure(code: str, error: BaseException) -> None:
            nonlocal cleanup_cancellation
            cleanup_errors.append(code)
            if isinstance(error, (KeyboardInterrupt, SystemExit)) and cleanup_cancellation is None:
                cleanup_cancellation = error

        if process is not None and owner is not None:
            _FAILED_CONTENT_READS[process.pid] = owner
        try:
            if process is not None:
                try:
                    if process.poll() is None:
                        process.kill()
                except (
                    OSError,
                    ValueError,
                    subprocess.SubprocessError,
                    KeyboardInterrupt,
                    SystemExit,
                ) as error:
                    retain_cleanup_failure("worker_stop_failed", error)
                try:
                    process.wait(timeout=max(0.0, deadline_monotonic - time.monotonic()))
                    reaped = True
                except (
                    OSError,
                    ValueError,
                    subprocess.SubprocessError,
                    KeyboardInterrupt,
                    SystemExit,
                ) as error:
                    retain_cleanup_failure("worker_reap_failed", error)
                if native_owner_missing:
                    cleanup_errors.append("worker_identity_unavailable")
                if reaped and owner is not None and owner.native is not None:
                    try:
                        owner.native.confirm_terminal(deadline_monotonic)
                    except (OSError, KeyboardInterrupt, SystemExit) as error:
                        retain_cleanup_failure("guardian_terminal_or_handles_unconfirmed", error)
                readers_finished = True
                for name in ("stdout_thread", "stderr_thread"):
                    reader = getattr(process, name, None)
                    if isinstance(reader, Thread):
                        try:
                            reader.join(timeout=max(0.0, deadline_monotonic - time.monotonic()))
                        except (OSError, RuntimeError, KeyboardInterrupt, SystemExit) as error:
                            retain_cleanup_failure("worker_pipe_reader_join_failed", error)
                        if reader.is_alive():
                            readers_finished = False
                            cleanup_errors.append("worker_pipe_reader_unconfirmed")
                for stream in (process.stdin, process.stdout):
                    if stream is not None and (
                        stream is process.stdin or (reaped and readers_finished)
                    ):
                        try:
                            stream.close()
                        except (OSError, ValueError, KeyboardInterrupt, SystemExit) as error:
                            retain_cleanup_failure("worker_pipe_close_failed", error)
        except BaseException as error:
            retain_cleanup_failure("worker_cleanup_interrupted", error)
        if not cleanup_errors and reaped:
            if process is not None and owner is not None:
                _FAILED_CONTENT_READS.pop(process.pid)
            _CONTENT_READ_CAPACITY.release()
        if cleanup_errors:
            if primary_error is not None:
                primary_error.add_note(
                    "content_read_worker_cleanup_failed:" + ",".join(cleanup_errors)
                )
            else:
                if cleanup_cancellation is not None:
                    raise cleanup_cancellation
                raise OSError("content_read_worker_cleanup_failed")


@dataclass(frozen=True)
class StoredContent:
    """本地和对象存储共享的校验后登记值，不包含公开可用存储路径。"""

    content_hash: str
    size_bytes: int


@dataclass(frozen=True)
class StoredObject(StoredContent):
    """本地文件实现额外保留内部Path；不把S3键伪造成文件路径。"""

    object_path: Path


class ContentStorage(Protocol):
    """原文发布/回收共用的三个IO操作；事实与ACL仍由PG负责。"""

    def store_bytes(self, payload: bytes) -> StoredContent: ...

    def read_verified(
        self, content_hash: str, *, deadline_monotonic: float | None = None
    ) -> bytes: ...

    def delete_object(self, content_hash: str) -> None: ...


class ContentStore:
    """按内容哈希寻址的原文库: 写入原子, 路径与用户输入无关。"""

    def __init__(self, root_directory: Path) -> None:
        self._root = root_directory
        self._root.mkdir(parents=True, exist_ok=True)

    def object_path_for_hash(self, content_hash: str) -> Path:
        """仅接受 64 位十六进制哈希; 目录分片来自哈希本身, 不受用户路径影响。"""
        if not SHA256_PATTERN.fullmatch(content_hash):
            raise ContentPathValidationError("content hash must be 64 lowercase hex characters")
        return self._root / content_hash[:2] / content_hash

    def store_bytes(self, payload: bytes) -> StoredObject:
        """同目录临时落盘后排他发布；已有完整相同对象才复用，不覆盖旧对象。"""
        content_hash = hashlib.sha256(payload).hexdigest()
        object_path = self.object_path_for_hash(content_hash)
        object_path.parent.mkdir(parents=True, exist_ok=True)
        if object_path.exists():
            existing_size = object_path.stat().st_size
            if hashlib.sha256(object_path.read_bytes()).hexdigest() != content_hash:
                raise ValueError(f"existing object corrupted for {content_hash}")
            return StoredObject(
                content_hash=content_hash,
                size_bytes=existing_size,
                object_path=object_path,
            )
        file_descriptor, temporary_name = tempfile.mkstemp(dir=object_path.parent, prefix=".tmp-")
        temporary_identity: tuple[int, int] | None = None
        operation_error: BaseException | None = None
        try:
            try:
                temporary_stat = os.fstat(file_descriptor)
                temporary_identity = (temporary_stat.st_dev, temporary_stat.st_ino)
                with os.fdopen(file_descriptor, "wb", closefd=False) as temporary_file:
                    temporary_file.write(payload)
                    temporary_file.flush()
                    os.fsync(temporary_file.fileno())
            except BaseException as error:
                operation_error = error
                raise
            finally:
                try:
                    os.close(file_descriptor)
                except OSError as close_error:
                    if operation_error is None:
                        raise
                    operation_error.add_note(
                        "temporary content descriptor close failed: " + type(close_error).__name__
                    )
            try:
                os.link(temporary_name, object_path)
            except FileExistsError as publication_error:
                try:
                    existing_payload = self.read_verified(content_hash)
                except (OSError, ValueError):
                    raise publication_error from None
                if existing_payload != payload:
                    raise
        except BaseException as error:
            operation_error = error
            raise
        finally:
            try:
                if temporary_identity is not None:
                    try:
                        remaining_stat = os.lstat(temporary_name)
                    except FileNotFoundError:
                        pass
                    else:
                        if (remaining_stat.st_dev, remaining_stat.st_ino) == temporary_identity:
                            os.unlink(temporary_name)
            except OSError as cleanup_error:
                if operation_error is None:
                    raise
                operation_error.add_note(
                    "temporary content cleanup failed: " + type(cleanup_error).__name__
                )
        return StoredObject(
            content_hash=content_hash, size_bytes=len(payload), object_path=object_path
        )

    def read_verified(self, content_hash: str, *, deadline_monotonic: float | None = None) -> bytes:
        """读取原文并校验哈希; 损坏对象抛错, 不返回未验证内容。"""
        object_path = self.object_path_for_hash(content_hash)
        if deadline_monotonic is None:
            payload = object_path.read_bytes()
        else:
            remaining = remaining_content_time(deadline_monotonic)
            request = json.dumps(
                {
                    "storage": "local",
                    "root_directory": str(self._root.absolute()),
                    "content_hash": content_hash,
                    "remaining_seconds": remaining,
                    "byte_limit": MAX_DEADLINE_CONTENT_BYTES,
                }
            ).encode()
            payload = _read_with_deadline(request, deadline_monotonic, MAX_DEADLINE_CONTENT_BYTES)
        actual_hash = hashlib.sha256(payload).hexdigest()
        if actual_hash != content_hash:
            raise ValueError(f"content hash mismatch for {content_hash}")
        if deadline_monotonic is not None:
            remaining_content_time(deadline_monotonic)
        return payload

    def delete_object(self, content_hash: str) -> None:
        """删除未引用对象; 供写库失败后的清理路径调用。"""
        object_path = self.object_path_for_hash(content_hash)
        if object_path.exists():
            object_path.unlink()
