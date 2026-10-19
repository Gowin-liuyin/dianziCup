"""前一受控段结束后，用原对象和私密身份启动新的两小时隔离验证段。"""

import hashlib
import json
import os
import selectors
import signal
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RESOURCE = Path("/tmp/dianzi-minio-r02-20261015")
RUN = Path("/mnt/d/dianzi/reports/runs/recovery_r04_minio_segment4_20261015")
OLD_RUN = Path("/mnt/d/dianzi/reports/runs/recovery_r04_minio_segment3_20261015")
GROUP = Path("/sys/fs/cgroup/dianzi-r01-20261014/minio-server-20261015")
EXPECTED_HASH = "10ec54df2dc51dfa1399b7187d9377a20bd1b50f22d123a756175173b0cfff75"


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def main():
    binary = RESOURCE / "bin/minio"
    if hashlib.sha256(binary.read_bytes()).hexdigest() != EXPECTED_HASH:
        raise RuntimeError("object server binary checksum mismatch")
    startup_deadline = time.monotonic() + 90
    while not (OLD_RUN / "service_end.json").exists() and time.monotonic() < startup_deadline:
        time.sleep(1)
    previous = json.loads((OLD_RUN / "service_end.json").read_text())
    if not previous.get("ended_at") or (GROUP / "cgroup.procs").read_text().strip():
        raise RuntimeError("previous owned resource segment is not closed")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 29400))
    private = RESOURCE / "private"
    identity = json.loads((private / "connection.json").read_text())
    sensitive = {identity["access_key"], identity["secret_key"]}
    sensitive.update(value[index:index + 8] for value in tuple(sensitive)
                     for index in range(len(value) - 7))

    def redact(value):
        for secret in sorted(sensitive, key=len, reverse=True):
            value = value.replace(secret, "[REDACTED]")
        return value

    def owned_group():
        (GROUP / "cgroup.procs").write_text(str(os.getpid()))

    environment = dict(os.environ)
    environment.update(MINIO_ROOT_USER_FILE=str(private / "access-key"),
                       MINIO_ROOT_PASSWORD_FILE=str(private / "secret-key"),
                       MINIO_BROWSER="off", MINIO_UPDATE="off",
                       MINIO_PROMETHEUS_AUTH_TYPE="jwt", GOMAXPROCS="2", GOMEMLIMIT="384MiB")
    started_at = now()
    deadline = time.monotonic() + 7200
    command = [str(binary), "server", "--quiet", "--address", "127.0.0.1:29400",
               str(RESOURCE / "objects")]
    process = subprocess.Popen(command, env=environment, cwd=RESOURCE,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, bufsize=1, start_new_session=True, preexec_fn=owned_group)
    receipt = {"started_at": started_at, "supervisor_pid": os.getpid(), "child_pid": process.pid,
               "previous_segment_end": previous["ended_at"], "maximum_seconds": 7200,
               "binary_sha256": EXPECTED_HASH, "cgroup": str(GROUP),
               "scope": "isolated loopback integration only, existing objects/identity retained",
               "cgroup_events_at_start": (GROUP / "memory.events").read_text()}
    (RUN / "service_start.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt), flush=True)
    reason = "deadline"
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        with (RUN / "service.log").open("x", encoding="utf-8") as log:
            while process.poll() is None and time.monotonic() < deadline:
                if (RUN / "service_stop.request").exists():
                    reason = "owned stop request"
                    break
                for key, _mask in selector.select(timeout=1):
                    line = key.fileobj.readline()
                    if line:
                        log.write(redact(line))
                        log.flush()
            if process.poll() is not None:
                reason = "child exited"
    finally:
        selector.close()
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        (RUN / "service_end.json").write_text(json.dumps({
            "started_at": started_at, "ended_at": now(), "reason": reason,
            "exit_code": process.returncode,
            "cgroup_events_at_end": (GROUP / "memory.events").read_text(),
        }, indent=2) + "\n")


if __name__ == "__main__":
    main()
