"""Capture one bounded developer verification command without overwriting prior logs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    parsed = parser.parse_args()
    if not parsed.label.replace("_", "").isalnum() or not parsed.command:
        raise SystemExit("invalid verification command")
    log = RUN / (parsed.label + ".log")
    receipt = RUN / (parsed.label + ".json")
    if log.exists() or receipt.exists():
        raise SystemExit("verification label already recorded")
    started = now()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "sdk/python")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["REVIEW_RUN_LABEL"] = parsed.label
    try:
        result = subprocess.run(
            parsed.command,
            cwd=ROOT,
            capture_output=True,
            timeout=180,
            check=False,
            env=environment,
        )
        output = result.stdout + b"\n--- stderr ---\n" + result.stderr
        status = result.returncode
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or b"") + (error.stderr or b"") + b"\nTimeoutExpired\n"
        status = 124
    except OSError as error:
        output = (type(error).__name__ + ": process could not be started\n").encode()
        status = 127
    log.write_bytes(output)
    receipt.write_bytes(
        json.dumps(
            {
                "command": parsed.command,
                "cwd": str(ROOT),
                "started_at": started,
                "finished_at": now(),
                "exit_code": status,
                "log_path": log.name,
            },
            indent=2,
        ).encode()
        + b"\n"
    )
    print(json.dumps({"label": parsed.label, "exit_code": status, "log": str(log)}))
    raise SystemExit(status)
