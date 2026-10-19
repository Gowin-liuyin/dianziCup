"""Capture Linux init and relay ancestry before short official same-cache schema and trace tools."""

import json
import os
import signal
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

RUN = Path(__file__).resolve().parent
BINARY = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
PROJECT = "mnt-d-wt-r12-pfbr1-backend-src"


def identity(pid):
    raw = Path(f"/proc/{pid}/stat").read_text()
    fields = raw.rsplit(")", 1)[1].split()
    return {
        "pid": pid, "ppid": int(fields[1]), "birth_clock_ticks": int(fields[19]),
        "comm": raw.split("(", 1)[1].rsplit(")", 1)[0],
    }


ancestors = [identity(os.getpid())]
while ancestors[-1]["pid"] != 1 and len(ancestors) < 16:
    ancestors.append(identity(ancestors[-1]["ppid"]))
assert ancestors[-1]["pid"] == 1
control = {
    "started_at": datetime.now(UTC).isoformat(), "ancestors": ancestors,
    "complete_to_pid1": True, "preexisting_classification":
    "all control ancestors are observed and counted; shared init is never terminated",
}
(RUN / "cbm_resource_control.json").write_text(json.dumps(control, indent=2) + "\n")
os.sched_setaffinity(0, set(sorted(os.sched_getaffinity(0))[:2]))
environment = dict(os.environ, CBM_CACHE_DIR="/tmp/dianzi-cbm-r12-pfbr1-20261017", GOMAXPROCS="2")
commands = [
    ("schema", [BINARY, "cli", "--json", "get_graph_schema", "--project", PROJECT]),
    ("factory", [BINARY, "cli", "--json", "trace_path", "--project", PROJECT,
                 "--function-name", PROJECT + ".ai_intel.retrieval.runtime_policy.build_projection_job_handlers",
                 "--direction", "both", "--depth", "3", "--format", "json"]),
]
deadline = time.monotonic() + 23
results = []
for label, command in commands:
    started = datetime.now(UTC).isoformat()
    with (RUN / ("cbm_resource_" + label + ".raw.log")).open("xb") as log:
        child = subprocess.Popen(command, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        original = identity(child.pid)
        try:
            code = child.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            assert identity(child.pid)["birth_clock_ticks"] == original["birth_clock_ticks"]
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=1)
            code = 124
    results.append({
        "label": label, "argv": command, "started_at": started,
        "ended_at": datetime.now(UTC).isoformat(), "exit_code": code,
        "child_identity": original,
    })
    if code:
        break
(RUN / "cbm_resource_results.json").write_text(json.dumps({
    "results": results, "ancestors": ancestors, "complete_to_pid1": True,
    "affinity": sorted(os.sched_getaffinity(0)),
    "source_sha": "9cd6381eacc67853c055643d634ffb1812875214",
    "no_index_rebuild": True,
}, indent=2) + "\n")
print(json.dumps({"tools": len(results), "exit_codes": [item["exit_code"] for item in results]}))
raise SystemExit(next((item["exit_code"] for item in results if item["exit_code"]), 0))
