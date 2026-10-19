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
        "review_target_sha": "5e952f25d7a1c03296e1a8801a757c9c0317af99",
        "review_target_tree": "c99ba0178c781e3d48555b5ddbd8d9743c420d8a",
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
