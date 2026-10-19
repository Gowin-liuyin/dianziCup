"""Bound the independent source-only CBM tools and count complete guest ancestry."""

import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

RUN = Path(__file__).parent
BINARY = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
CACHE = "/tmp/dianzi-cbm-r18-http-review1-20261017"
PROJECT = "dianzi-r18-http-review1-20261017"
REPO = "/mnt/d/wt/r18-http-mcp-review1/sdk/python/ai_intel_client"


def identity(pid):
    raw = Path(f"/proc/{pid}/stat").read_text()
    fields = raw.rsplit(")", 1)[1].split()
    rss = int(fields[21]) * os.sysconf("SC_PAGE_SIZE")
    return {"pid": pid, "ppid": int(fields[1]), "birth_clock_ticks": int(fields[19]),
            "comm": raw.split("(", 1)[1].rsplit(")", 1)[0], "rss_bytes": rss}


def observed_tree(child):
    processes = {}
    for entry in Path("/proc").iterdir():
        if entry.name.isdecimal():
            try:
                item = identity(int(entry.name))
            except (OSError, ValueError):
                continue
            processes[item["pid"]] = item
    selected = {item["pid"]: processes.get(item["pid"], item) for item in ancestors}
    if child.pid in processes:
        selected[child.pid] = processes[child.pid]
    changed = True
    while changed:
        changed = False
        for item in processes.values():
            if item["pid"] not in selected and item["ppid"] in selected:
                if item["ppid"] in {ancestor["pid"] for ancestor in ancestors}:
                    if item["ppid"] != os.getpid():
                        continue
                selected[item["pid"]] = item
                changed = True
    return selected


ancestors = [identity(os.getpid())]
while ancestors[-1]["pid"] != 1 and len(ancestors) < 16:
    ancestors.append(identity(ancestors[-1]["ppid"]))
assert ancestors[-1]["pid"] == 1
assert len(ancestors) < 8
os.sched_setaffinity(0, set(sorted(os.sched_getaffinity(0))[:2]))
environment = dict(os.environ, CBM_CACHE_DIR=CACHE, GOMAXPROCS="2", GOMEMLIMIT="512MiB")
label = sys.argv[1]
commands = [("help", [BINARY, "--help"])] if label == "help" else [
    ("index", [BINARY, "cli", "--json", "index_repository", "--repo-path", REPO,
               "--name", PROJECT, "--mode", "fast"]),
    ("architecture", [BINARY, "cli", "--json", "get_architecture", "--project", PROJECT]),
    ("schema", [BINARY, "cli", "--json", "get_graph_schema", "--project", PROJECT]),
    ("transport_trace", [BINARY, "cli", "--json", "trace_path", "--project", PROJECT,
                         "--function-name", PROJECT + ".http_transport.create_http_app",
                         "--direction", "both", "--depth", "3", "--format", "json"]),
    ("adapter_trace", [BINARY, "cli", "--json", "trace_path", "--project", PROJECT,
                       "--function-name", PROJECT + ".mcp_adapter.create_current_read_tool_server",
                       "--direction", "both", "--depth", "3", "--format", "json"]),
]
deadline = time.monotonic() + 45
results = []
peak = {}
max_rss = 0
for tool, command in commands:
    started = datetime.now(UTC).isoformat()
    with (RUN / ("cbm_" + tool + ".raw.log")).open("xb") as log:
        child = subprocess.Popen(command, env=environment, stdout=log,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        original = identity(child.pid)
        failure = None
        while child.poll() is None:
            tree = observed_tree(child)
            if len(tree) > len(peak):
                peak = tree
            max_rss = max(max_rss, sum(item["rss_bytes"] for item in tree.values()))
            if len(tree) > 8:
                failure = "full_guest_process_cap_exceeded"
            elif any(item["rss_bytes"] > 512 * 1024**2 for item in tree.values()):
                failure = "sampled_process_rss_exceeded"
            elif sum(item["rss_bytes"] for item in tree.values()) > 1024**3:
                failure = "sampled_guest_rss_exceeded"
            elif time.monotonic() > deadline:
                failure = "deadline_exceeded"
            if failure:
                assert identity(child.pid)["birth_clock_ticks"] == original["birth_clock_ticks"]
                os.killpg(child.pid, signal.SIGKILL)
                break
            time.sleep(0.01)
        code = child.wait(timeout=1)
    results.append({"label": tool, "argv": command, "started_at": started,
                    "ended_at": datetime.now(UTC).isoformat(), "exit_code": code,
                    "failure": failure, "child_identity": original})
    if code or failure:
        break
record = {
    "source_sha": "9fb558aaab4b1630eac62a88be7e2c5686243dab",
    "material_sha": "ccbbf3f5688bc57a81c881504a09ea5d18471387",
    "repo": REPO, "cache": CACHE, "project": PROJECT,
    "binary_sha256": hashlib.sha256(Path(BINARY).read_bytes()).hexdigest(),
    "ancestors": ancestors, "full_ancestry_to_pid1": True,
    "guest_peak_count": len(peak), "guest_peak_chain": list(peak.values()),
    "sampled_peak_guest_rss_bytes": max_rss,
    "memory_control": "GOMEMLIMIT is soft; RSS sampled, not guest kernel hard limits",
    "cpu_affinity": sorted(os.sched_getaffinity(0)),
    "cleanup_root": "only each spawned tool session; shared ancestors never terminated",
    "remaining_owned_tools": [item for item in observed_tree(child).values()
                              if item["pid"] not in {ancestor["pid"] for ancestor in ancestors}],
    "source_sha256": {str(path.relative_to(Path(REPO))): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in Path(REPO).glob("*.py")},
    "results": results,
}
(RUN / ("cbm_" + label + ".guest.json")).write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({"tools": len(results), "codes": [item["exit_code"] for item in results],
                  "guest_peak": len(peak), "remaining_owned": len(record["remaining_owned_tools"])}))
raise SystemExit(next((item["exit_code"] or int(bool(item["failure"]))
                       for item in results if item["exit_code"] or item["failure"]), 0))
