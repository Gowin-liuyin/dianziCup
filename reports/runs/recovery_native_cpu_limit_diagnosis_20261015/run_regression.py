"""Run the default unit gate once, with all caches outside the worktree."""

import json
import os
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
environment = os.environ.copy()
environment.update(PYTHONPATH=str(ROOT / "backend/src"), PYTHONDONTWRITEBYTECODE="1", COVERAGE_FILE="D:/tmp/nativecpu-diagnostic-20261015/.coverage", UV_CACHE_DIR="D:/tmp/nativecpu-diagnostic-20261015/uv")
Path("D:/tmp/nativecpu-diagnostic-20261015").mkdir(parents=True, exist_ok=True)
command = ["D:/wt/r06-feeds/backend/.venv/Scripts/python.exe", "-B", "-m", "pytest", "tests/unit", "-o", "cache_dir=D:/tmp/nativecpu-diagnostic-20261015/pytest-cache", "--basetemp=D:/tmp/nativecpu-diagnostic-20261015/pytest-temp", f"--junitxml={OUTPUT / 'unit.xml'}", f"--cov-report=json:{OUTPUT / 'unit_coverage.json'}"]
started = time.perf_counter()
record = {"command": command, "cwd": str(ROOT / "backend"), "started_at": datetime.now(timezone.utc).isoformat(), "head": "1927eeb00a7e0c1335f76340b0382f46102f08f2", "default_addopts_preserved": True, "timeout_seconds": 75}
with (OUTPUT / "unit.log").open("wb") as log:
    process = subprocess.run(command, cwd=ROOT / "backend", env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=75, check=False)
record.update(exit_code=process.returncode, wall_seconds=time.perf_counter() - started, completed_at=datetime.now(timezone.utc).isoformat())
(OUTPUT / "unit.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps(record))
