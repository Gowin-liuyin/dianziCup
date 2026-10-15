"""记录日期显示修改的调用图及前端检查；不读取凭据或访问外部服务。"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent / "ui_timestamp"
RUN.mkdir(exist_ok=True)


def execute(label, command, cwd):
    receipt_path = RUN / (label + ".json")
    if receipt_path.exists():
        raise FileExistsError(label)
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=180)
    (RUN / (label + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
    receipt = {"started_at": started,
               "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
               "command": command, "cwd": str(cwd), "exit_code": result.returncode,
               "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt), json.dumps((result.stdout + result.stderr)[-1800:]))
    return result.returncode


if __name__ == "__main__":
    import sys

    label, mode = sys.argv[1:]
    if mode == "index":
        base = ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "/usr/bin/env",
                "CBM_CACHE_DIR=/tmp/dianzi-cbm-root-ui-timestamp-20261015",
                "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
        code = execute(label + "_index", base + ["index_repository", "--repo-path",
                       "/mnt/d/dianzi/frontend/src", "--name", "dianzi-root-ui-timestamp", "--mode", "fast"], ROOT)
        if code == 0:
            code = execute(label + "_trace", base + ["trace_path", "--project", "dianzi-root-ui-timestamp",
                           "--function-name", "SavedTime", "--direction", "both", "--include-tests", "true"], ROOT)
    else:
        commands = {"test": ["npm.cmd", "test", "--", "--reporter=verbose"],
                    "typecheck": ["npm.cmd", "run", "typecheck"],
                    "lint": ["npm.cmd", "run", "lint"], "build": ["npm.cmd", "run", "build"]}
        code = execute(label, commands[mode], ROOT / "frontend")
    raise SystemExit(code)
