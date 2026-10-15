"""Record local verification without serializing environment values or credentials."""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
evidence_directory = Path(__file__).resolve().parent
run_name, working_directory, *command = sys.argv[1:]
started_at = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
result = subprocess.run(command, cwd=working_directory, capture_output=True, text=True, encoding="utf-8", errors="replace")
ended_at = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
log_path = evidence_directory / f"{run_name}.log"
log_path.write_text(result.stdout + result.stderr, encoding="utf-8")
record = {"name": run_name, "cwd": working_directory, "argv": command, "started_at": started_at, "ended_at": ended_at, "exit_code": result.returncode, "log": log_path.name}
with (evidence_directory / "commands.jsonl").open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(record, ensure_ascii=False) + "\n")
print(json.dumps(record, ensure_ascii=False))
print((result.stdout + result.stderr)[-1800:])
sys.exit(result.returncode)
