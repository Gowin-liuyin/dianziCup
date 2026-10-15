"""Record a safe local command's stdout/stderr, argv, clock, and exit code."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
BACKEND = RUN.parents[2] / "backend"


def current_time():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


label = sys.argv[1]
command = sys.argv[2:]
started_at = current_time()
result = subprocess.run(command, cwd=BACKEND, env=dict(os.environ, PYTHONUTF8="1"),
                        capture_output=True, encoding="utf-8", timeout=120)
(RUN / (label + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
receipt = {"argv": command, "cwd": str(BACKEND), "started_at": started_at,
           "finished_at": current_time(), "exit_code": result.returncode,
           "environment_override": {"PYTHONUTF8": "1"}}
(RUN / (label + "_command.json")).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(json.dumps(receipt, indent=2))
print("\n".join(result.stdout.splitlines()[-4:]))
raise SystemExit(result.returncode)
