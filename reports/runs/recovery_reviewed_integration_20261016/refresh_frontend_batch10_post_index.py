"""Record an independent frontend source index before mounting the reviewed workspace."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
PROJECT = "dianzi-root-frontend-batch10_post-20261016"
PREFIX = [
    "C:/Program Files/WSL/wsl.exe", "-d", "Ubuntu-22.04", "--", "env",
    "CBM_CACHE_DIR=/tmp/dianzi-cbm-root-frontend-batch10_post-20261016",
    "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json",
]


def clock():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
paths = sorted(path for path in (ROOT / "frontend/src").rglob("*") if path.suffix in {".ts", ".tsx", ".css"})
snapshot = [{"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths]
(RUN / "frontend_batch10_post_index_source_files.json").write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8", newline="\n")
checks = [
    ("index", ["index_repository", "--repo-path", "/mnt/d/dianzi/frontend/src", "--mode", "full", "--name", PROJECT]),
    ("schema", ["get_graph_schema", "--project", PROJECT]),
    ("architecture", ["get_architecture", "--project", PROJECT]),
    ("workbench", ["trace_path", "--project", PROJECT, "--function-name", "Workbench", "--direction", "both", "--depth", "2", "--max-output-tokens", "2000"]),
]
receipts = []
for label, arguments in checks:
    started = clock()
    result = subprocess.run(PREFIX + arguments, cwd=ROOT, capture_output=True, timeout=60)
    (RUN / ("frontend_batch10_post_cbm_" + label + ".log")).write_bytes(result.stdout + result.stderr)
    receipts.append({"started_at": started, "ended_at": clock(), "baseline_sha": head, "scope": "frontend/src only; secrets/holdout/reports excluded", "source_snapshot": "frontend_batch10_post_index_source_files.json", "command": PREFIX + arguments, "cwd": str(ROOT), "exit_code": result.returncode})
    (RUN / "frontend_batch10_post_cbm_receipts.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"label": label, "exit_code": result.returncode}), flush=True)
    if result.returncode:
        break
raise SystemExit(0 if all(item["exit_code"] == 0 for item in receipts) else 1)
