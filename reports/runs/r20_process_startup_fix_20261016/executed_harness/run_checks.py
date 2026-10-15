"""Capture bounded local check receipts without printing environment values."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PYTHON = Path("D:/dianzi/backend/.venv/Scripts/python.exe")
CBM = [
    "wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "/usr/bin/env",
    "CBM_CACHE_DIR=/tmp/r20-process-startup-fix-20261016",
    "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json",
]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    command = arguments.command
    if command[0] == "python":
        command[0] = str(PYTHON)
    elif command[0] == "cbm":
        command = [*CBM, *command[1:]]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "backend/src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    began = datetime.now(UTC).isoformat()
    started = time.monotonic()
    with (RUN / f"{arguments.name}.log").open("wb") as output:
        result = subprocess.run(
            command, cwd=ROOT / "backend", env=environment,
            stdout=output, stderr=subprocess.STDOUT, check=False, timeout=240,
        )
    receipt = {
        "argv": command, "cwd": str(ROOT / "backend"), "started_utc": began,
        "ended_utc": datetime.now(UTC).isoformat(), "exit_code": result.returncode,
        "wall_seconds": time.monotonic() - started,
        "code_files": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                ROOT / "backend/src/ai_intel/infrastructure/process_limits.py",
                ROOT / "backend/src/ai_intel/ingestion/parsing/_pdf_worker.py",
                ROOT / "backend/tests/unit/test_r20_process_startup.py",
            )
        },
    }
    (RUN / f"{arguments.name}.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"name": arguments.name, **receipt}, ensure_ascii=False))
    print((RUN / f"{arguments.name}.log").read_text(encoding="utf-8", errors="replace")[-9000:])


if __name__ == "__main__":
    main()
