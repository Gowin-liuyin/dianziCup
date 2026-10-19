"""Keep independent command evidence without exposing inherited environment values."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
CACHE = Path("D:/tmp/nativecpu-guard-review-1-recheck-20261015")
name, directory, *command = sys.argv[1:]
CACHE.mkdir(parents=True, exist_ok=True)
environment = os.environ.copy()
environment.update(
    PYTHONPATH=str(ROOT / "backend/src"),
    PYTHONDONTWRITEBYTECODE="1",
    COVERAGE_FILE=str(CACHE / ".coverage"),
    MYPY_CACHE_DIR=str(CACHE / "mypy"),
    RUFF_CACHE_DIR=str(CACHE / "ruff"),
    UV_CACHE_DIR=str(CACHE / "uv"),
)
record = {
    "command": command,
    "cwd": directory,
    "started_at": datetime.now().astimezone().isoformat(),
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "limiter_sha256": hashlib.sha256(
        (ROOT / "backend/src/ai_intel/infrastructure/process_limits.py").read_bytes()
    ).hexdigest(),
}
started = time.perf_counter()
try:
    with (OUTPUT / f"{name}.log").open("wb") as log:
        result = subprocess.run(command, cwd=directory, env=environment,
                                stdout=log, stderr=subprocess.STDOUT, timeout=150, check=False)
    record["exit_code"] = result.returncode
except subprocess.TimeoutExpired:
    record["exit_code"] = None
    record["outcome"] = "driver_timeout_150s"
record.update(wall_seconds=time.perf_counter() - started,
              completed_at=datetime.now().astimezone().isoformat())
(OUTPUT / f"{name}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps(record))
sys.exit(record["exit_code"] if record["exit_code"] is not None else 124)
