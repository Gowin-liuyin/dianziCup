"""隔离候选工作树检查问答等待预算，不请求真实模型。"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path("D:/dianzi-wt-r05-question-ui-timeout")
run = Path(__file__).resolve().parent / "question_ui_timeout"
run.mkdir(exist_ok=False)
clock = ZoneInfo("Asia/Shanghai")
checks = {
    "unit": ["npm.cmd", "test", "--", "--reporter=json", "--outputFile=" + str(run / "unit_results.json")],
    "types": ["npm.cmd", "run", "typecheck"],
    "lint": ["npm.cmd", "run", "lint"],
    "build": ["npm.cmd", "run", "build"],
    "trace": ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "/usr/bin/env", "CBM_CACHE_DIR=/tmp/dianzi-cbm-root-r05-ui-timeout-20261015", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json", "trace_path", "--project", "r05-ui-timeout", "--function-name", "fetchJson", "--direction", "both", "--include-tests", "true"],
}
failures = 0
for name, command in checks.items():
    started = datetime.now(clock).isoformat(timespec="seconds")
    result = subprocess.run(command, cwd=root / "frontend", capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    output = result.stdout + result.stderr
    (run / (name + ".log")).write_text(output, encoding="utf-8")
    receipt = {"started_at": started, "ended_at": datetime.now(clock).isoformat(timespec="seconds"), "command": command, "cwd": str(root / "frontend"), "exit_code": result.returncode, "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(), "tree_state": "timeout candidate working diff; freeze follows", "live": "not_run"}
    (run / (name + ".json")).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt), flush=True)
    failures += result.returncode != 0
raise SystemExit(bool(failures))
