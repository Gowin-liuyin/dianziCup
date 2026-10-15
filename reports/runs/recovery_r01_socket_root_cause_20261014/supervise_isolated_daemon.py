"""Run only this project daemon with a 72-hour deadline and bounded native resources."""

import json
import os
import selectors
import signal
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path


CACHE = Path("/tmp/dianzi-docker-static-r01-20261014")
RUNTIME = CACHE / "runtime"
CGROUP = Path("/sys/fs/cgroup/dianzi-r01-20261014")
MAXIMUM_SECONDS = 72 * 60 * 60
MAXIMUM_LOG_BYTES = 10 * 1024 * 1024
assert os.getuid() == 0 and CACHE.resolve() == CACHE
previous_lifecycle = None
if RUNTIME.exists():
    previous_lifecycle = json.loads((RUNTIME / "lifecycle.json").read_text())
    assert previous_lifecycle["ended_at"] is not None, "Never replace a running instance."
    assert previous_lifecycle["stop_reason"] == "supervisor_signal_15"
    assert not Path("/proc/" + str(previous_lifecycle["supervisor_pid"])).exists()
assert CGROUP.is_dir() and not (CGROUP / "cgroup.procs").read_text().strip()
assert all(child.name == "supervisor" and not (child / "cgroup.procs").read_text().strip()
           for child in CGROUP.iterdir() if child.is_dir())
RUNTIME.mkdir(mode=0o700, exist_ok=True)
(RUNTIME / "data").mkdir(mode=0o700, exist_ok=True)
(RUNTIME / "exec").mkdir(mode=0o700, exist_ok=True)
(RUNTIME / "client-config").mkdir(mode=0o700, exist_ok=True)
(RUNTIME / "client-config/config.json").write_text("{}\n")
(RUNTIME / "daemon.json").write_text("{}\n")
for name, value in {"memory.max": "8589934592", "memory.swap.max": "2147483648",
                    "cpu.max": "200000 100000", "pids.max": "2048"}.items():
    (CGROUP / name).write_text(value)
(CGROUP / "cgroup.subtree_control").write_text("+memory +cpu +pids")
supervisor_group = CGROUP / "supervisor"
supervisor_group.mkdir(exist_ok=True)
(supervisor_group / "cgroup.procs").write_text(str(os.getpid()))
started = datetime.now().astimezone()
deadline_at = (datetime.fromisoformat(previous_lifecycle["deadline"]) if previous_lifecycle
               else started + timedelta(seconds=MAXIMUM_SECONDS))
assert deadline_at > started
command = [str(CACHE / "portable/docker/dockerd"),
           "--host", "unix://" + str(RUNTIME / "docker.sock"),
           "--data-root", str(RUNTIME / "data"), "--exec-root", str(RUNTIME / "exec"),
           "--pidfile", str(RUNTIME / "dockerd.pid"),
           "--config-file", str(RUNTIME / "daemon.json"),
           "--bridge=none", "--iptables=false", "--ip6tables=false", "--ip-forward=false",
           "--ip-masq=false", "--group=root", "--cgroup-parent=/dianzi-r01-20261014",
           "--exec-opt", "native.cgroupdriver=cgroupfs", "--log-driver=local",
           "--log-opt", "max-size=10m", "--log-opt", "max-file=3"]
environment = {"PATH": str(CACHE / "portable/docker") + ":/usr/sbin:/usr/bin:/sbin:/bin",
               "LANG": "C.UTF-8"}
proxy_keys = ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy")
environment.update({key: os.environ[key] for key in proxy_keys if os.environ.get(key)})
daemon = subprocess.Popen(command, cwd=RUNTIME, env=environment, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
(RUNTIME / "supervisor.pid").write_text(str(os.getpid()))
lifecycle = {"started_at": started.isoformat(timespec="seconds"),
             "deadline": deadline_at.isoformat(timespec="seconds"),
             "supervisor_pid": os.getpid(), "daemon_pid": daemon.pid, "command": command,
             "limits": {"memory_bytes": 8589934592, "swap_bytes": 2147483648,
                        "cpu_count": 2, "pids": 2048, "daemon_log_bytes": MAXIMUM_LOG_BYTES},
             "socket": str(RUNTIME / "docker.sock"), "cgroup": str(CGROUP), "ended_at": None,
             "proxy_keys_forwarded": [key for key in proxy_keys if key in environment]}
(RUNTIME / "lifecycle.json").write_text(json.dumps(lifecycle, indent=2))
stop_reason = None


def request_stop(signum: int, frame: object) -> None:
    """Convert explicit signals into orderly shutdown of this daemon group only."""
    global stop_reason
    stop_reason = "supervisor_signal_" + str(signum)


signal.signal(signal.SIGTERM, request_stop)
signal.signal(signal.SIGINT, request_stop)
selector = selectors.DefaultSelector()
assert daemon.stdout is not None
selector.register(daemon.stdout, selectors.EVENT_READ)
deadline = time.monotonic() + (deadline_at - started).total_seconds()
written = 0
with (RUNTIME / "dockerd.log").open("wb") as log:
    while daemon.poll() is None and stop_reason is None:
        if time.monotonic() >= deadline:
            stop_reason = "72_hour_deadline"
            break
        for key, events in selector.select(timeout=1):
            chunk = os.read(key.fileobj.fileno(), 8192)
            remaining = MAXIMUM_LOG_BYTES - written
            log.write(chunk[:remaining])
            log.flush()
            written += min(len(chunk), remaining)
            if len(chunk) > remaining:
                stop_reason = "daemon_log_budget_reached"
                break
if daemon.poll() is None:
    os.killpg(daemon.pid, signal.SIGTERM)
    try:
        daemon.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(daemon.pid, signal.SIGKILL)
        daemon.wait(timeout=5)
lifecycle.update(ended_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                 stop_reason=stop_reason or "daemon_exited", exit_code=daemon.returncode,
                 daemon_log_bytes=written)
(RUNTIME / "lifecycle.json").write_text(json.dumps(lifecycle, indent=2))
