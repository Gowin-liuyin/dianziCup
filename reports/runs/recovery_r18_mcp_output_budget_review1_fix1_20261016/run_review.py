"""Capture bounded independent commands and redirect legacy fixture receipts here."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


if __name__ == "__main__":
    label, *command = sys.argv[1:]
    log = RUN / f"{label}.log"
    receipt = RUN / f"{label}.json"
    if log.exists() or receipt.exists() or not command:
        raise SystemExit("invalid or already recorded command")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "sdk/python")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["REVIEW_RUN_LABEL"] = str(RUN / label)
    started = now()
    try:
        result = subprocess.run(
            command, cwd=ROOT, capture_output=True, env=environment, timeout=180, check=False
        )
        output = result.stdout + b"\n--- stderr ---\n" + result.stderr
        code = result.returncode
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or b"") + (error.stderr or b"") + b"\nTimeoutExpired\n"
        code = 124
    log.write_bytes(output)
    receipt.write_bytes(
        json.dumps(
            {
                "command": command,
                "cwd": str(ROOT),
                "started_at": started,
                "finished_at": now(),
                "exit_code": code,
                "log_path": log.name,
            },
            indent=2,
        ).encode()
        + b"\n"
    )
    print(json.dumps({"label": label, "exit_code": code, "log": str(log)}))
    raise SystemExit(code)
