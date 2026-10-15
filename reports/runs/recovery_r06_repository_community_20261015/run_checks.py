"""Capture bounded commands and their real timestamps, exit codes and logs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
WORKTREE = RUN.parents[2]
ZONE = timezone(timedelta(hours=8))


def main() -> int:
    label, *command = sys.argv[1:]
    metadata_path = RUN / f"{label}.command.json"
    if metadata_path.exists():
        raise RuntimeError("Command evidence cannot be overwritten")
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(WORKTREE / "backend" / "src")
    metadata = {
        "command": command,
        "cwd": str(WORKTREE / "backend"),
        "started_at": datetime.now(ZONE).isoformat(timespec="seconds"),
        "timeout_seconds": 240,
        "baseline_sha": "1ff54965a0dd2e4f4a13245cee8dd59d2b3fdcfc",
    }
    with (RUN / f"{label}.log").open("w", encoding="utf-8") as output:
        try:
            result = subprocess.run(
                command,
                cwd=WORKTREE / "backend",
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=240,
                check=False,
            )
            metadata["exit_code"] = result.returncode
        except subprocess.TimeoutExpired:
            metadata["exit_code"] = 124
    metadata["ended_at"] = datetime.now(ZONE).isoformat(timespec="seconds")
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata), flush=True)
    return int(metadata["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
