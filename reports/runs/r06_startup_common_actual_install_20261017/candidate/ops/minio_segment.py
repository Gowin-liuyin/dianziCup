"""Run a new MinIO generation with original caps, bounded time and pidfd exit acknowledgement."""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import select
import selectors
import shutil
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from minio_controller import MinioScope

OPS = Path("/mnt/d/dianzi-runtime-cache/r06-f3-ops-20261017")
RESOURCE = Path("/tmp/dianzi-minio-r02-20261015")
PARENT = Path("/sys/fs/cgroup/dianzi-r01-20261014")
CORE = Path("/mnt/d/dianzi-runtime-cache/r06-f3-core-20261017")
HASH = "10ec54df2dc51dfa1399b7187d9377a20bd1b50f22d123a756175173b0cfff75"
TOTAL_SECONDS = 22500
ZONE = timezone(timedelta(hours=8))
LIMITS = {
    "memory.max": "536870912",
    "memory.swap.max": "0",
    "pids.max": "128",
    "cpu.max": "100000 100000",
}
RESERVE_FDS = 132
IO_RESERVE_FDS = 4


class CleanupReserve:
    """Own bounded low descriptor slots before Popen; release them for IO and one recovery."""

    def __init__(self) -> None:
        import resource

        limit, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        highest = max(int(name) for name in os.listdir("/proc/self/fd"))
        if limit != resource.RLIM_INFINITY and limit <= highest + RESERVE_FDS + 6:
            raise OSError(errno.EMFILE, "owned MinIO descriptor capacity unavailable before Popen")
        self.handles: list[int] = []
        self.recovery_used = False
        self.io_released = False
        try:
            for _ in range(RESERVE_FDS):
                self.handles.append(os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC))
        except BaseException:
            self.release_all()
            raise

    def release_io(self) -> None:
        if not self.io_released:
            self.io_released = True
            for _ in range(min(IO_RESERVE_FDS, len(self.handles))):
                os.close(self.handles.pop(0))

    def release_pin_slot(self) -> None:
        if self.handles:
            os.close(self.handles.pop(0))

    def recover(self, error: OSError) -> bool:
        if self.recovery_used or error.errno not in {
            errno.EMFILE,
            errno.ENFILE,
            errno.ENOMEM,
            errno.EPERM,
        }:
            return False
        self.recovery_used = True
        self.release_all()
        return True

    def release_all(self) -> None:
        while self.handles:
            os.close(self.handles.pop())


_cleanup_reserve: CleanupReserve | None = None


def prepare_cleanup_capacity() -> None:
    global _cleanup_reserve
    if _cleanup_reserve is not None and _cleanup_reserve.handles:
        raise RuntimeError("owned MinIO cleanup reserve already allocated")
    _cleanup_reserve = CleanupReserve()


def release_cleanup_io() -> None:
    if _cleanup_reserve is not None:
        _cleanup_reserve.release_io()


def release_cleanup_capacity() -> None:
    if _cleanup_reserve is not None:
        _cleanup_reserve.release_all()


def recover_cleanup_capacity(error: OSError) -> bool:
    return _cleanup_reserve is not None and _cleanup_reserve.recover(error)


def pin_owned_process(pid: int) -> int:
    if _cleanup_reserve is not None:
        _cleanup_reserve.release_pin_slot()
    try:
        return os.pidfd_open(pid)
    except OSError as error:
        if not recover_cleanup_capacity(error):
            raise
        return os.pidfd_open(pid)


def identity(pid: int) -> dict[str, object]:
    path = Path("/proc") / str(pid)
    fields = path.joinpath("stat").read_text().rpartition(")")[2].split()
    return {
        "pid": pid,
        "start_ticks": fields[19],
        "parent_pid": int(fields[1]),
        "session_id": int(fields[3]),
        "executable": str(path.joinpath("exe").resolve()),
        "cgroup": path.joinpath("cgroup").read_text().strip(),
    }


def group_for_nonce(nonce: str) -> Path:
    if len(nonce) != 32 or any(character not in "abcdef0123456789" for character in nonce):
        raise ValueError("fixed generation nonce required")
    suffix = ""
    state_path = OPS / "launch_state.json"
    if state_path.exists():
        from configuration import unique_json_object, validate_launch_state

        state = validate_launch_state(
            json.loads(state_path.read_bytes(), object_pairs_hook=unique_json_object)
        )
        if state["nonce"] != nonce:
            raise ValueError("MinIO launch nonce differs")
        suffix = "-" + str(state["observation_id"])
    return (
        PARENT
        / ("minio-r06-envelope-" + nonce + suffix)
        / ("minio-r06-nine-script-" + nonce + suffix)
    )


def check_relaunch(activation: dict[str, object]) -> None:
    """Read the previous generation's exact kernel scope; never remove or signal a cgroup."""
    from configuration import unique_json_object

    group = group_for_nonce(str(activation["nonce"]))
    if not (OPS / "launch_state.json").exists():
        if group.parent.exists() or any(
            (OPS / name).exists() for name in ("minio_start.json", "minio_controller_start.json")
        ):
            raise ValueError("old nonce MinIO scope occupied or unbound; no cleanup authorized")
        return
    start = json.loads(
        (OPS / "minio_controller_start.json").read_bytes(),
        object_pairs_hook=unique_json_object,
    )
    end = json.loads(
        (OPS / "minio_controller_end.json").read_bytes(),
        object_pairs_hook=unique_json_object,
    )
    service_end = json.loads(
        (OPS / "minio_end.json").read_bytes(), object_pairs_hook=unique_json_object
    )
    if any(row.get("nonce") != activation["nonce"] for row in (start, end, service_end)):
        raise ValueError("previous MinIO nonce differs")
    if (
        start["target"] != str(group)
        or start["envelope"] != str(group.parent)
        or start["boot_id"] != Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    ):
        raise ValueError("previous MinIO scope or boot differs")
    if (
        group.resolve() != group
        or group.is_symlink()
        or group.stat().st_ino != start["target_inode"]
        or end["target_inode"] != start["target_inode"]
    ):
        raise ValueError("previous MinIO kernel inode differs")
    if any(
        end.get(key) is not True
        for key in (
            "target_empty",
            "whole_tree_cleanup_guaranteed",
            "helper_pidfd_kernel_exit_ack",
        )
    ) or not (
        service_end.get("pidfd_kernel_exit_ack") is True
        or service_end.get("waitpid_kernel_exit_ack") is True
    ):
        raise ValueError("previous MinIO exit ACK incomplete")
    if start["started_at"] != end["started_at"] or any(
        group.parent.joinpath(name).read_text().strip() != value for name, value in LIMITS.items()
    ):
        raise ValueError("previous MinIO resource binding differs")
    owner = group.parent / "owner"
    if {path for path in group.parent.iterdir() if path.is_dir()} != {
        owner,
        group,
    } or any(path.is_dir() for path in group.iterdir()):
        raise ValueError("foreign MinIO subgroup present")
    if any(
        path.joinpath("cgroup.procs").read_text().split() for path in (group.parent, owner, group)
    ):
        raise ValueError("previous MinIO group still occupied")
    for identity_row in (start["controller"], start["helper"]):
        if Path("/proc", str(identity_row["pid"])).exists():
            raise ValueError("previous MinIO PID present; no cleanup authorized")


def require_activation() -> dict[str, object]:
    from configuration import unique_json_object, validate_activation

    activation = json.loads(
        (OPS / "activation.json").read_bytes(), object_pairs_hook=unique_json_object
    )
    if not isinstance(activation, dict):
        raise ValueError("activation object required")
    prepared = json.loads(
        (OPS / "prepared.json").read_bytes(), object_pairs_hook=unique_json_object
    )
    if not isinstance(prepared, dict):
        raise ValueError("prepared object required")
    if OPS.resolve() != OPS or OPS.is_symlink():
        raise ValueError("new operations path redirected")
    return validate_activation(prepared, activation, OPS, CORE)


def write(name: str, value: object) -> None:
    with (OPS / name).open("x", encoding="utf-8") as output:
        json.dump(value, output, indent=2)
        output.write("\n")


def same_kernel_identity(actual: dict[str, object], expected: dict[str, object]) -> bool:
    """Parent adoption changes ancestry while held birth and scope identities remain fixed."""
    return {key: value for key, value in actual.items() if key != "parent_pid"} == {
        key: value for key, value in expected.items() if key != "parent_pid"
    }


def stop_child(
    process: subprocess.Popen[bytes],
    pidfd: int,
    expected: dict[str, object] | None,
    group: Path,
    stop_deadline: float | None = None,
) -> bool:
    started = time.monotonic()
    hard_end = min(started + 15, stop_deadline if stop_deadline is not None else started + 15)
    release_cleanup_io()
    try:
        return stop_child_once(process, pidfd, expected, group, stop_deadline)
    except OSError as error:
        if recover_cleanup_capacity(error):
            return stop_child_once(process, pidfd, expected, group, hard_end)
        finish_proven_handles(
            {process.pid: (pidfd, expected)} if expected is not None else {}, hard_end
        )
        raise


def stop_child_once(
    process: subprocess.Popen[bytes],
    pidfd: int,
    expected: dict[str, object] | None,
    group: Path,
    stop_deadline: float | None,
) -> bool:
    stop_started = time.monotonic()
    hard_end = min(stop_started + 15, stop_deadline or stop_started + 15)
    if process.poll() is None:
        if expected is not None and not same_kernel_identity(identity(process.pid), expected):
            raise ValueError("owned MinIO child kernel identity changed")
        if (
            expected is not None
            and expected["cgroup"] != "0::/" + group.relative_to("/sys/fs/cgroup").as_posix()
        ):
            raise ValueError("owned MinIO child cgroup differs")
        members = set(group.joinpath("cgroup.procs").read_text().split())
        if members - {str(os.getpid()), str(process.pid)}:
            try:
                return stop_owned_tree(process, pidfd, expected, group, stop_started, hard_end)
            except (RuntimeError, OSError):
                if (
                    process.poll() is None
                    and expected is not None
                    and same_kernel_identity(identity(process.pid), expected)
                ):
                    signal.pidfd_send_signal(pidfd, signal.SIGTERM)
                    try:
                        process.wait(
                            timeout=max(0, min(stop_started + 10, hard_end) - time.monotonic())
                        )
                    except subprocess.TimeoutExpired:
                        if not same_kernel_identity(identity(process.pid), expected):
                            raise ValueError(
                                "owned MinIO child identity changed before KILL"
                            ) from None
                        signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                        process.wait(timeout=max(0, hard_end - time.monotonic()))
                raise
        signal.pidfd_send_signal(pidfd, signal.SIGTERM)
        try:
            process.wait(
                timeout=10
                if stop_deadline is None
                else max(0, min(10, hard_end - time.monotonic()))
            )
        except subprocess.TimeoutExpired:
            signal.pidfd_send_signal(pidfd, signal.SIGKILL)
            process.wait(timeout=max(0, min(5, hard_end - time.monotonic())))
    try:
        with selectors.DefaultSelector() as acknowledgement:
            acknowledgement.register(pidfd, selectors.EVENT_READ)
            acknowledged = bool(acknowledgement.select(timeout=0))
    except OSError:
        acknowledged = pidfd_exited(pidfd)
    if not acknowledged:
        raise RuntimeError("owned MinIO pidfd kernel exit ACK unavailable")
    members = set(group.joinpath("cgroup.procs").read_text().split())
    if members != {str(os.getpid())}:
        return stop_owned_tree(process, pidfd, expected, group, stop_started, hard_end)
    return True


def pidfd_exited(pidfd: int) -> bool:
    poller = select.poll()
    poller.register(pidfd, select.POLLIN)
    events = poller.poll(0)
    if any(event & (select.POLLNVAL | select.POLLERR) for _, event in events):
        raise RuntimeError("owned MinIO pidfd is invalid")
    return any(event & select.POLLIN for _, event in events)


def stop_direct_without_pidfd(
    process: subprocess.Popen[bytes],
    expected: dict[str, object] | None,
    group: Path,
    hard_end: float,
) -> bool:
    """Use the unreaped Popen child relationship on pidfd failure, without claiming pidfd ACK."""
    scope = "0::/" + group.relative_to("/sys/fs/cgroup").as_posix()
    members = set(group.joinpath("cgroup.procs").read_text().split())
    if members - {str(os.getpid()), str(process.pid)}:
        raise RuntimeError("pidfd unavailable for owned MinIO descendants")
    if process.poll() is None:
        actual = identity(process.pid)
        if (
            expected is None
            or not same_kernel_identity(actual, expected)
            or actual["cgroup"] != scope
            or actual["parent_pid"] != os.getpid()
        ):
            raise RuntimeError("pidfd unavailable and Popen child identity unconfirmed")
        process.terminate()
        try:
            process.wait(timeout=max(0, min(10, hard_end - time.monotonic())))
        except subprocess.TimeoutExpired:
            if not same_kernel_identity(identity(process.pid), expected):
                raise RuntimeError("Popen child identity changed before KILL") from None
            process.kill()
            process.wait(timeout=max(0, min(5, hard_end - time.monotonic())))
    if group.joinpath("cgroup.procs").read_text().split() != [str(os.getpid())]:
        raise RuntimeError("Popen wait ACK did not confirm empty owned child scope")
    return True


def stop_owned_tree(
    process: subprocess.Popen[bytes],
    pidfd: int,
    expected: dict[str, object] | None,
    group: Path,
    stop_started: float,
    hard_end: float,
) -> bool:
    """Pin and close proven descendants in this exclusive nonce group within one 15s budget."""
    if (
        group.resolve() != group
        or group_for_nonce(group.name.removeprefix("minio-r06-nine-script-")) != group
    ):
        raise RuntimeError("owned MinIO generation contains unconfirmed descendants")
    scope = "0::/" + group.relative_to("/sys/fs/cgroup").as_posix()
    owner = identity(os.getpid())
    if owner["cgroup"] != scope or any(
        group.parent.joinpath(name).read_text().strip() != value for name, value in LIMITS.items()
    ):
        raise RuntimeError("owned MinIO group identity or limits changed")
    group_stat = group.stat()
    boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    if expected is None or expected.get("pid") != process.pid or expected.get("cgroup") != scope:
        raise RuntimeError("owned MinIO child provenance unavailable")
    held: dict[int, tuple[int, dict[str, object]]] = {process.pid: (pidfd, expected)}
    proven: dict[int, tuple[int, dict[str, object]]] = {}
    if not pidfd_exited(pidfd) and same_kernel_identity(identity(process.pid), expected):
        proven[process.pid] = held[process.pid]
    signalled: set[int] = set()
    try:
        while True:
            if (
                identity(os.getpid()) != owner
                or Path("/proc/sys/kernel/random/boot_id").read_text().strip() != boot
                or group.stat().st_ino != group_stat.st_ino
            ):
                raise RuntimeError("owned MinIO supervisor or group identity changed")
            members = {int(value) for value in group.joinpath("cgroup.procs").read_text().split()}
            for member in members - {os.getpid()} - held.keys():
                row = identity(member)
                handle = pin_owned_process(member)
                try:
                    if not same_kernel_identity(identity(member), row) or row["cgroup"] != scope:
                        raise RuntimeError("owned MinIO descendant identity changed")
                    held[member] = (handle, row)
                    if member_has_proven_ancestry(member, held, os.getpid(), expected, process.pid):
                        proven[member] = held[member]
                except BaseException:
                    os.close(handle)
                    raise
            for member in members - {os.getpid()}:
                row = held[member][1]
                if row.get("pid") != member:
                    raise RuntimeError("owned MinIO descendant identity unavailable")
                if not member_has_proven_ancestry(member, held, os.getpid(), expected, process.pid):
                    raise RuntimeError("owned MinIO generation contains unconfirmed descendants")
                proven[member] = held[member]
            live = [
                (member, handle, row)
                for member, (handle, row) in held.items()
                if not pidfd_exited(handle)
            ]
            if not live:
                process.wait(timeout=0)
                if group.joinpath("cgroup.procs").read_text().split() != [str(os.getpid())]:
                    if time.monotonic() >= hard_end:
                        raise RuntimeError(
                            "owned MinIO tree kernel exit ACK unavailable within hard budget"
                        )
                    time.sleep(min(0.01, max(0, hard_end - time.monotonic())))
                    continue
                return True
            now = time.monotonic()
            if now >= hard_end:
                raise RuntimeError(
                    "owned MinIO tree kernel exit ACK unavailable within hard budget"
                )
            kill_phase = now >= min(stop_started + 10, hard_end)
            for member, handle, row in live:
                if not same_kernel_identity(identity(member), row):
                    raise RuntimeError("owned MinIO descendant identity changed before signal")
                if kill_phase or member not in signalled:
                    signal.pidfd_send_signal(
                        handle, signal.SIGKILL if kill_phase else signal.SIGTERM
                    )
                    signalled.add(member)
            time.sleep(min(0.01, max(0, hard_end - time.monotonic())))
    finally:
        try:
            cleanup_errors = finish_proven_handles(proven, hard_end)
            if cleanup_errors and sys.exc_info()[1] is None:
                raise RuntimeError("owned MinIO proven handle cleanup incomplete")
        finally:
            for member, (handle, _) in held.items():
                if member != process.pid:
                    os.close(handle)


def member_has_proven_ancestry(
    member: int,
    held: dict[int, tuple[int, dict[str, object]]],
    owner_pid: int,
    expected: dict[str, object],
    child_pid: int,
) -> bool:
    row = held[member][1]
    ancestor = member
    visited: set[int] = set()
    while ancestor in held and ancestor not in visited:
        visited.add(ancestor)
        ancestor = int(str(held[ancestor][1].get("parent_pid", -1)))
    session_proven = (
        expected.get("session_id") == child_pid
        and row.get("session_id") == child_pid
        and int(str(row["start_ticks"])) >= int(str(expected["start_ticks"]))
    )
    return ancestor == owner_pid or session_proven


def finish_proven_handles(
    held: dict[int, tuple[int, dict[str, object]]], hard_end: float
) -> list[str]:
    """An allocation failure must not discard previously proven pidfd cleanup capabilities."""
    term_end = hard_end - 5
    live: list[tuple[int, int, dict[str, object]]] = []
    errors: list[str] = []
    for member, (handle, row) in held.items():
        try:
            if pidfd_exited(handle):
                continue
            try:
                actual = identity(member)
            except OSError as error:
                if recover_cleanup_capacity(error):
                    actual = identity(member)
                elif error.errno in {errno.EMFILE, errno.ENFILE, errno.ENOMEM}:
                    actual = row
                else:
                    raise
            if not same_kernel_identity(actual, row):
                raise RuntimeError("proven MinIO member identity changed")
            live.append((member, handle, row))
            signal.pidfd_send_signal(handle, signal.SIGTERM)
        except ProcessLookupError:
            if not pidfd_exited(handle):
                errors.append("ProcessLookupError")
        except OSError as error:
            errors.append(type(error).__name__)
        except RuntimeError as error:
            errors.append(type(error).__name__)
    while live and time.monotonic() < term_end:
        live = [(member, handle, row) for member, handle, row in live if not pidfd_exited(handle)]
        if live:
            time.sleep(min(0.01, max(0, term_end - time.monotonic())))
    for member, handle, row in live:
        try:
            if pidfd_exited(handle):
                continue
            try:
                actual = identity(member)
            except OSError as error:
                if error.errno not in {errno.EMFILE, errno.ENFILE, errno.ENOMEM}:
                    raise
                actual = row
            if not same_kernel_identity(actual, row):
                raise RuntimeError("proven MinIO member identity changed before KILL")
            signal.pidfd_send_signal(handle, signal.SIGKILL)
        except ProcessLookupError:
            if not pidfd_exited(handle):
                errors.append("ProcessLookupError")
        except (OSError, RuntimeError) as error:
            errors.append(type(error).__name__)
    while live and time.monotonic() < hard_end:
        live = [(member, handle, row) for member, handle, row in live if not pidfd_exited(handle)]
        if live:
            time.sleep(min(0.01, max(0, hard_end - time.monotonic())))
    if live:
        errors.append("missing_kernel_exit_ack")
    return errors


def main(scope: MinioScope | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--check-relaunch", action="store_true")
    arguments = parser.parse_args()
    if arguments.check_relaunch:
        check_relaunch(require_activation())
        return
    if not arguments.start:
        raise ValueError("explicit root start required")
    activation = require_activation()
    nonce = str(activation["nonce"])
    from configuration import unique_json_object, validate_launch_state
    launch_state = validate_launch_state(json.loads((OPS / "launch_state.json").read_bytes(), object_pairs_hook=unique_json_object))
    prior_log_bytes = launch_state["component_log_bytes"].get("minio", 0)
    if launch_state["runtime_binding_sha256"] != activation["runtime_binding_sha256"]:
        raise ValueError("MinIO launch configuration differs")
    group = group_for_nonce(nonce)
    lifecycle = json.loads(
        Path("/tmp/dianzi-docker-static-r01-20261014/runtime/lifecycle.json").read_bytes()
    )
    boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    if boot != lifecycle["boot_id"] or lifecycle["ended_at"] is not None:
        raise ValueError("owned daemon boot differs")
    started = datetime.now(ZONE)
    deadline = min(
        started + timedelta(seconds=TOTAL_SECONDS),
        datetime.fromisoformat(lifecycle["deadline"]),
    )
    stop_begin_by = deadline - timedelta(seconds=15)
    if (deadline - started).total_seconds() < TOTAL_SECONDS:
        raise ValueError("full source and shutdown window does not fit daemon deadline")
    if hashlib.sha256((RESOURCE / "bin/minio").read_bytes()).hexdigest() != HASH:
        raise ValueError("owned MinIO binary changed")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 29400))
    if scope is None:
        raise ValueError("owned MinIO outside controller required before Popen")
    scope.require_helper()
    if scope.target != group:
        raise ValueError("owned MinIO target binding differs")
    private = RESOURCE / "private"
    connection = json.loads(private.joinpath("connection.json").read_bytes())
    secrets = (connection["access_key"], connection["secret_key"])
    environment = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(RESOURCE),
        "MINIO_ROOT_USER_FILE": str(private / "access-key"),
        "MINIO_ROOT_PASSWORD_FILE": str(private / "secret-key"),
        "MINIO_BROWSER": "off",
        "MINIO_UPDATE": "off",
        "MINIO_PROMETHEUS_AUTH_TYPE": "jwt",
        "GOMAXPROCS": "2",
        "GOMEMLIMIT": "384MiB",
    }
    selector: selectors.BaseSelector | None = None
    process: subprocess.Popen[bytes] | None = None
    pidfd: int | None = None
    child_identity: dict[str, object] | None = None
    monotonic_deadline = time.monotonic() + TOTAL_SECONDS
    monotonic_deadline = min(monotonic_deadline, scope.monotonic_deadline)
    deadline = min(deadline, scope.deadline)
    stop_begin_by = deadline - timedelta(seconds=15)
    reason = "startup_failed"
    log_bytes = 0
    acknowledged = False
    waitpid_acknowledged = False
    cleanup_error: str | None = None
    prepare_cleanup_capacity()
    reserve_count_before_popen = (
        len(_cleanup_reserve.handles) if _cleanup_reserve is not None else 0
    )
    try:
        process = subprocess.Popen(
            [
                str(RESOURCE / "bin/minio"),
                "server",
                "--quiet",
                "--address",
                "127.0.0.1:29400",
                str(RESOURCE / "objects"),
            ],
            env=environment,
            cwd=RESOURCE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        child_identity = identity(process.pid)
        scope.register_child(process.pid)
        pidfd = pin_owned_process(process.pid)
        selector = selectors.DefaultSelector()
        write(
            "minio_start.json",
            {
                "started_at": started.isoformat(),
                "hard_deadline": deadline.isoformat(),
                "stop_begin_by": stop_begin_by.isoformat(),
                "boot_id": boot,
                "nonce": nonce,
                "run_id": activation["run_id"],
                "supervisor": identity(os.getpid()),
                "child": child_identity,
                "cgroup": str(group),
                "cgroup_limits": LIMITS,
                "cleanup_reserve_fd_count_before_popen": reserve_count_before_popen,
                "held_scope_fd_count": scope.held_fd_count(),
                "binary_sha256": HASH,
                "objects_inode": (RESOURCE / "objects").stat().st_ino,
                "retained_existing_objects": True,
                "product_sha": activation["product_sha"],
                "runtime_binding_sha256": activation["runtime_binding_sha256"],
                "observation_id": launch_state["observation_id"],
            },
        )
        if process.stdout is None:
            raise RuntimeError("owned MinIO output pipe required")
        selector.register(process.stdout, selectors.EVENT_READ)
        reason = "deadline"
        with (OPS / "minio.log").open("xb") as log:
            while (
                process.poll() is None
                and datetime.now(ZONE) < stop_begin_by
                and time.monotonic() < monotonic_deadline - 15
            ):
                if scope.parent_exited():
                    reason = "owned_controller_exit"
                    break
                message = scope.receive()
                if message is not None and message.get("event") == "stop":
                    reason = "owned_controller_deadline"
                    break
                if (
                    shutil.disk_usage(RESOURCE / "objects").free < 16 * 1024**3
                    and not (CORE / "stop.request").exists()
                ):
                    with (CORE / "stop.request").open("x", encoding="utf-8") as output:
                        output.write("owned store disk guard below16GiB\n")
                if (
                    (OPS / "minio_stop.request").exists()
                    or (CORE / "runtime_end.json").exists()
                    or (CORE / "owned_stop_failure.json").exists()
                    or (OPS / "guardian_end.json").exists()
                ):
                    reason = "owned_stop_or_collector_end"
                    break
                remaining = min(
                    (stop_begin_by - datetime.now(ZONE)).total_seconds(),
                    monotonic_deadline - 15 - time.monotonic(),
                )
                for key, _ in selector.select(timeout=max(0, min(1, remaining))):
                    chunk = os.read(key.fd, 65536)
                    for secret in secrets:
                        chunk = chunk.replace(secret.encode(), b"[REDACTED]")
                    if prior_log_bytes + log_bytes + len(chunk) > 8 * 1024**2:
                        reason = "log_budget"
                        break
                    log.write(chunk)
                    log.flush()
                    log_bytes += len(chunk)
                if reason == "log_budget":
                    break
            if process.poll() is not None:
                reason = "child_exit"
    finally:
        original_error = sys.exc_info()[1]
        release_cleanup_io()
        descriptor_error: BaseException | None = None
        try:
            if selector is not None:
                selector.close()
                selector = None
        except BaseException as error:
            descriptor_error = error
        try:
            if process is not None and process.stdout is not None:
                process.stdout.close()
        except BaseException as error:
            if descriptor_error is None:
                descriptor_error = error
        try:
            if process is not None:
                stop_deadline = min(
                    monotonic_deadline,
                    time.monotonic() + max(0, (deadline - datetime.now(ZONE)).total_seconds()),
                    time.monotonic() + 15,
                )
                scope.begin_stop(stop_deadline)
                if pidfd is None:
                    try:
                        pidfd = pin_owned_process(process.pid)
                    except OSError:
                        waitpid_acknowledged = stop_direct_without_pidfd(
                            process, child_identity, group, stop_deadline
                        )
                        raise
                if child_identity is None:
                    child_identity = identity(process.pid)
                acknowledged = stop_child(process, pidfd, child_identity, group, stop_deadline)
        except BaseException as error:
            cleanup_error = type(error).__name__
            if scope.parent_exited():
                try:
                    scope.parent_death_cleanup(stop_deadline)
                except BaseException as emergency_error:
                    scope.error_types.append(type(emergency_error).__name__)
            if original_error is None:
                original_error = error
        finally:
            release_cleanup_capacity()
            if pidfd is not None:
                os.close(pidfd)
            if process is not None:
                try:
                    write(
                        "minio_end.json",
                        {
                            "started_at": started.isoformat(),
                            "ended_at": datetime.now(ZONE).isoformat(),
                            "nonce": nonce,
                            "reason": reason,
                            "exit_code": process.returncode,
                            "cleanup_error_type": cleanup_error,
                            "descriptor_error_type": type(descriptor_error).__name__
                            if descriptor_error is not None
                            else None,
                            "log_bytes": log_bytes,
                            "pidfd_kernel_exit_ack": acknowledged,
                            "waitpid_kernel_exit_ack": waitpid_acknowledged,
                            "emergency_kernel_empty_ack": scope.closed_by_emergency,
                            "control_error_types": scope.error_types[-16:],
                            "final_group_contains_only_supervisor": True
                            if acknowledged or waitpid_acknowledged
                            else "unknown",
                            "objects_deleted": False,
                            "product_sha": activation["product_sha"],
                            "runtime_binding_sha256": activation["runtime_binding_sha256"],
                            "observation_id": launch_state["observation_id"],
                            "formal_six_hour_pass": False,
                        },
                    )
                except BaseException:
                    if original_error is None:
                        raise
        if original_error is not None:
            raise original_error
        if descriptor_error is not None:
            raise descriptor_error


if __name__ == "__main__":
    try:
        if "--start" not in sys.argv:
            main()
        else:
            activation = require_activation()
            sys.modules.setdefault("minio_segment", sys.modules[__name__])
            from minio_controller import run_owned_minio

            run_owned_minio(activation, main)
    except Exception as error:
        print(json.dumps({"error_type": type(error).__name__, "details": "withheld"}))
        raise SystemExit(1) from None
