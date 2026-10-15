"""Index only frozen source with an independent cache outside the workspace."""

from pathlib import Path
import datetime as dt
import json
import subprocess

ARTIFACTS = Path(__file__).resolve().parent
PROJECT = "r02-dimension-review1"
SOURCE = "/mnt/c/Users/yinha/.codex/worktrees/recovery-r02-dimensions-review/dianzi/backend/src"
BASE = ["wsl", "-u", "root", "--", "env",
        "CBM_CACHE_DIR=/tmp/dianzi-cbm-r02-dimension-review1-20261015",
        "CBM_ALLOWED_ROOT=" + SOURCE,
        "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
ZONE = dt.timezone(dt.timedelta(hours=8))

def timestamp():
    return dt.datetime.now(ZONE).isoformat(timespec="seconds")

commands = [
    ("cbm_index", ["index_repository", "--repo-path", SOURCE, "--name", PROJECT,
                   "--mode", "fast", "--persistence", "false"]),
    ("cbm_schema", ["get_graph_schema", "--project", PROJECT, "--format", "json"]),
    ("cbm_dimension_exact", ["search_graph", "--project", PROJECT, "--qn-pattern",
                             PROJECT + ".ai_intel.enrichment.persistence.DimensionRepository.publish",
                             "--format", "json"]),
    ("cbm_dimension_trace", ["trace_path", "--project", PROJECT, "--function-name",
                             PROJECT + ".ai_intel.enrichment.persistence.DimensionRepository.publish",
                             "--direction", "both", "--depth", "3", "--include-evidence", "true",
                             "--format", "json"]),
    ("cbm_validation_trace", ["trace_path", "--project", PROJECT, "--function-name",
                              PROJECT + ".ai_intel.enrichment.persistence.DimensionRepository._validate_references",
                              "--direction", "both", "--depth", "2", "--include-evidence", "true",
                              "--format", "json"]),
]

for name, arguments in commands:
    start = timestamp()
    process = subprocess.run(BASE + arguments, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
    (ARTIFACTS / (name + ".stdout.json")).write_text(process.stdout, encoding="utf-8")
    (ARTIFACTS / (name + ".stderr.log")).write_text(process.stderr, encoding="utf-8")
    (ARTIFACTS / (name + ".command.json")).write_text(json.dumps(
        {"start": start, "end": timestamp(), "command": BASE + arguments,
         "exit_code": process.returncode}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(name, process.returncode, process.stdout[:1500])
