"""Capture a source-only graph for the immutable code commit, with caches outside the worktree."""

import json
import subprocess
from datetime import datetime
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PREFIX = ["wsl", "-d", "Ubuntu-22.04", "--", "env", "XDG_CACHE_HOME=/tmp/dianzi-cbm-r07-public-signals-20261015",
          "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
PROJECT = "r07-public-signals-7142c38"
COMMANDS = {
    "cbm_frozen_index": ["index_repository", "--repo-path", "/mnt/d/wt/r07-public-signals/backend/src",
                         "--name", PROJECT, "--mode", "moderate", "--persistence", "false"],
    "cbm_frozen_architecture": ["get_architecture", "--project", PROJECT],
    "cbm_frozen_schema": ["get_graph_schema", "--project", PROJECT],
    "cbm_frozen_enrichment_trace": ["trace_path", "--project", PROJECT, "--function-name", "enrich_structured_fields",
                                    "--direction", "both", "--depth", "2", "--max-output-tokens", "2400"],
    "cbm_frozen_selection_trace": ["trace_path", "--project", PROJECT, "--function-name", "select_public_signal_document",
                                   "--direction", "both", "--depth", "2", "--max-output-tokens", "1800"],
}
for name, arguments in COMMANDS.items():
    start = datetime.now().astimezone().isoformat(timespec="seconds")
    with (RUN / (name + ".json")).open("w", encoding="utf-8") as stream:
        result = subprocess.run(PREFIX + arguments, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=60, check=False)
    receipt = {"argv": PREFIX + arguments, "cwd": str(ROOT), "started_at": start,
               "ended_at": datetime.now().astimezone().isoformat(timespec="seconds"), "exit_code": result.returncode,
               "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               "range": "backend/src only; no fixtures, reports, secrets or holdout"}
    (RUN / (name + ".command.json")).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if result.returncode:
        raise SystemExit(result.returncode)
