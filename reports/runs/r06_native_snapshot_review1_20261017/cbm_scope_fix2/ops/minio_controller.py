"""Keep one emergency owner outside the nonce MinIO tree under the original aggregate caps."""

from __future__ import annotations

import errno
import json
import math
import mmap
import os
import socket
import struct
import sys
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

import minio_segment

MAX_CONTROLLER_FDS = 16


class MinioScope:
    """Pre-open kernel capabilities before fork; unknown members never authorize group kill."""

    def __init__(self, nonce: str, deadline: datetime, monotonic_deadline: float) -> None:
        self.nonce = nonce
        self.target = minio_segment.group_for_nonce(nonce)
        self.envelope = self.target.parent
        self.owner = self.envelope / "owner"
        self.deadline = deadline
        self.monotonic_deadline = monotonic_deadline
        self.stop_deadline: float | None = None
        self.parent_pid = os.getpid()
        self.helper_pid: int | None = None
        self.helper_identity: dict[str, object] | None = None
        self.go_identity: dict[str, object] | None = None
        self.handles: dict[str, int] = {}
        self.channel: socket.socket | None = None
        self.peer: socket.socket | None = None
        self.stop_clock: mmap.mmap | None = None
        self.events: list[dict[str, object]] = []
        self.closed_by_emergency = False
        self.failure: BaseException | None = None
        self.error_types: list[str] = []
        self.scope_verified = True
        self.procs_read_recovery_used = False
        if self.envelope.exists():
            raise ValueError("fresh owned MinIO envelope required")
        self.envelope.mkdir()
        for name, value in minio_segment.LIMITS.items():
            self.envelope.joinpath(name).write_text(value)
        self.envelope.joinpath("cgroup.subtree_control").write_text("+cpu +memory +pids")
        self.owner.mkdir()
        self.target.mkdir()
        self.owner.joinpath("cgroup.procs").write_text(str(os.getpid()))
        try:
            for name, path, flags in (
                ("envelope", self.envelope, os.O_RDONLY | os.O_DIRECTORY),
                ("target", self.target, os.O_RDONLY | os.O_DIRECTORY),
                ("owner", self.owner, os.O_RDONLY | os.O_DIRECTORY),
                ("procs", self.target / "cgroup.procs", os.O_RDWR),
                ("envelope_procs", self.envelope / "cgroup.procs", os.O_RDONLY),
                ("events", self.target / "cgroup.events", os.O_RDONLY),
                ("freeze", self.target / "cgroup.freeze", os.O_WRONLY),
                ("kill", self.target / "cgroup.kill", os.O_WRONLY),
                ("owner_procs", self.owner / "cgroup.procs", os.O_RDWR),
                ("boot", Path("/proc/sys/kernel/random/boot_id"), os.O_RDONLY),
            ):
                self.handles[name] = os.open(path, flags | os.O_CLOEXEC)
            self.handles["parent_pidfd"] = os.pidfd_open(self.parent_pid)
            self.handles["helper_slot"] = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
            self.channel, self.peer = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            self.stop_clock = mmap.mmap(-1, 8)
            self.channel.setblocking(False)
            self.peer.setblocking(False)
            self.boot = self.read_handle("boot").strip()
            self.target_inode = os.fstat(self.handles["target"]).st_ino
            self.envelope_inode = os.fstat(self.handles["envelope"]).st_ino
            self.owner_inode = os.fstat(self.handles["owner"]).st_ino
            if self.held_fd_count() > MAX_CONTROLLER_FDS:
                raise RuntimeError("owned MinIO emergency descriptor budget exceeded")
            self.require_scope()
            self.preheld_fd_count = self.held_fd_count()
            self.actual_fd_count_before_fork = len(os.listdir("/proc/self/fd")) - 1
        except BaseException:
            self.close()
            raise

    def held_fd_count(self) -> int:
        return len(self.handles) + int(self.channel is not None) + int(self.peer is not None)

    def read_handle(self, name: str) -> str:
        os.lseek(self.handles[name], 0, os.SEEK_SET)
        return os.read(self.handles[name], 65536).decode()

    def write_handle(self, name: str, value: str) -> None:
        os.lseek(self.handles[name], 0, os.SEEK_SET)
        if os.write(self.handles[name], value.encode()) != len(value):
            raise OSError("owned MinIO kernel capability write incomplete")

    def require_scope(self) -> None:
        if (
            self.target.resolve() != self.target
            or self.target.stat().st_ino != self.target_inode
            or self.envelope.stat().st_ino != self.envelope_inode
            or self.owner.stat().st_ino != self.owner_inode
            or self.read_handle("boot").strip() != self.boot
            or minio_segment.group_for_nonce(self.nonce) != self.target
            or any(
                self.envelope.joinpath(name).read_text().strip() != value
                for name, value in minio_segment.LIMITS.items()
            )
        ):
            raise RuntimeError("owned MinIO emergency scope identity changed")
        if any(path.is_dir() for path in self.target.iterdir()):
            raise RuntimeError("unknown subgroup inside owned MinIO target")
        if {path for path in self.envelope.iterdir() if path.is_dir()} != {
            self.owner,
            self.target,
        } or self.read_handle("envelope_procs").split():
            raise RuntimeError("unknown member or subgroup inside owned MinIO envelope")
        allowed_owner = set() if self.parent_exited() else {self.parent_pid}
        if self.helper_pid == os.getpid():
            allowed_owner.add(os.getpid())
        if {int(value) for value in self.read_handle("owner_procs").split()} - allowed_owner:
            raise RuntimeError("unknown member inside owned MinIO emergency owner")

    def send(self, event: str, **fields: object) -> None:
        if self.channel is None:
            raise RuntimeError("owned MinIO bootstrap channel absent")
        payload = json.dumps({"nonce": self.nonce, "event": event, **fields}).encode()
        if len(payload) > 8192:
            raise ValueError("owned MinIO control message exceeds bound")
        self.channel.send(payload)

    def receive(self) -> dict[str, object] | None:
        if self.channel is None:
            return None
        try:
            payload = self.channel.recv(8193)
        except BlockingIOError:
            return None
        if not payload:
            return None
        value = json.loads(payload)
        if not isinstance(value, dict) or value.get("nonce") != self.nonce or len(payload) > 8192:
            raise ValueError("owned MinIO control message identity differs")
        return value

    def require_helper(self) -> None:
        self.require_scope()
        row = minio_segment.identity(os.getpid())
        if (
            row["cgroup"] != "0::/" + self.target.relative_to("/sys/fs/cgroup").as_posix()
            or row["session_id"] != os.getpid()
        ):
            raise RuntimeError("owned MinIO helper bootstrap identity differs")

    def register_child(self, pid: int) -> None:
        self.go_identity = minio_segment.identity(pid)
        if self.go_identity["parent_pid"] != os.getpid() or self.go_identity["session_id"] != pid:
            raise RuntimeError("owned MinIO direct child birth differs")
        self.send("child_created", pid=pid, identity=self.go_identity)
        end = min(time.monotonic() + 5, self.monotonic_deadline)
        while True:
            message = self.receive()
            if message is not None and message.get("event") == "child_bound":
                return
            if self.parent_exited() or time.monotonic() >= end:
                raise RuntimeError("owned MinIO child birth controller ACK absent")
            time.sleep(0.01)

    def begin_stop(self, hard_end: float) -> None:
        self.stop_deadline = min(hard_end, self.monotonic_deadline)
        if self.stop_clock is None:
            raise RuntimeError("owned MinIO shared shutdown clock absent")
        self.stop_clock[:] = struct.pack("d", self.stop_deadline)
        if not self.parent_exited():
            try:
                self.send("stopping", hard_end=self.stop_deadline)
            except OSError as error:
                self.error_types.append(type(error).__name__)

    def shared_stop_deadline(self) -> float | None:
        if self.stop_clock is None:
            raise RuntimeError("owned MinIO shared shutdown clock absent")
        value: object = struct.unpack("d", self.stop_clock[:])[0]
        if not isinstance(value, float):
            raise RuntimeError("owned MinIO shared shutdown clock type differs")
        if value == 0:
            return None
        if not math.isfinite(value) or value > self.monotonic_deadline or value <= 0:
            raise RuntimeError("owned MinIO shared shutdown clock invalid")
        return value

    def parent_exited(self) -> bool:
        return minio_segment.pidfd_exited(self.handles["parent_pidfd"])

    def parent_death_cleanup(self, hard_end: float) -> bool:
        if not self.parent_exited():
            return False
        self.require_helper()
        self.helper_identity = minio_segment.identity(os.getpid())
        self.helper_pid = os.getpid()
        self.write_handle("owner_procs", str(os.getpid()))
        return self.emergency_stop(hard_end)

    def prove_members(self) -> set[int]:
        if self.helper_identity is None or self.helper_pid is None:
            raise RuntimeError("owned MinIO helper birth unbound")
        members = {int(value) for value in self.read_handle("procs").split()}
        scope = "0::/" + self.target.relative_to("/sys/fs/cgroup").as_posix()
        rows = {pid: minio_segment.identity(pid) for pid in members}
        for pid, row in rows.items():
            if row["cgroup"] != scope:
                raise RuntimeError("owned MinIO emergency member scope changed")
            if pid == self.helper_pid:
                if not minio_segment.same_kernel_identity(row, self.helper_identity):
                    raise RuntimeError("owned MinIO helper birth changed")
                continue
            session_proven = row["session_id"] == self.helper_pid and int(
                str(row["start_ticks"])
            ) >= int(str(self.helper_identity["start_ticks"]))
            if self.go_identity is not None:
                session_proven = session_proven or (
                    row["session_id"] == self.go_identity["pid"]
                    and int(str(row["start_ticks"])) >= int(str(self.go_identity["start_ticks"]))
                )
            ancestor = pid
            visited: set[int] = set()
            while ancestor != self.helper_pid and ancestor in rows and ancestor not in visited:
                visited.add(ancestor)
                ancestor = int(str(rows[ancestor]["parent_pid"]))
            if ancestor != self.helper_pid and not session_proven:
                raise RuntimeError("unknown member refuses owned MinIO whole-group kill")
        return members

    def emergency_stop(self, hard_end: float) -> bool:
        self.require_scope()
        if time.monotonic() >= hard_end:
            raise RuntimeError("owned MinIO emergency shutdown hard budget exhausted")
        self.write_handle("freeze", "1")
        try:
            while "frozen 1" not in self.read_handle("events"):
                if time.monotonic() >= hard_end:
                    raise RuntimeError("owned MinIO freeze kernel ACK missing")
                time.sleep(0.01)
            self.require_scope()
            members = self.prove_members()
            if members != {int(value) for value in self.read_handle("procs").split()}:
                raise RuntimeError("owned MinIO frozen membership changed")
            self.write_handle("kill", "1")
            while "populated 0" not in self.read_handle("events"):
                if time.monotonic() >= hard_end:
                    raise RuntimeError("owned MinIO target kernel empty ACK missing")
                time.sleep(0.01)
            self.closed_by_emergency = True
            return True
        finally:
            self.write_handle("freeze", "0")

    def close(self) -> None:
        errors: list[OSError] = []
        channels = (self.channel, self.peer)
        self.channel = None
        self.peer = None
        for channel in channels:
            if channel is not None:
                try:
                    channel.close()
                except OSError as error:
                    errors.append(error)
        if self.stop_clock is not None:
            self.stop_clock.close()
            self.stop_clock = None
        while self.handles:
            _, handle = self.handles.popitem()
            try:
                os.close(handle)
            except OSError as error:
                errors.append(error)
        if errors and sys.exc_info()[1] is None:
            raise errors[0]

    def finish_pinned(self, hard_end: float) -> None:
        proven = {}
        for name, row in (
            ("helper_pidfd", self.helper_identity),
            ("go_pidfd", self.go_identity),
        ):
            if name in self.handles and row is not None:
                proven[int(str(row["pid"]))] = (self.handles[name], row)
        self.error_types.extend(minio_segment.finish_proven_handles(proven, hard_end))

    def stop_remaining(self, hard_end: float) -> None:
        try:
            try:
                members = self.read_handle("procs").split()
            except OSError as error:
                if (
                    not self.scope_verified
                    or time.monotonic() >= hard_end
                    or self.procs_read_recovery_used
                    or error.errno not in {errno.EMFILE, errno.ENFILE, errno.ENOMEM, errno.EAGAIN}
                ):
                    raise
                self.procs_read_recovery_used = True
                self.error_types.append(type(error).__name__)
                if self.failure is None:
                    self.failure = error
                self.require_scope()
                if time.monotonic() >= hard_end:
                    raise RuntimeError("owned MinIO recovery read hard budget exhausted") from error
                members = self.read_handle("procs").split()
            if not members:
                return
            if not self.scope_verified:
                self.finish_pinned(hard_end)
                return
            self.emergency_stop(hard_end)
        except BaseException as error:
            self.scope_verified = False
            self.error_types.append(type(error).__name__)
            if self.failure is None:
                self.failure = error
            self.finish_pinned(hard_end)


def run_owned_minio(activation: dict[str, object], entry: Callable[[MinioScope], None]) -> None:
    """Fork exactly one helper; all added processes remain under the old aggregate envelope."""
    started = datetime.now(minio_segment.ZONE)
    lifecycle = json.loads(
        Path("/tmp/dianzi-docker-static-r01-20261014/runtime/lifecycle.json").read_bytes()
    )
    deadline = min(
        started + timedelta(seconds=minio_segment.TOTAL_SECONDS),
        datetime.fromisoformat(lifecycle["deadline"]),
    )
    if (deadline - started).total_seconds() < minio_segment.TOTAL_SECONDS:
        raise ValueError("full owned MinIO window does not fit daemon deadline")
    scope = MinioScope(
        str(activation["nonce"]),
        deadline,
        time.monotonic() + minio_segment.TOTAL_SECONDS,
    )
    if scope.channel is None or scope.peer is None:
        raise RuntimeError("owned MinIO prepared channels unavailable")
    try:
        helper_pid = os.fork()
    except BaseException:
        scope.close()
        raise
    if helper_pid == 0:
        try:
            scope.channel.close()
            scope.channel = scope.peer
            scope.peer = None
            os.close(scope.handles.pop("helper_slot"))
            scope.write_handle("procs", str(os.getpid()))
            os.setsid()
            limit = time.monotonic() + 5
            while True:
                message = scope.receive()
                if message is not None:
                    if message.get("event") != "ready":
                        raise RuntimeError("owned MinIO bootstrap ACK identity differs")
                    break
                if scope.parent_exited() or time.monotonic() >= limit:
                    raise RuntimeError("owned MinIO parent bootstrap ACK absent")
                time.sleep(0.01)
            entry(scope)
            scope.send("finished", error_type=None)
            code = 0
        except BaseException as error:
            try:
                scope.send(
                    "finished",
                    error_type=type(error).__name__,
                    errno=error.errno if isinstance(error, OSError) else None,
                )
            except (OSError, RuntimeError):
                scope.error_types.append("parent_control_channel_unavailable")
            code = 1
        finally:
            minio_segment.release_cleanup_capacity()
            scope.close()
        os._exit(code)
    scope.helper_pid = helper_pid
    scope.peer.close()
    scope.peer = None
    try:
        os.close(scope.handles.pop("helper_slot"))
        scope.handles["helper_pidfd"] = os.pidfd_open(helper_pid)
        scope.helper_identity = minio_segment.identity(helper_pid)
        limit = time.monotonic() + 5
        while (
            scope.helper_identity["session_id"] != helper_pid
            or scope.helper_identity["cgroup"]
            != "0::/" + scope.target.relative_to("/sys/fs/cgroup").as_posix()
        ):
            if time.monotonic() >= limit:
                raise RuntimeError("owned MinIO helper independent session not ready")
            time.sleep(0.01)
            scope.helper_identity = minio_segment.identity(helper_pid)
        minio_segment.write(
            "minio_controller_start.json",
            {
                "started_at": started.isoformat(),
                "controller": minio_segment.identity(os.getpid()),
                "helper": scope.helper_identity,
                "boot_id": scope.boot,
                "nonce": scope.nonce,
                "envelope": str(scope.envelope),
                "target": str(scope.target),
                "target_inode": scope.target_inode,
                "held_controller_fd_count": scope.held_fd_count(),
                "owned_preheld_fd_count_before_fork": scope.preheld_fd_count,
                "actual_fd_count_before_fork": scope.actual_fd_count_before_fork,
                "actual_process_fd_count": len(os.listdir("/proc/self/fd")) - 1,
                "aggregate_limits": minio_segment.LIMITS,
                "hard_deadline": deadline.isoformat(),
            },
        )
        scope.send("ready")
        while True:
            shared_end = scope.shared_stop_deadline()
            if shared_end is not None:
                scope.stop_deadline = min(scope.stop_deadline or shared_end, shared_end)
            message = scope.receive()
            if message is None and minio_segment.pidfd_exited(scope.handles["helper_pidfd"]):
                break
            if message is not None:
                event = message.get("event")
                if event == "child_created":
                    pid = message.get("pid")
                    if not isinstance(pid, int) or isinstance(pid, bool):
                        raise ValueError("owned MinIO child PID field invalid")
                    row = message.get("identity")
                    if not isinstance(row, dict):
                        raise ValueError("owned MinIO child birth identity absent")
                    actual = minio_segment.identity(pid)
                    if (
                        not minio_segment.same_kernel_identity(actual, row)
                        or row["pid"] != pid
                        or row["parent_pid"] != helper_pid
                        or row["session_id"] != pid
                        or row["cgroup"] != scope.helper_identity["cgroup"]
                    ):
                        raise RuntimeError("owned MinIO child birth binding differs")
                    scope.go_identity = row
                    try:
                        scope.handles["go_pidfd"] = os.pidfd_open(pid)
                    except OSError as error:
                        scope.error_types.append(type(error).__name__)
                    scope.send("child_bound")
                elif event == "stopping":
                    hard_end = message.get("hard_end")
                    if not isinstance(hard_end, (int, float)) or isinstance(hard_end, bool):
                        raise ValueError("owned MinIO shared stop deadline invalid")
                    scope.stop_deadline = min(hard_end, scope.monotonic_deadline)
                elif event == "finished" and message.get("error_type") is not None:
                    scope.error_types.append(str(message["error_type"]))
                    scope.failure = (
                        OSError(message["errno"], "owned MinIO helper resource failure")
                        if isinstance(message.get("errno"), int)
                        else OSError("owned MinIO helper failed")
                        if message["error_type"] == "OSError"
                        else RuntimeError("owned MinIO helper failed")
                    )
                scope.events.append(
                    {
                        "event": event,
                        "observed_at": datetime.now(minio_segment.ZONE).isoformat(),
                    }
                )
                scope.events = scope.events[-16:]
            now = time.monotonic()
            remaining_wall = (deadline - datetime.now(minio_segment.ZONE)).total_seconds()
            if scope.stop_deadline is None and (
                now >= scope.monotonic_deadline - 15 or remaining_wall <= 15
            ):
                scope.stop_deadline = min(
                    now + 15, scope.monotonic_deadline, now + max(0, remaining_wall)
                )
                scope.send("stop", hard_end=scope.stop_deadline)
            if scope.stop_deadline is not None and now >= scope.stop_deadline - 2:
                scope.stop_remaining(scope.stop_deadline)
                break
            time.sleep(0.01)
        if minio_segment.pidfd_exited(scope.handles["helper_pidfd"]):
            _, status = os.waitpid(helper_pid, 0)
            if status != 0 and scope.failure is None:
                scope.failure = RuntimeError("owned MinIO helper exited unsuccessfully")
        remaining = scope.read_handle("procs").split()
        if remaining:
            end = scope.stop_deadline or min(time.monotonic() + 15, scope.monotonic_deadline)
            scope.stop_remaining(end)
    except BaseException as error:
        scope.error_types.append(type(error).__name__)
        if scope.failure is None:
            scope.failure = error
    finally:
        try:
            scope.stop_deadline = scope.stop_deadline or min(
                time.monotonic() + 15, scope.monotonic_deadline
            )
            if scope.helper_identity is not None and not scope.closed_by_emergency:
                scope.stop_remaining(scope.stop_deadline)
            minio_segment.write(
                "minio_controller_end.json",
                {
                    "started_at": started.isoformat(),
                    "ended_at": datetime.now(minio_segment.ZONE).isoformat(),
                    "nonce": scope.nonce,
                    "target_inode": scope.target_inode,
                    "target_empty": scope.read_handle("procs").split() == [],
                    "emergency_kernel_empty_ack": scope.closed_by_emergency,
                    "helper_pidfd_kernel_exit_ack": minio_segment.pidfd_exited(
                        scope.handles["helper_pidfd"]
                    )
                    if "helper_pidfd" in scope.handles
                    else False,
                    "events": scope.events,
                    "error_types": scope.error_types[-16:],
                    "whole_tree_cleanup_guaranteed": scope.scope_verified
                    and scope.read_handle("procs").split() == [],
                    "formal_six_hour_pass": False,
                },
            )
        finally:
            scope.close()
    if scope.failure is not None:
        raise scope.failure
