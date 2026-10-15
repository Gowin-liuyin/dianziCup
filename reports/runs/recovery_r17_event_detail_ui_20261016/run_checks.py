"""Record one fixed, non-secret UI check with timestamps and the actual exit code."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

WORKSPACE = Path(__file__).resolve().parents[3]
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
RUN_DIRECTORY = Path(__file__).resolve().parent
FRONTEND = WORKSPACE / "frontend"
CBM_BINARY = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
CBM_PREFIX = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "env", "CBM_CACHE_DIR=/tmp/dianzi-cbm-r17-event-detail-ui-20261016", "CBM_ALLOWED_ROOT=/mnt/d/wt/r17-event-detail-ui/frontend/src", CBM_BINARY, "cli", "--json"]
CHECKS = {
    "cbm-index": (WORKSPACE, CBM_PREFIX + ["index_repository", "--repo-path", "/mnt/d/wt/r17-event-detail-ui/frontend/src", "--name", "r17-event-detail-c3-src", "--mode", "fast", "--persistence", "false"]),
    "cbm-schema": (WORKSPACE, CBM_PREFIX + ["get_graph_schema", "--project", "r17-event-detail-c3-src", "--format", "json"]),
    "cbm-architecture": (WORKSPACE, CBM_PREFIX + ["get_architecture", "--project", "r17-event-detail-c3-src", "--format", "json"]),
    "cbm-trace": (WORKSPACE, CBM_PREFIX + ["trace_path", "--args-file", "/mnt/d/wt/r17-event-detail-ui/reports/runs/recovery_r17_event_detail_ui_20261016/cbm-trace.args.json"]),
    "browser": (FRONTEND, ["node", "node_modules/@playwright/test/cli.js", "test", "--config", str(RUN_DIRECTORY / "playwright.config.mjs")]),
    "events-tests": (FRONTEND, ["npm.cmd", "run", "test", "--", "--run", "src/features/events/event-detail-view.test.tsx", "src/features/events/event-workspace.test.tsx", "--maxWorkers=1", "--no-file-parallelism", "--reporter=json", f"--outputFile={RUN_DIRECTORY / 'events-tests.json'}"]),
    "regression-tests": (FRONTEND, ["npm.cmd", "run", "test", "--", "--run", "--maxWorkers=1", "--no-file-parallelism", "--reporter=json", f"--outputFile={RUN_DIRECTORY / 'regression-tests.json'}"]),
    "typecheck": (FRONTEND, ["npm.cmd", "run", "typecheck"]),
    "lint": (FRONTEND, ["npm.cmd", "run", "lint"]),
    "build": (FRONTEND, ["npm.cmd", "run", "build"]),
    "diff-check": (WORKSPACE, ["git", "diff", "--check"]),
}

label = sys.argv[1]
output_label = sys.argv[2] if len(sys.argv) > 2 else label
check_cwd, command = CHECKS[label]
start = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
check_environment = dict(os.environ)
if label == "browser":
    check_environment["PLAYWRIGHT_BROWSERS_PATH"] = "C:/Users/yinha/.codex/cache/dianzi/r01_playwright_1248"
result = subprocess.run(command, cwd=check_cwd, env=check_environment, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
end = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
(RUN_DIRECTORY / f"{output_label}.stdout.log").write_text(result.stdout, encoding="utf-8")
(RUN_DIRECTORY / f"{output_label}.stderr.log").write_text(result.stderr, encoding="utf-8")
record = {"label": output_label, "cwd": str(check_cwd), "command": command, "start": start, "end": end, "exit_code": result.returncode}
with (RUN_DIRECTORY / "commands.jsonl").open("a", encoding="utf-8") as output:
    output.write(json.dumps(record, ensure_ascii=False) + "\n")
print(json.dumps(record, ensure_ascii=False))
print(result.stdout[-2200:])
print(result.stderr[-1200:])
sys.exit(result.returncode)
