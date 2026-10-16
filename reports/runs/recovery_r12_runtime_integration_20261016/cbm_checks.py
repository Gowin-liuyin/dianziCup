"""Freeze current source relationships alongside the migration call-site searches."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PROJECT = "dianzi-r12-runtime-production-20261016"
PREFIX = ["wsl.exe", "-d", "Ubuntu-22.04", "--exec", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]


def execute(label, arguments):
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    result = subprocess.run(PREFIX + arguments, capture_output=True, timeout=45)
    (RUN / (label + ".log")).write_bytes(result.stdout + result.stderr)
    (RUN / (label + ".json")).write_text(json.dumps({
        "argv": PREFIX + arguments, "cwd": str(ROOT), "started_at": started,
        "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "exit_code": result.returncode,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    }, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"label": label, "exit_code": result.returncode}), flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)


execute("cbm_index", ["index_repository", "--repo-path", "/mnt/d/wt/r12-runtime-integration/backend/src", "--name", PROJECT, "--mode", "fast", "--persistence", "false"])
execute("cbm_schema", ["get_graph_schema", "--project", PROJECT])
execute("cbm_architecture", ["get_architecture", "--project", PROJECT, "--path", "ai_intel/retrieval", "--aspects", "overview", "--format", "json"])
for label, function, direction in (
    ("indexer_callers", "retrieval.indexing.HybridIndexer.refresh_scope", "inbound"),
    ("indexer_dependencies", "retrieval.indexing.HybridIndexer.refresh_scope", "outbound"),
    ("migration_callers", "infrastructure.database.run_migrations", "inbound"),
):
    execute("cbm_" + label, ["trace_path", "--project", PROJECT, "--function-name", PROJECT + ".ai_intel." + function, "--direction", direction, "--depth", "2", "--max-output-tokens", "2000", "--format", "json"])
