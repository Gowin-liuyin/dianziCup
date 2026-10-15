"""保存本切片真实命令、原始输出和北京时间，不代替测试断言。"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

run_directory = Path(__file__).resolve().parent
workspace = run_directory.parents[2]
name = sys.argv[1]
command = sys.argv[2:]
environment = os.environ.copy()
environment["PYTHONPATH"] = str(workspace / "backend" / "src")
environment["XDG_CACHE_HOME"] = "/tmp/dianzi-r11-manifest-parser-cbm"
started_at = datetime.now(timezone(timedelta(hours=8))).isoformat()
result = subprocess.run(command, cwd=workspace / "backend", env=environment, capture_output=True)
ended_at = datetime.now(timezone(timedelta(hours=8))).isoformat()
(run_directory / f"{name}.stdout.log").write_bytes(result.stdout)
(run_directory / f"{name}.stderr.log").write_bytes(result.stderr)
sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=workspace).decode().strip()
receipt = {
    "command": command,
    "cwd": str(workspace / "backend"),
    "started_at": started_at,
    "ended_at": ended_at,
    "exit_code": result.returncode,
    "sha": sha,
    "data_mode": (
        "local static source analysis; no external IO"
        if name.startswith("cbm")
        else "explicit synthetic unit/contract/security fixture; no external IO"
    ),
}
(run_directory / f"{name}.json").write_text(
    json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(receipt, ensure_ascii=False))
sys.exit(result.returncode)
