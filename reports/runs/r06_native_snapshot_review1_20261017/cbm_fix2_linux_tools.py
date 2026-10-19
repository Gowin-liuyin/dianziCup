"""Run one fresh index and short official queries with real guest control ancestry."""

import hashlib
import json
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
BINARY = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
CACHE = "/tmp/dianzi-cbm-r06-native-review1-fix2-20261017"
REPO = str(RUN / "cbm_scope_fix2")


def identity(pid):
    raw = Path(f"/proc/{pid}/stat").read_text()
    fields = raw.rsplit(")", 1)[1].split()
    return {"pid": pid, "ppid": int(fields[1]), "birth_clock_ticks": int(fields[19]), "comm": raw.split("(", 1)[1].rsplit(")", 1)[0]}


ancestors = [identity(os.getpid())]
while ancestors[-1]["pid"] != 1 and len(ancestors) < 16:
    ancestors.append(identity(ancestors[-1]["ppid"]))
assert ancestors[-1]["pid"] == 1
(RUN / "cbm_resource_control.json").write_text(json.dumps({
    "started_at": datetime.now(timezone.utc).isoformat(), "ancestors": ancestors,
    "complete_to_pid1": True, "tool_root_is_pid1": False,
    "preexisting_classification": "captured ancestors counted; shared init never treated as tool root or terminated",
}, indent=2) + "\n")
os.sched_setaffinity(0, set(sorted(os.sched_getaffinity(0))[:2]))
assert not Path(CACHE).exists()
environment = dict(os.environ, CBM_CACHE_DIR=CACHE, GOMAXPROCS="2", GOMEMLIMIT="480MiB")
deadline = time.monotonic() + 38
results = []


def run_tool(label, arguments):
    command = [BINARY, *arguments]
    started = datetime.now(timezone.utc).isoformat()
    output_path = RUN / ("fix2_cbm_" + label + ".raw.log")
    with output_path.open("xb") as output:
        child = subprocess.Popen(command, env=environment, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        birth = identity(child.pid)
        try:
            code = child.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            assert identity(child.pid)["birth_clock_ticks"] == birth["birth_clock_ticks"]
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=1)
            code = 124
    raw = output_path.read_bytes()
    result = {"label": label, "argv": command, "started_at": started,
              "ended_at": datetime.now(timezone.utc).isoformat(), "exit_code": code,
              "child_identity": birth, "real_wait_exit_observed": child.poll() is not None,
              "log_sha256": hashlib.sha256(raw).hexdigest()}
    results.append(result)
    if code:
        raise RuntimeError("CBM tool failed: " + label)
    if label == "help":
        return {}
    parsed = json.loads(raw)
    if parsed.get("isError"):
        raise RuntimeError("CBM result isError: " + label)
    return parsed


error = None
project = None
try:
    run_tool("help", ["--help"])
    indexed = run_tool("index", ["cli", "--json", "index_repository", "--repo-path", REPO, "--mode", "fast"])
    project = indexed["structuredContent"]["project"]
    run_tool("schema", ["cli", "--json", "get_graph_schema", "--project", project])
    run_tool("tree", ["cli", "--json", "trace_path", "--project", project,
                      "--function-name", project + ".core.windows_actor.process_tree",
                      "--direction", "both", "--depth", "3", "--format", "json"])
    run_tool("kill", ["cli", "--json", "trace_path", "--project", project,
                      "--function-name", project + ".core.windows_actor.WindowsOwnedActor.kill_owned_tree",
                      "--direction", "both", "--depth", "3", "--format", "json"])
except Exception as exception:
    error = {"type": type(exception).__name__, "message": str(exception)}
record = {"source_sha": "37ffe6da1d9a258359363d42488d236b7c00ad87", "cache": CACHE,
          "project": project, "binary_sha256": hashlib.sha256(Path(BINARY).read_bytes()).hexdigest(),
          "affinity": sorted(os.sched_getaffinity(0)), "ancestors": ancestors,
          "complete_to_pid1": True, "tool_root_is_pid1": False, "results": results, "error": error,
          "linux_memory_enforcement": "GOMEMLIMIT is a soft Go limit; no claimed hard guest memory cap"}
(RUN / "fix2_cbm_results.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({"tools": len(results), "exit_codes": [item["exit_code"] for item in results], "error": error}))
raise SystemExit(error is not None)
