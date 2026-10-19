"""Capture the offline frozen environment install with the original subprocess bytes."""

import json
import subprocess
from datetime import datetime
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
argv = ["uv", "sync", "--offline", "--frozen", "--extra", "semantic"]
started = datetime.now().astimezone().isoformat()
completed = subprocess.run(argv, cwd=ROOT / "backend", capture_output=True)
(RUN / "sync.log").write_bytes(completed.stdout + completed.stderr)
(RUN / "sync.json").write_text(json.dumps({"argv": argv, "cwd": str(ROOT / "backend"), "started_at": started, "finished_at": datetime.now().astimezone().isoformat(), "exit_code": completed.returncode}, indent=2), encoding="utf-8")
print(json.dumps({"exit_code": completed.returncode}))
raise SystemExit(completed.returncode)
