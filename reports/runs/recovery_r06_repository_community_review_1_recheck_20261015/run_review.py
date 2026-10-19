"""Record independent commands without reading or printing credentials."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
WORKTREE = RUN.parents[2]
ZONE = timezone(timedelta(hours=8))


def main() -> int:
    label, working_directory, *command = sys.argv[1:]
    metadata_path = RUN / f"{label}.command.json"
    if metadata_path.exists():
        raise RuntimeError("Evidence already exists")
    metadata = {
        "command": command,
        "cwd": working_directory,
        "started_at": datetime.now(ZONE).isoformat(timespec="seconds"),
        "timeout_seconds": 300,
        "review_target_sha": "84faff95c20cdf98e411875349d5e48960a478ad",
        "review_target_tree": "976b5d572e12d82dbcc07a27bf7fe0bc859f551c",
    }
    with (RUN / f"{label}.log").open("wb") as output:
        try:
            result = subprocess.run(
                command,
                cwd=working_directory,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=300,
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
