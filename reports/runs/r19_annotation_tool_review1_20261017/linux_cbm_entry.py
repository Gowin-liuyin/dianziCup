"""Record the owned WSL host identity before running the fixed local CBM binary."""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

run = Path(__file__).parent
label = sys.argv[1]
binary = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
identity = Path("/proc/self/stat").read_text()
parent_identity = Path(f"/proc/{os.getppid()}/stat").read_text()
(run / "tool_active_host.stat").write_text("host " + identity)
(run / (label + ".linux_host.stat")).write_text(
    "host " + identity + "parent " + parent_identity
)
started = datetime.now(timezone.utc).isoformat()
wall = time.monotonic()
command = [binary, *sys.argv[2:]]
environment = os.environ.copy()
environment["CBM_CACHE_DIR"] = "/tmp/dianzi-cbm-r19-annotation-review1-20261017"
child = subprocess.Popen(command, env=environment)
child_stat = Path(f"/proc/{child.pid}/stat").read_text()
child_fields = child_stat.rsplit(")", 1)[1].split()
seen = {child.pid: {"pid": child.pid, "ppid": int(child_fields[1]), "birth_clock_ticks": int(child_fields[19]), "comm": child_stat.split("(", 1)[1].rsplit(")", 1)[0]}}
peak = {}
failure = None


def owned_processes():
    entries = {}
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        try:
            value = (path / "stat").read_text()
            fields = value.rsplit(")", 1)[1].split()
            entries[int(path.name)] = {"pid": int(path.name), "ppid": int(fields[1]), "birth_clock_ticks": int(fields[19]), "comm": value.split("(", 1)[1].rsplit(")", 1)[0]}
        except (OSError, IndexError, ValueError):
            continue
    owned = {os.getpid()}
    ancestor = os.getpid()
    while entries[ancestor]["ppid"] > 1:
        parent = entries[ancestor]["ppid"]
        if parent not in entries:
            raise RuntimeError("owned Linux parent identity disappeared")
        if entries[parent]["birth_clock_ticks"] > entries[ancestor]["birth_clock_ticks"]:
            raise RuntimeError("reused Linux parent cannot establish ownership")
        owned.add(parent)
        ancestor = parent
    while True:
        added = {pid for pid, item in entries.items() if item["ppid"] in owned and item["birth_clock_ticks"] >= entries[item["ppid"]]["birth_clock_ticks"]}
        if added <= owned:
            break
        owned.update(added)
    return {pid: entries[pid] for pid in owned}


while True:
    current = owned_processes()
    seen.update(current)
    if not peak:
        peak = {**current, **seen}
    if len(current) > len(peak):
        peak = current
    live = run / (label + ".linux_live.json")
    pending_live = run / (label + ".linux_live.pending.json")
    pending_live.write_text(json.dumps({"label": label, "process_rows": list(current.values())}))
    pending_live.replace(live)
    if child.poll() is not None:
        break
    if len(current) > 9 or time.monotonic() - wall > 50:
        failure = "linux_process_limit_or_deadline_exceeded"
        child.kill()
        break
    time.sleep(0.02)
code = child.wait(timeout=5)
release_deadline = time.monotonic() + 3
while child.poll() is not None and time.monotonic() < release_deadline:
    time.sleep(0.05)
current = owned_processes()
ancestor_ids = {os.getpid()}
ancestor = os.getpid()
while current[ancestor]["ppid"] in current:
    ancestor = current[ancestor]["ppid"]
    ancestor_ids.add(ancestor)
remaining = [item for pid, item in current.items() if pid not in ancestor_ids]
record = {
    "started_at": started,
    "ended_at": datetime.now(timezone.utc).isoformat(),
    "elapsed_seconds": time.monotonic() - wall,
    "command": command,
    "host_stat": identity,
    "parent_stat": parent_identity,
    "child_stat": child_stat,
    "child_pid": child.pid,
    "exit_code": code,
    "waited": True,
    "process_rows": list(seen.values()),
    "peak_process_rows": list(peak.values()),
    "linux_peak_count": len(peak),
    "remaining_owned_children": remaining,
    "linux_control_ancestor_chain": [current[pid] for pid in ancestor_ids],
    "host_and_session_exit_verification": "Windows wsl process wait; host/session are still running while this receipt is written",
    "failure": failure,
    "cache_path": environment["CBM_CACHE_DIR"],
}
(run / (label + ".linux_receipt.json")).write_text(json.dumps(record, indent=2) + "\n")
raise SystemExit(int(code or bool(failure or remaining)))
