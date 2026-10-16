"""Keep raw artifact whitespace visible separately from the frozen source diff check."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
checks = []
for label, command in [
    ("frozen_code", ["git", "diff", "--check", "7dae1d82363d8459f3546fee4b92137559dcb5aa^",
                     "7dae1d82363d8459f3546fee4b92137559dcb5aa"]),
    ("initial_material", ["git", "diff", "--check", "7dae1d82363d8459f3546fee4b92137559dcb5aa",
                          "eb6daced5f2467dc56ade15857e60a1af9486db0"]),
]:
    start = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    (RUN / (label + "_diff_check.log")).write_text(result.stdout + result.stderr, encoding="utf-8")
    checks.append({"label": label, "command": command, "cwd": str(ROOT), "started_at": start,
                   "completed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
                   "exit_code": result.returncode})
(RUN / "material_diff_commands.json").write_text(json.dumps(checks, indent=2))
print(json.dumps(checks))
raise SystemExit(checks[-1]["exit_code"])
