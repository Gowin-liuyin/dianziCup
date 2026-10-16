"""Index the current backend source snapshot and record investigation call paths."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
PROJECT = "dianzi-root-source-storage-batch11-20261016"
PREFIX = [
    "wsl", "-d", "Ubuntu-22.04", "--", "env",
    "CBM_CACHE_DIR=/tmp/dianzi-cbm-root-source-storage-batch11-20261016",
    "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json",
]


def clock():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
files = sorted((ROOT / "backend/src").rglob("*.py"))
snapshot = [
    {"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    for path in files
]
(RUN / "source_storage_batch11_index_source_files.json").write_text(
    json.dumps(snapshot, indent=2) + "\n", encoding="utf-8", newline="\n"
)
checks = [
    ("index", ["index_repository", "--repo-path", "/mnt/d/dianzi/backend/src", "--mode", "full", "--name", PROJECT]),
    ("schema", ["get_graph_schema", "--project", PROJECT]),
    ("architecture", ["get_architecture", "--project", PROJECT]),
    ("workflow_tool", ["trace_path", "--project", PROJECT, "--function-name", PROJECT + ".ai_intel.investigation.workflow_service._WorkflowRuntime.tool", "--direction", "both", "--depth", "2", "--max-output-tokens", "2000"]),
    ("default_consumer", ["trace_path", "--project", PROJECT, "--function-name", PROJECT + ".ai_intel.workers.runtime.consume_job", "--direction", "both", "--depth", "2", "--max-output-tokens", "2000"]),
]
receipts = []
for label, arguments in checks:
    started = clock()
    result = subprocess.run(PREFIX + arguments, cwd=ROOT, capture_output=True, timeout=60)
    (RUN / ("source_storage_batch11_cbm_" + label + ".log")).write_bytes(result.stdout + result.stderr)
    receipt = {
        "started_at": started, "ended_at": clock(), "baseline_sha": head,
        "source_snapshot": "source_storage_batch11_index_source_files.json",
        "scope": "backend/src only; secrets, fixtures, holdout and reports excluded",
        "limitations": "Tool default exclusions checked against source/rg; assets require separate source verification",
        "command": PREFIX + arguments, "cwd": str(ROOT), "exit_code": result.returncode,
    }
    receipts.append(receipt)
    (RUN / "source_storage_batch11_cbm_receipts.json").write_text(
        json.dumps(receipts, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"label": label, "exit_code": result.returncode}), flush=True)
    if result.returncode:
        break
raise SystemExit(0 if all(item["exit_code"] == 0 for item in receipts) else 1)
