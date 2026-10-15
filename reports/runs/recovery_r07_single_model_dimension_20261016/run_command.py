"""Capture local child commands without changing their exit code."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN_ROOT = Path(__file__).resolve().parent
WORKTREE = RUN_ROOT.parents[2]
name, working_directory, *arguments = sys.argv[1:]
environment = os.environ.copy()
environment["PYTHONPATH"] = str(WORKTREE / "backend" / "src")
started = datetime.now(ZoneInfo("Asia/Shanghai"))
source_sha = subprocess.check_output(
    ["git", "rev-parse", "HEAD"], cwd=WORKTREE, text=True
).strip()
result = subprocess.run(arguments, cwd=working_directory, env=environment, capture_output=True)
ended = datetime.now(ZoneInfo("Asia/Shanghai"))
(RUN_ROOT / f"{name}.stdout.log").write_bytes(result.stdout)
(RUN_ROOT / f"{name}.stderr.log").write_bytes(result.stderr)
receipt = {
    "argv": arguments,
    "cwd": working_directory,
    "started_at_shanghai": started.isoformat(),
    "ended_at_shanghai": ended.isoformat(),
    "exit_code": result.returncode,
    "source_sha": source_sha,
    "pythonpath": environment["PYTHONPATH"],
}
(RUN_ROOT / f"{name}.command.json").write_text(
    json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
)
print(json.dumps(receipt, ensure_ascii=False))
print(result.stdout.decode("utf-8", errors="replace"))
print(result.stderr.decode("utf-8", errors="replace"))
sys.exit(result.returncode)
