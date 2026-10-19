"""Index only the fixed source tree with an independent external CBM cache."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
SOURCE = "/mnt/d/wt/r06-live-diagnosis-1156/backend/src"
TOOL = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
PROJECT = "r06-live-failure-diagnosis-1156-src"
BASE = [
    "wsl", "--exec", "env",
    "XDG_CACHE_HOME=/tmp/dianzi-cbm-r06-live-failure-diagnosis-1156-cache",
    "CBM_ALLOWED_ROOT=" + SOURCE, TOOL,
]


def current_time():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


commands = [
    ("version", BASE + ["--version"]),
    ("index", BASE + ["cli", "index_repository", "--repo-path", SOURCE, "--name", PROJECT,
                       "--mode", "full"]),
    ("schema", BASE + ["cli", "get_graph_schema", "--project", PROJECT]),
    ("architecture", BASE + ["cli", "get_architecture", "--project", PROJECT,
                              "--aspects", "overview"]),
]
for function_name in (
    "build_source_page_handler", "normalize_catalog_page", "_catalog_page",
    "select_avid_blob", "normalize_avid_blob", "_release_page", "_arxiv_page",
):
    commands.append(("trace_" + function_name, BASE + [
        "cli", "trace_path", "--project", PROJECT, "--function-name", function_name,
        "--direction", "outbound", "--depth", "4", "--limit", "150",
        "--max-output-tokens", "3000",
    ]))
receipts = []
for label, command in commands:
    started_at = current_time()
    result = subprocess.run(command, cwd=RUN.parents[2], capture_output=True,
                            encoding="utf-8", timeout=90)
    (RUN / ("cbm_" + label + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
    receipts.append({"label": label, "argv": command, "cwd": str(RUN.parents[2]),
                     "started_at": started_at, "finished_at": current_time(),
                     "exit_code": result.returncode})
    (RUN / "cbm_commands.json").write_text(json.dumps(receipts, indent=2), encoding="utf-8")
print(json.dumps({"commands": len(receipts), "exit_codes": [row["exit_code"] for row in receipts]}))
