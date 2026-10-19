"""Bound a fresh MinIO process group while retaining the existing authorized objects."""

import hashlib
import json
import os
import selectors
import signal
import socket
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path("/mnt/d/dianzi/reports/runs/recovery_r06_live_segment_8a_20261016/minio_diagnostic_segment_2")
RESOURCE = Path("/tmp/dianzi-minio-r02-20261015")
GROUP = Path("/sys/fs/cgroup/dianzi-r01-20261014/minio-r06-live-8a-diag2-20261016")
HASH = "10ec54df2dc51dfa1399b7187d9377a20bd1b50f22d123a756175173b0cfff75"
CLOCK = ZoneInfo("Asia/Shanghai")


def now():
    return datetime.now(CLOCK).isoformat(timespec="seconds")


def write(name, value):
    (RUN / name).write_text(json.dumps(value, indent=2) + "\n")


def identity(pid):
    path = Path("/proc") / str(pid)
    return {"pid": pid, "start_ticks": path.joinpath("stat").read_text().split()[21], "executable": str(path.joinpath("exe").resolve()), "cgroup": path.joinpath("cgroup").read_text().strip()}


def main():
    gate = json.loads((RUN / "root_authorization.json").read_text(encoding="utf-8-sig"))
    assert gate["root_live_authorized"] and gate["maximum_seconds"] == 21600
    lifecycle = json.loads(Path("/tmp/dianzi-docker-static-r01-20261014/runtime/lifecycle.json").read_text())
    boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    assert boot == lifecycle["boot_id"] and lifecycle["ended_at"] is None
    assert Path("/proc").joinpath(str(lifecycle["daemon_pid"]), "stat").exists()
    assert hashlib.sha256((RESOURCE / "bin/minio").read_bytes()).hexdigest() == HASH
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 29400))
    assert not GROUP.exists()
    GROUP.mkdir()
    for name, value in {"memory.max": str(512 * 1024**2), "memory.swap.max": "0", "pids.max": "128", "cpu.max": "100000 100000"}.items():
        GROUP.joinpath(name).write_text(value)
    GROUP.joinpath("cgroup.procs").write_text(str(os.getpid()))
    private = RESOURCE / "private"
    connection = json.loads(private.joinpath("connection.json").read_text())
    secrets = (connection["access_key"], connection["secret_key"])
    environment = {**os.environ, "MINIO_ROOT_USER_FILE": str(private / "access-key"), "MINIO_ROOT_PASSWORD_FILE": str(private / "secret-key"), "MINIO_BROWSER": "off", "MINIO_UPDATE": "off", "MINIO_PROMETHEUS_AUTH_TYPE": "jwt", "GOMAXPROCS": "2", "GOMEMLIMIT": "384MiB"}
    process = subprocess.Popen([str(RESOURCE / "bin/minio"), "server", "--quiet", "--address", "127.0.0.1:29400", str(RESOURCE / "objects")], env=environment, cwd=RESOURCE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    started = datetime.now(CLOCK)
    deadline = min(started + timedelta(seconds=1800), datetime.fromisoformat("2026-10-17T21:49:15+08:00"))
    write("minio_start.json", {"started_at": started.isoformat(timespec="seconds"), "hard_deadline": deadline.isoformat(timespec="seconds"), "boot_id": boot, "supervisor": identity(os.getpid()), "child": identity(process.pid), "cgroup": str(GROUP), "cgroup_limits": {name: GROUP.joinpath(name).read_text().strip() for name in ("memory.max", "memory.swap.max", "cpu.max", "pids.max")}, "binary_sha256": HASH, "endpoint": "127.0.0.1:29400", "objects_directory": str(RESOURCE / "objects"), "retained_existing_objects": True, "log_limit_bytes": 8 * 1024**2})
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    reason = "deadline"
    log_bytes = 0
    try:
        with (RUN / "minio.log").open("xb") as log:
            while process.poll() is None and datetime.now(CLOCK) < deadline:
                if (RUN / "minio_stop.request").exists():
                    reason = "owned_stop_request"
                    break
                for key, _ in selector.select(timeout=1):
                    chunk = os.read(key.fd, 65536)
                    for secret in secrets:
                        chunk = chunk.replace(secret.encode(), b"[REDACTED]")
                    if log_bytes + len(chunk) > 8 * 1024**2:
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
        selector.close()
        if process.poll() is None:
            assert identity(process.pid)["cgroup"] == "0::/dianzi-r01-20261014/minio-r06-live-8a-diag2-20261016"
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        write("minio_end.json", {"started_at": started.isoformat(timespec="seconds"), "ended_at": now(), "reason": reason, "exit_code": process.returncode, "log_bytes": log_bytes, "cgroup_events": GROUP.joinpath("memory.events").read_text()})


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        write("minio_failure.json", {"observed_at": now(), "error_type": type(error).__name__, "details": "withheld"})
        raise SystemExit(1) from None
