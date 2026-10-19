"""Stop-file acknowledgements are written by actual worker/beat interpreters only."""

from __future__ import annotations

import ctypes
import json
import os
import threading
import time
from ctypes import wintypes
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

CONTROL_DIRECTORY = Path(__file__).resolve().parent / "control"
WATCH_POLL_SECONDS = 0.05
ACK_LIMIT_BYTES = 4096
ProcessRole = Literal["worker", "beat"]


def owned_control_path(role: ProcessRole, kind: Literal["stop", "ready", "ack"]) -> Path:
    """No caller-supplied path, URL or filename is accepted."""
    if role not in ("worker", "beat") or kind not in ("stop", "ready", "ack"):
        raise ValueError("unknown owned control role")
    expected = Path(__file__).resolve().parent / "control"
    if expected != CONTROL_DIRECTORY or CONTROL_DIRECTORY.resolve() != expected:
        raise ValueError("owned control directory identity differs")
    for parent in CONTROL_DIRECTORY.parents:
        if parent.is_symlink() or parent.is_junction():
            raise ValueError("owned control parent is redirected")
    if CONTROL_DIRECTORY.is_symlink() or CONTROL_DIRECTORY.is_junction():
        raise ValueError("owned control directory is redirected")
    return CONTROL_DIRECTORY / f"{role}_{kind}.json"


def reject_previous_control_files(role: ProcessRole) -> None:
    for kind in ("stop", "ready", "ack"):
        if owned_control_path(role, kind).exists():
            raise RuntimeError("old owned process control files prohibit startup")


def current_windows_identity() -> dict[str, int]:
    """The current-process handle binds the actual PID to its kernel creation time."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    creation, exit_time, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
    if not kernel.GetProcessTimes(
        kernel.GetCurrentProcess(),
        ctypes.byref(creation),
        ctypes.byref(exit_time),
        ctypes.byref(kernel_time),
        ctypes.byref(user_time),
    ):
        raise OSError("owned process creation time unavailable")
    return {
        "actual_pid": os.getpid(),
        "creation_ticks": creation.dwLowDateTime + (creation.dwHighDateTime << 32),
    }


def write_process_control(
    role: ProcessRole, kind: Literal["ready", "ack"], identity: dict[str, int]
) -> None:
    path = owned_control_path(role, kind)
    payload = json.dumps(
        {"role": role, "observed_at": datetime.now(UTC).isoformat(), **identity}
    ).encode()
    if len(payload) > ACK_LIMIT_BYTES:
        raise RuntimeError("owned control receipt budget exceeded")
    with path.open("xb") as output:
        output.write(payload + b"\n")
        output.flush()
        os.fsync(output.fileno())


def read_stop_request(role: ProcessRole) -> bool:
    path = owned_control_path(role, "stop")
    if path.is_symlink() or path.is_junction():
        raise RuntimeError("owned stop request is invalid")
    if not path.exists():
        return False
    if path.stat().st_size > ACK_LIMIT_BYTES:
        raise RuntimeError("owned stop request is invalid")
    content = json.loads(path.read_bytes())
    if content != {"role": role, "owned_stop": True}:
        raise RuntimeError("owned stop request contract differs")
    return True


def acknowledge_stop(role: ProcessRole, identity: dict[str, int]) -> None:
    """Solo worker checks should_stop before consuming the next task; beat exits now."""
    write_process_control(role, "ack", identity)
    if role == "worker":
        from celery.worker import state

        state.should_stop = 0
    else:
        os._exit(0)


def install_owned_stop_watcher(role: ProcessRole) -> None:
    """The caller must have verified root authorization before importing product runtime."""
    reject_previous_control_files(role)
    CONTROL_DIRECTORY.mkdir(exist_ok=True)
    identity = current_windows_identity()
    write_process_control(role, "ready", identity)

    def watch() -> None:
        try:
            while not read_stop_request(role):
                time.sleep(WATCH_POLL_SECONDS)
            acknowledge_stop(role, identity)
        except Exception:
            os._exit(70)

    threading.Thread(target=watch, name=f"r06_owned_{role}_stop", daemon=True).start()
