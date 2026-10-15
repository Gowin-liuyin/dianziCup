"""Record this slice's commands and original output bytes without shell interpolation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def main() -> int:
    run_directory = Path(__file__).resolve().parent
    workspace = run_directory.parents[2]
    label, relative_directory, *command = sys.argv[1:]
    working_directory = workspace / relative_directory
    if (
        not Path(command[0]).is_absolute()
        and (working_directory / command[0]).is_file()
    ):
        command[0] = str(working_directory / command[0])
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(workspace / "backend" / "src")
    started_at = datetime.now(timezone(timedelta(hours=8))).isoformat()
    result = subprocess.run(
        command,
        cwd=working_directory,
        env=environment,
        capture_output=True,
        check=False,
    )
    ended_at = datetime.now(timezone(timedelta(hours=8))).isoformat()
    (run_directory / f"{label}.stdout.log").write_bytes(result.stdout)
    (run_directory / f"{label}.stderr.log").write_bytes(result.stderr)
    commit = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=workspace, capture_output=True, check=True
        )
        .stdout.decode()
        .strip()
    )
    receipt = {
        "command": command,
        "cwd": str(working_directory),
        "started_at": started_at,
        "ended_at": ended_at,
        "exit_code": result.returncode,
        "code_sha": commit,
        "pythonpath": environment["PYTHONPATH"],
    }
    (run_directory / f"{label}.receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, ensure_ascii=False))
    print(result.stdout.decode("utf-8", errors="replace")[-7000:])
    print(result.stderr.decode("utf-8", errors="replace")[-2000:])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
