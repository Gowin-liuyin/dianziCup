"""Save command output and timing without serializing environment or credentials."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
directory = Path(__file__).resolve().parent
label, cwd, *command = sys.argv[1:]
if (directory / f"{label}.log").exists():
    raise ValueError("Evidence labels cannot overwrite a previous run")
started_at = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
ended_at = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
(directory / f"{label}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
record = {"label": label, "cwd": cwd, "argv": command, "started_at": started_at, "ended_at": ended_at, "exit_code": result.returncode}
with (directory / "commands.jsonl").open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(record, ensure_ascii=False) + "\n")
print(json.dumps(record, ensure_ascii=False))
print((result.stdout + result.stderr)[-2000:])
sys.exit(result.returncode)
