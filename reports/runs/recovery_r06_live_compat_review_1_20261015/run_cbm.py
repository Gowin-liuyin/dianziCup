"""Independent official CBM CLI index of this worktree's product source only."""

import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta, timezone

RUN = Path(__file__).resolve().parent
SOURCE = "/mnt/d/wt/r06-live-compat-review-1/backend/src"
PROJECT = "r06-live-compat-review-1-src"
BASE = ["wsl", "--exec", "env", "XDG_CACHE_HOME=/tmp/dianzi-cbm-r06-live-compat-review-1-cache",
        "CBM_ALLOWED_ROOT=" + SOURCE, "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"]


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


commands = [("version", BASE + ["--version"]),
            ("index", BASE + ["cli", "index_repository", "--repo-path", SOURCE, "--name", PROJECT, "--mode", "full"]),
            ("schema", BASE + ["cli", "get_graph_schema", "--project", PROJECT]),
            ("architecture", BASE + ["cli", "get_architecture", "--project", PROJECT, "--aspects", "overview"])]
for name in ("build_source_page_handler", "_fetch_catalog_page", "normalize_catalog_page", "_release_page", "parse_github_releases",
             "normalize_avid_blob", "normalize_avid_vulnerability", "persist_catalog_documents", "execute_job", "document_detail"):
    commands.append(("trace_" + name, BASE + ["cli", "trace_path", "--project", PROJECT, "--function-name", name,
        "--direction", "outbound", "--depth", "4", "--limit", "150", "--max-output-tokens", "4000"]))
receipts = []
for label, argv in commands:
    started = now()
    result = subprocess.run(argv, cwd=RUN.parents[2], capture_output=True, encoding="utf-8", timeout=90)
    (RUN / ("cbm_" + label + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
    receipts.append({"label": label, "argv": argv, "cwd": str(RUN.parents[2]), "started_at": started, "finished_at": now(), "exit_code": result.returncode})
    (RUN / "cbm_commands.json").write_text(json.dumps(receipts, indent=2), encoding="utf-8")
print(json.dumps({"commands": len(receipts), "exit_codes": [x["exit_code"] for x in receipts]}))
