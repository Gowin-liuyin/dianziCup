"""Record a worktree-local source index and the actual API/worker call paths."""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
LABEL = sys.argv[1] if len(sys.argv) > 1 else "root_api_worker_wip"
assert LABEL.replace("_", "").isalnum()
PROJECT = "r07-root-api-" + LABEL
PREFIX = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
commands = [
    ("index", ["index_repository", "--repo-path", "/mnt/d/wt/r07-enrichment-jobs/backend/src", "--name", PROJECT, "--mode", "fast"]),
    ("schema", ["get_graph_schema", "--project", PROJECT]),
    ("architecture", ["get_architecture", "--project", PROJECT]),
]
for function in ("ai_intel.api.enrichment_routes.build_enrichment_router", "ai_intel.enrichment.runtime_policy.build_enrichment_job_service", "ai_intel.workers.runtime.consume_job"):
    commands.append(("trace_" + function.rsplit(".", 1)[-1], ["trace_path", "--project", PROJECT, "--function-name", PROJECT + "." + function, "--direction", "inbound", "--depth", "2", "--max-output-tokens", "2000"]))
records = []
for name, arguments in commands:
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    argv = PREFIX + arguments
    with (RUN / (LABEL + "_cbm_" + name + ".log")).open("xb") as output:
        result = subprocess.run(argv, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=120)
    record = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "cwd": str(ROOT), "argv": argv, "exit_code": result.returncode}
    records.append(record)
    if result.returncode:
        break
(RUN / (LABEL + "_cbm_receipt.json")).write_text(json.dumps({"head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "project": PROJECT, "index_scope": "backend/src; secrets/holdout/caches excluded by source-only root", "commands": records}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"project": PROJECT, "commands": len(records), "exit_codes": [item["exit_code"] for item in records]}))
raise SystemExit(any(item["exit_code"] != 0 for item in records))
