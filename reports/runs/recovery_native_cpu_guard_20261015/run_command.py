"""Run one named offline check and retain exact command, source version and exit status."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
name, *command = sys.argv[1:]
environment = os.environ.copy()
environment.update(PYTHONPATH=str(ROOT / "backend/src"), PYTHONDONTWRITEBYTECODE="1", COVERAGE_FILE="D:/tmp/nativecpu-guard-20261015/.coverage", UV_CACHE_DIR="D:/tmp/nativecpu-guard-20261015/uv", MYPY_CACHE_DIR="D:/tmp/nativecpu-guard-20261015/mypy", RUFF_CACHE_DIR="D:/tmp/nativecpu-guard-20261015/ruff")
Path("D:/tmp/nativecpu-guard-20261015").mkdir(parents=True, exist_ok=True)
started = time.perf_counter()
record = {"command": command, "cwd": str(ROOT / "backend"), "started_at": datetime.now(timezone.utc).isoformat(), "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "limiter_sha256": hashlib.sha256((ROOT / "backend/src/ai_intel/infrastructure/process_limits.py").read_bytes()).hexdigest()}
with (OUTPUT / f"{name}.log").open("wb") as log:
    process = subprocess.run(command, cwd=ROOT / "backend", env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=120, check=False)
record.update(exit_code=process.returncode, wall_seconds=time.perf_counter() - started, completed_at=datetime.now(timezone.utc).isoformat())
(OUTPUT / f"{name}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps(record))
