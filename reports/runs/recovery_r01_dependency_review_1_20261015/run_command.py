"""Run one independent review command with byte logs and Shanghai timestamps."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--utf8", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    command = arguments.command
    if command and command[0] == "--":
        command = command[1:]
    run_root = Path(__file__).resolve().parent
    if (run_root / f"{arguments.name}.meta.json").exists():
        raise ValueError("A recorded command may not be overwritten")
    environment = os.environ.copy()
    if arguments.utf8:
        environment["PYTHONIOENCODING"] = "utf-8"
    zone = datetime.timezone(datetime.timedelta(hours=8))
    started_at = datetime.datetime.now(zone).isoformat(timespec="seconds")
    start_clock = time.monotonic()
    timed_out = False
    with (run_root / f"{arguments.name}.stdout.log").open("wb") as stdout:
        with (run_root / f"{arguments.name}.stderr.log").open("wb") as stderr:
            process = subprocess.Popen(command, cwd=arguments.cwd, env=environment, stdout=stdout, stderr=stderr)
            try:
                exit_code = process.wait(timeout=arguments.timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                process.kill()
                process.wait()
                exit_code = 124
    ended_at = datetime.datetime.now(zone).isoformat(timespec="seconds")
    metadata = {
        "command": command,
        "cwd": arguments.cwd,
        "started_at": started_at,
        "ended_at": ended_at,
        "timezone": "Asia/Shanghai",
        "duration_seconds": round(time.monotonic() - start_clock, 3),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "python_io_encoding": "utf-8" if arguments.utf8 else "inherited",
        "stdout": f"{arguments.name}.stdout.log",
        "stderr": f"{arguments.name}.stderr.log",
    }
    for key in ("stdout", "stderr"):
        metadata[f"{key}_sha256"] = hashlib.sha256((run_root / metadata[key]).read_bytes()).hexdigest()
    (run_root / f"{arguments.name}.meta.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
