"""隔离测试对象服务的有界启动、重启与秘密脱敏，不改现有服务。"""

import hashlib
import json
import os
import secrets
import selectors
import signal
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path("/tmp/dianzi-minio-r02-20261015")
RUN = Path("/mnt/d/dianzi/reports/runs/recovery_r02_minio_20261015")
GROUP = Path("/sys/fs/cgroup/dianzi-r01-20261014/minio-server-20261015")
EXPECTED = "10ec54df2dc51dfa1399b7187d9377a20bd1b50f22d123a756175173b0cfff75"
MAX_SECONDS = 7200


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def main() -> int:
    binary = ROOT / "bin/minio"
    if hashlib.sha256(binary.read_bytes()).hexdigest() != EXPECTED:
        raise ValueError("binary checksum mismatch")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 29400))
    private = ROOT / "private"
    private.mkdir(mode=0o700)
    access_key = "dianzi-r02-" + secrets.token_hex(8)
    secret_key = secrets.token_urlsafe(36)
    connection = {"endpoint": "127.0.0.1:29400", "access_key": access_key,
                  "secret_key": secret_key, "bucket": "test-dianzi-r02-20261015"}
    for filename, value in {"access-key": access_key, "secret-key": secret_key,
                            "connection.json": json.dumps(connection)}.items():
        path = private / filename
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            handle.write(value)
    GROUP.mkdir()
    for name, value in {"memory.max": "805306368", "memory.swap.max": "0",
                        "pids.max": "256", "cpu.max": "50000 100000"}.items():
        (GROUP / name).write_text(value)
    environment = dict(os.environ)
    environment.update(MINIO_ROOT_USER_FILE=str(private / "access-key"),
                       MINIO_ROOT_PASSWORD_FILE=str(private / "secret-key"),
                       MINIO_BROWSER="off", MINIO_UPDATE="off", MINIO_PROMETHEUS_AUTH_TYPE="jwt",
                       GOMAXPROCS="2", GOMEMLIMIT="384MiB")
    sensitive = {access_key, secret_key}
    sensitive.update(value[index:index + 8] for value in (access_key, secret_key)
                     for index in range(len(value) - 7))

    def redact(value: str) -> str:
        for item in sorted(sensitive, key=len, reverse=True):
            value = value.replace(item, "[REDACTED]")
        return value

    def child_group() -> None:
        (GROUP / "cgroup.procs").write_text(str(os.getpid()))

    started = now()
    deadline = time.monotonic() + MAX_SECONDS
    segment = 0
    stop_reason = "deadline"
    with (RUN / "service.log").open("x", encoding="utf-8") as output:
        while time.monotonic() < deadline:
            segment += 1
            command = [str(binary), "server", "--quiet", "--address", "127.0.0.1:29400",
                       str(ROOT / "objects")]
            child = subprocess.Popen(command, env=environment, cwd=ROOT, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, bufsize=1,
                                     start_new_session=True, preexec_fn=child_group)
            receipt = {"started_at": now(), "supervisor_pid": os.getpid(), "child_pid": child.pid,
                       "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                       "segment": segment, "binary_sha256": EXPECTED, "endpoint": "127.0.0.1:29400",
                       "mode": "explicit isolated integration test, plaintext loopback, root identity",
                       "max_total_seconds": MAX_SECONDS, "cgroup": str(GROUP)}
            (RUN / f"service_segment_{segment}_start.json").write_text(json.dumps(receipt, indent=2))
            print(json.dumps(receipt), flush=True)
            selector = selectors.DefaultSelector()
            selector.register(child.stdout, selectors.EVENT_READ)
            restart = False
            while child.poll() is None and time.monotonic() < deadline:
                for key, _ in selector.select(timeout=0.25):
                    line = key.fileobj.readline()
                    if line:
                        output.write(redact(line))
                        output.flush()
                if (RUN / "service_stop.request").exists():
                    stop_reason = "owned stop request"
                    break
                request = RUN / f"service_restart_{segment}.request"
                if request.exists():
                    restart = True
                    break
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=10)
            if child.stdout is not None:
                output.write(redact(child.stdout.read()))
                child.stdout.close()
            selector.close()
            (RUN / f"service_segment_{segment}_end.json").write_text(json.dumps({
                **receipt, "ended_at": now(), "exit_code": child.returncode,
                "restart_requested": restart,
            }, indent=2))
            if not restart:
                if child.returncode != 0 and stop_reason == "deadline":
                    stop_reason = "child exited"
                break
    (RUN / "service_end.json").write_text(json.dumps({
        "started_at": started, "ended_at": now(), "reason": stop_reason,
        "segments": segment, "cgroup_events": (GROUP / "memory.events").read_text(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
