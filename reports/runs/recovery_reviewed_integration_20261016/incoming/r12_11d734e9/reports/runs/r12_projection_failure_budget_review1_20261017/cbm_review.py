"""Run official single-shot CBM CLI tools in an isolated source-only Linux cache."""

import hashlib
import json
import os
import signal
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

RUN = Path(__file__).resolve().parent
BINARY = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
CACHE = "/tmp/dianzi-cbm-r12-pfbr1-20261017"
PROJECT = "mnt-d-wt-r12-pfbr1-backend-src"
REPO = "/mnt/d/wt/r12-pfbr1/backend/src"
os.sched_setaffinity(0, set(sorted(os.sched_getaffinity(0))[:2]))
(RUN / "tool_active_host.stat").write_text("host " + Path(f"/proc/{os.getpid()}/stat").read_text())
environment = dict(os.environ, CBM_CACHE_DIR=CACHE, GOMAXPROCS="2")
tools = [
    ("help", [BINARY, "--help"]),
    ("index", [BINARY, "cli", "--json", "index_repository", "--repo-path", REPO, "--mode", "fast"]),
    ("schema", [BINARY, "cli", "--json", "get_graph_schema", "--project", PROJECT]),
]
for name, function in (
    ("consumer", "ai_intel.workers.runtime.consume_job"),
    ("factory", "ai_intel.retrieval.runtime_policy.build_projection_job_handlers"),
    ("prepare", "ai_intel.retrieval.indexing.HybridIndexer.prepare_generation"),
    ("create", "ai_intel.retrieval.opensearch_client.OpenSearchCorpusClient.create_index"),
):
    tools.append((name, [
        BINARY, "cli", "--json", "trace_path", "--project", PROJECT,
        "--function-name", PROJECT + "." + function,
        "--direction", "both", "--depth", "3", "--format", "json",
    ]))
deadline = time.monotonic() + 54
results = []
for label, command in tools:
    start = datetime.now(UTC).isoformat()
    log = RUN / ("cbm_" + label + ".raw.log")
    assert not log.exists()
    with log.open("wb") as output:
        process = subprocess.Popen(
            command, env=environment, stdout=output, stderr=subprocess.STDOUT, start_new_session=True
        )
        birth = Path(f"/proc/{process.pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
        try:
            code = process.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            current = Path(f"/proc/{process.pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
            assert current == birth
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=1)
            code = 124
    result = {
        "label": label, "argv": command, "started_at": start,
        "ended_at": datetime.now(UTC).isoformat(), "exit_code": code,
        "pid": process.pid, "birth_clock_ticks": birth,
        "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
    }
    results.append(result)
    print(json.dumps(result), flush=True)
    if code != 0:
        break
(RUN / "cbm_results.json").write_text(json.dumps({
    "source_sha": "9cd6381eacc67853c055643d634ffb1812875214",
    "cache": CACHE, "project": PROJECT,
    "binary_sha256": hashlib.sha256(Path(BINARY).read_bytes()).hexdigest(),
    "affinity": sorted(os.sched_getaffinity(0)),
    "results": results,
}, indent=2) + "\n")
raise SystemExit(next((item["exit_code"] for item in results if item["exit_code"]), 0))
