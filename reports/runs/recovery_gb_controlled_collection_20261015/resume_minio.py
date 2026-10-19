"""原段4正常收尾后，同对象身份的六个半小时有界依赖段。"""

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
RUN = Path("/mnt/d/dianzi/reports/runs/recovery_gb_controlled_collection_20261015/minio")
OLD_RUN = Path("/mnt/d/dianzi/reports/runs/recovery_r04_minio_segment4_20261015")
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
    for name, expected in {"cpu.max": "50000 100000", "memory.max": "805306368", "memory.swap.max": "0", "pids.max": "256"}.items():
        assert (GROUP / name).read_text().strip() == expected, "existing cgroup resource limits changed"
    initial_cpu = int(dict(line.split() for line in (GROUP / "cpu.stat").read_text().splitlines())["usage_usec"])
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
    deadline = time.monotonic() + 23400
    command = [str(binary), "server", "--quiet", "--address", "127.0.0.1:29400",
               str(RESOURCE / "objects")]
    process = subprocess.Popen(command, env=environment, cwd=RESOURCE,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, bufsize=1, start_new_session=True, preexec_fn=owned_group)
    receipt = {"started_at": started_at, "supervisor_pid": os.getpid(), "child_pid": process.pid,
               "previous_segment_end": previous["ended_at"], "maximum_seconds": 23400,
               "binary_sha256": EXPECTED_HASH, "cgroup": str(GROUP),
               "hard_deadline": datetime.fromtimestamp(time.time() + 23400, ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
               "aggregate_cpu_budget_seconds": 1800, "maximum_log_bytes": 16 * 1024**2,
               "binary_release_status": "local development build; not an official released artifact",
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
                current_cpu = int(dict(line.split() for line in (GROUP / "cpu.stat").read_text().splitlines())["usage_usec"])
                if current_cpu - initial_cpu >= 1800 * 1_000_000:
                    reason = "aggregate CPU budget"
                    break
                if log.tell() > 16 * 1024**2:
                    reason = "log limit"
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
