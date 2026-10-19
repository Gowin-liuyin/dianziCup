"""Record independent review command output without exposing connection details."""

import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

run_directory = Path(__file__).resolve().parent
root = run_directory.parents[2]
label, *argv = sys.argv[1:]
zone = datetime.timezone(datetime.timedelta(hours=8))
environment = dict(os.environ)
environment["PYTHONPATH"] = str(root / "backend" / "src")
environment["UV_PROJECT_ENVIRONMENT"] = str(root / ".review-venv")
environment["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
started_at = datetime.datetime.now(zone).isoformat()
result = subprocess.run(argv, cwd=root / "backend", env=environment, capture_output=True)
output = result.stdout + result.stderr
(run_directory / f"{label}.log").write_bytes(output)
record = {"label": label, "argv": argv, "cwd": str(root / "backend"), "started_at": started_at,
          "ended_at": datetime.datetime.now(zone).isoformat(), "exit_code": result.returncode}
with (run_directory / "commands.jsonl").open("a", encoding="utf-8", newline="\n") as receipt:
    receipt.write(json.dumps(record, ensure_ascii=False) + "\n")
print(json.dumps(record, ensure_ascii=False))
print(output.decode("utf-8", errors="replace")[-6000:])
raise SystemExit(result.returncode)
