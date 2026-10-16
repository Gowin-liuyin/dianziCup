"""Record the real staged material whitespace check without editing raw outputs."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
ZONE = ZoneInfo("Asia/Shanghai")
command = ["git", "diff", "--cached", "--check"]
started = datetime.now(ZONE).isoformat()
result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
(RUN / "fix3_material_diff_check.log").write_text(result.stdout + result.stderr, encoding="utf-8")
record = {"command": command, "cwd": str(ROOT), "started_at": started,
          "completed_at": datetime.now(ZONE).isoformat(), "exit_code": result.returncode,
          "raw_outputs_unchanged": True, "scope": "new material staging before final manifest restaging"}
(RUN / "fix3_material_diff_command.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps(record))
raise SystemExit(result.returncode)
