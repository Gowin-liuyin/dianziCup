"""Signal only this segment's supervisor after matching boot, start time and command."""

import argparse
import json
import os
import signal
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--check", action="store_true")
check_only = parser.parse_args().check
runtime = Path("/tmp/dianzi-docker-static-r01-20261014/runtime")
lifecycle = json.loads((runtime / "lifecycle.json").read_text())
assert lifecycle["recovery_segment"] == "20261016"
assert (
    lifecycle["boot_id"] == Path("/proc/sys/kernel/random/boot_id").read_text().strip()
)
assert lifecycle["ended_at"] is None
supervisor = Path("/proc") / str(lifecycle["supervisor_pid"])
assert (
    supervisor.joinpath("stat").read_text().split()[21]
    == lifecycle["supervisor_start_ticks"]
)
arguments = supervisor.joinpath("cmdline").read_bytes().split(b"\0")
assert (
    b"/mnt/d/dianzi/reports/runs/recovery_r01_runtime_recovery_20261016/supervise_recovered_daemon.py"
    in arguments
)
assert (
    supervisor.joinpath("cgroup").read_text().strip()
    == "0::/dianzi-r01-20261014/supervisor"
)
if not check_only:
    os.kill(lifecycle["supervisor_pid"], signal.SIGTERM)
print(
    json.dumps(
        {
            "operation": "owned_supervisor_identity_checked"
            if check_only
            else "owned_supervisor_term",
            "supervisor_pid": lifecycle["supervisor_pid"],
        }
    )
)
