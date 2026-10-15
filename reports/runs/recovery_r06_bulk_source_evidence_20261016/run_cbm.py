"""Freeze a source-only map in an independent WSL cache; no raw or test materials indexed."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
SOURCE = "/mnt/d/wt/r06-bulk-evidence/backend/src"
TOOL = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
PROJECT = "dianzi-r06-bulk-evidence"
prefix = ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "env",
          "CBM_ALLOWED_ROOT=" + SOURCE,
          "XDG_CACHE_HOME=/tmp/dianzi-cbm-r06-bulk-evidence-20261016", TOOL]
commands = [
    ("index_final", ["cli", "index_repository", "--repo-path", SOURCE,
                     "--name", PROJECT, "--mode", "full"]),
    ("schema", ["cli", "get_graph_schema", "--project", PROJECT]),
]
for name in ("register_source_revision_blocks", "add_text_block", "attach_evidence_span",
             "persist_catalog_documents", "persist_source_response", "execute_job"):
    commands.append(("trace_" + name, [
        "cli", "trace_path", "--project", PROJECT, "--function-name", name,
        "--direction", "both", "--depth", "3", "--limit", "250",
        "--max-output-tokens", "5000",
    ]))
sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                     text=True, check=True).stdout.strip()
tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, capture_output=True,
                      text=True, check=True).stdout.strip()
receipts = []
for label, args in commands:
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    result = subprocess.run(prefix + args, capture_output=True, text=True, timeout=60)
    (RUN / ("cbm_" + label + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
    receipts.append({"command": prefix + args, "started_at": started,
                     "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
                     "exit_code": result.returncode, "log": "cbm_" + label + ".log"})
record = {"code_commit": sha, "code_tree": tree, "allowed_root": SOURCE,
          "project": PROJECT, "commands": receipts}
(RUN / "cbm_commands.json").write_text(json.dumps(record, indent=2))
print(json.dumps({"code_commit": sha, "code_tree": tree,
                  "exit_codes": [row["exit_code"] for row in receipts]}))
assert all(row["exit_code"] == 0 for row in receipts)
