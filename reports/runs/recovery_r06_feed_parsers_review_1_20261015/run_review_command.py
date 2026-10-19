"""Record independent review commands without logging inherited environment values."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = Path("D:/wt/r06-feed-review")
SHANGHAI = timezone(timedelta(hours=8))


def main() -> None:
    label, cwd, *command = sys.argv[1:]
    started = datetime.now(SHANGHAI).isoformat(timespec="seconds")
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("TEST_") or name.endswith("_API_KEY"):
            environment.pop(name)
    environment["COVERAGE_FILE"] = str(RUN / f".coverage.{label}")
    metadata: dict[str, object] = {
        "started_at": started,
        "command": command,
        "cwd": cwd,
        "target_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
    }
    with (RUN / f"{label}.log").open("wb") as output:
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=300,
                check=False,
            )
            metadata["exit_code"] = result.returncode
        except subprocess.TimeoutExpired:
            metadata["exit_code"] = 124
            metadata["review_command_timeout_seconds"] = 300
    metadata["completed_at"] = datetime.now(SHANGHAI).isoformat(timespec="seconds")
    (RUN / f"{label}.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False))
    raise SystemExit(int(metadata["exit_code"]))


if __name__ == "__main__":
    main()
