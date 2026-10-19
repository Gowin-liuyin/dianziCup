"""Verify and archive the stopped project runtime, then restore its existing limits."""

import argparse
import errno
import hashlib
import json
import os
import shutil
import socket
import stat
from datetime import datetime
from pathlib import Path

CACHE = Path("/tmp/dianzi-docker-static-r01-20261014")
RUNTIME = CACHE / "runtime"
CGROUP_ROOT = Path("/sys/fs/cgroup")
CGROUP = CGROUP_ROOT / "dianzi-r01-20261014"
OUTPUT = Path(__file__).resolve().parent
DEADLINE = "2026-10-17T21:49:15+08:00"
LIMITS = {
    "memory.max": "8589934592",
    "memory.swap.max": "2147483648",
    "cpu.max": "200000 100000",
    "pids.max": "2048",
}


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def metadata(path):
    details = path.lstat()
    return {
        "path": str(path),
        "uid": details.st_uid,
        "gid": details.st_gid,
        "mode": oct(stat.S_IMODE(details.st_mode)),
        "size": details.st_size,
        "mtime_ns": details.st_mtime_ns,
        "inode": details.st_ino,
        "is_socket": stat.S_ISSOCK(details.st_mode),
        "is_symlink": path.is_symlink(),
    }


def owned_processes():
    matches = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) == os.getpid():
            continue
        try:
            words = (proc / "cmdline").read_bytes().split(b"\x00")
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        if any(str(CACHE).encode() in word for word in words):
            matches.append(
                {"pid": int(proc.name), "executable": os.readlink(proc / "exe")}
            )
        if any(
            b"supervise_isolated_daemon.py" in word
            or b"supervise_recovered_daemon.py" in word
            for word in words
        ):
            matches.append(
                {"pid": int(proc.name), "executable": os.readlink(proc / "exe")}
            )
    return matches


def limits_snapshot():
    return {
        str(path): {
            name: (path / name).read_text().strip() if (path / name).exists() else None
            for name in LIMITS
        }
        for path in [
            CGROUP_ROOT,
            *[
                child
                for child in CGROUP_ROOT.iterdir()
                if child.is_dir() and child != CGROUP
            ],
        ]
    }


def preflight():
    assert os.getuid() == 0
    assert CACHE.resolve() == CACHE and RUNTIME.resolve() == RUNTIME
    assert OUTPUT == Path(
        "/mnt/d/dianzi/reports/runs/recovery_r01_runtime_recovery_20261016"
    )
    lifecycle = json.loads((RUNTIME / "lifecycle.json").read_text())
    assert lifecycle["deadline"] == DEADLINE
    assert datetime.fromisoformat(DEADLINE) > datetime.now().astimezone()
    assert lifecycle["socket"] == str(RUNTIME / "docker.sock")
    assert lifecycle["command"][0] == str(CACHE / "portable/docker/dockerd")
    assert lifecycle["command"][lifecycle["command"].index("--data-root") + 1] == str(
        RUNTIME / "data"
    )
    assert lifecycle["ended_at"] is None
    old_pid_presence = {
        str(lifecycle[key]): Path("/proc/" + str(lifecycle[key])).exists()
        for key in ("supervisor_pid", "daemon_pid")
    }
    assert not any(old_pid_presence.values()), "Old process identities still exist."
    processes = owned_processes()
    assert not processes, "Owned runtime process is still present."
    socket_path = RUNTIME / "docker.sock"
    assert socket_path.resolve() == socket_path and not socket_path.is_symlink()
    assert stat.S_ISSOCK(socket_path.lstat().st_mode)
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(2)
        result = connection.connect_ex(str(socket_path))
    assert result == errno.ECONNREFUSED, "Socket is not proven stale."
    socket_listeners = [
        line.split()[-1]
        for line in Path("/proc/net/unix").read_text().splitlines()
        if str(RUNTIME) in line
    ]
    assert not socket_listeners
    assert not CGROUP.exists(), "Refuse an existing project cgroup."
    assert any(
        line.split()[1:3] == [str(CGROUP_ROOT), "cgroup2"]
        and "rw" in line.split()[3].split(",")
        for line in Path("/proc/mounts").read_text().splitlines()
    )
    assert {"memory", "cpu", "pids"} <= set(
        (CGROUP_ROOT / "cgroup.controllers").read_text().split()
    )
    containers = []
    for directory in sorted((RUNTIME / "data/containers").iterdir()):
        config = json.loads((directory / "config.v2.json").read_text())
        host = json.loads((directory / "hostconfig.json").read_text())
        containers.append(
            {
                "id": config["ID"],
                "name": config["Name"],
                "state": {
                    key: config["State"].get(key)
                    for key in (
                        "Running",
                        "Paused",
                        "Pid",
                        "ExitCode",
                        "StartedAt",
                        "FinishedAt",
                    )
                },
                "image_id": config["Image"],
                "labels": config["Config"].get("Labels"),
                "network_mode": host.get("NetworkMode"),
                "restart_policy": host.get("RestartPolicy"),
                "mounts": [
                    {
                        "type": mount.get("Type"),
                        "name": mount.get("Name"),
                        "source": mount.get("Source"),
                        "destination": mount.get("Destination"),
                    }
                    for mount in config.get("MountPoints", {}).values()
                ],
            }
        )
    record = {
        "observed_at": now(),
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "uptime": Path("/proc/uptime").read_text().strip(),
        "old_lifecycle": lifecycle,
        "old_stop_time": "unknown",
        "old_pid_presence": old_pid_presence,
        "owned_processes": processes,
        "socket_connect_errno": result,
        "socket_listeners": socket_listeners,
        "root_subtree_control": (CGROUP_ROOT / "cgroup.subtree_control")
        .read_text()
        .strip(),
        "existing_parent_and_sibling_limits": limits_snapshot(),
        "metadata": [
            metadata(path)
            for path in (
                CACHE,
                RUNTIME,
                RUNTIME / "data",
                RUNTIME / "exec",
                socket_path,
            )
        ],
        "persisted_containers": containers,
        "volume_names": sorted(
            path.name for path in (RUNTIME / "data/volumes").iterdir() if path.is_dir()
        ),
    }
    (OUTPUT / "preflight_evidence.json").write_text(json.dumps(record, indent=2))
    print(
        json.dumps(
            {
                "observed_at": record["observed_at"],
                "boot_id": record["boot_id"],
                "old_stop_time": "unknown",
                "socket_connect_errno": result,
                "persisted_containers": len(containers),
                "deadline": DEADLINE,
            }
        )
    )
    return record


def prepare():
    record = preflight()
    archive = CACHE / (
        "recovery-archive-" + datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")
    )
    assert (
        archive.parent == CACHE
        and archive.resolve() == archive
        and not archive.exists()
    )
    archive.mkdir(mode=0o700)
    archive_metadata = []
    for path in (
        RUNTIME / "lifecycle.json",
        RUNTIME / "dockerd.log",
        CACHE / "supervisor.log",
    ):
        if path.exists():
            assert path.resolve() == path and path.parent in (RUNTIME, CACHE)
            destination = archive / path.name
            shutil.copy2(path, destination)
            os.chmod(destination, 0o600)
            archive_metadata.append(
                {
                    "source": metadata(path),
                    "archive": metadata(destination),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
            if path.name == "lifecycle.json":
                shutil.copy2(path, OUTPUT / "previous_lifecycle.json")
    for path in (
        RUNTIME / "supervisor.pid",
        RUNTIME / "dockerd.pid",
        RUNTIME / "docker.sock",
        RUNTIME / "exec",
    ):
        if path.exists():
            assert (
                path.resolve() == path
                and path.parent == RUNTIME
                and not path.is_symlink()
            )
            before = metadata(path)
            destination = archive / path.name
            path.rename(destination)
            archive_metadata.append(
                {"source": before, "archive": metadata(destination), "moved": True}
            )
    (RUNTIME / "exec").mkdir(mode=0o700)
    redactions = 0
    original = (CGROUP_ROOT / "cgroup.subtree_control").read_text().strip()
    needed = {"memory", "cpu", "pids"} - set(original.split())
    if needed:
        (CGROUP_ROOT / "cgroup.subtree_control").write_text(
            " ".join("+" + name for name in sorted(needed))
        )
    CGROUP.mkdir()
    for name, value in LIMITS.items():
        (CGROUP / name).write_text(value)
    after = limits_snapshot()
    for directory, fields in record["existing_parent_and_sibling_limits"].items():
        for name, previous in fields.items():
            assert previous == after[directory][name] or (
                previous is None
                and after[directory][name] in (None, "max", "max 100000")
            )
    archive_record = {
        "prepared_at": now(),
        "private_archive": str(archive),
        "archive_metadata": archive_metadata,
        "proxy_redactions": redactions,
        "deadline": DEADLINE,
        "previous_stop_time": "unknown",
        "data_root": str(RUNTIME / "data"),
        "data_root_unchanged": True,
        "root_subtree_before": original,
        "root_subtree_after": (CGROUP_ROOT / "cgroup.subtree_control")
        .read_text()
        .strip(),
        "existing_parent_and_sibling_limits_after": after,
        "project_limits": {
            name: (CGROUP / name).read_text().strip() for name in LIMITS
        },
    }
    (OUTPUT / "preparation_evidence.json").write_text(
        json.dumps(archive_record, indent=2)
    )
    (RUNTIME / "recovery-prepared.json").write_text(
        json.dumps(archive_record, indent=2)
    )
    print(
        json.dumps(
            {
                "prepared_at": archive_record["prepared_at"],
                "archive": str(archive),
                "data_root_unchanged": True,
                "deadline": DEADLINE,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("preflight", "prepare"))
    operation = parser.parse_args().operation
    if operation == "prepare":
        prepare()
    else:
        preflight()
