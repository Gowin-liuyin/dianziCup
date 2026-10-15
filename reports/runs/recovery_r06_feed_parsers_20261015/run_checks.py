"""Capture bounded commands without borrowing product credentials or external IO."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent


def main() -> None:
    label, cwd_name, *command = sys.argv[1:]
    if not label.replace("_", "").isalnum() or not command:
        raise ValueError("invalid command label")
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("TEST_") or name.endswith("_API_KEY"):
            environment.pop(name)
    environment["CBM_CACHE_DIR"] = "/tmp/dianzi-cbm-r06-feed-parsers-20261015"
    environment["COVERAGE_FILE"] = str(RUN / f".coverage.{label}")
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    with (RUN / f"{label}.log").open("wb") as output:
        result = subprocess.run(
            command,
            cwd=ROOT / cwd_name,
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
            timeout=240,
            check=False,
        )
    metadata = {
        "started_at": started,
        "completed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(
            timespec="seconds"
        ),
        "command": command,
        "cwd": str(ROOT / cwd_name),
        "exit_code": result.returncode,
        "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
    }
    (RUN / f"{label}.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata))
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
