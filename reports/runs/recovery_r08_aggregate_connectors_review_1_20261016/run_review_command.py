"""Record independent commands without recording environment values."""

import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timedelta, timezone

RUN_DIRECTORY = Path(__file__).resolve().parent
WORKTREE = RUN_DIRECTORY.parents[2]
SHANGHAI = timezone(timedelta(hours=8))


def main() -> int:
    label, cwd, *argv = sys.argv[1:]
    started_at = datetime.now(SHANGHAI).isoformat(timespec="seconds")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(WORKTREE / "backend" / "src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=WORKTREE, text=True).strip()
    result = subprocess.run(argv, cwd=cwd, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    ended_at = datetime.now(SHANGHAI).isoformat(timespec="seconds")
    log = RUN_DIRECTORY / f"{label}.log"
    log.write_bytes(result.stdout)
    receipt = {
        "label": label,
        "argv": argv,
        "cwd": cwd,
        "started_at": started_at,
        "ended_at": ended_at,
        "head_sha": head,
        "code_sha": "8e150878a76e541e377b300f851d9c7caf919019",
        "exit_code": result.returncode,
        "log": str(log),
        "pythonpath": environment["PYTHONPATH"],
    }
    (RUN_DIRECTORY / f"{label}.command.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result.stdout.decode("utf-8", errors="replace"))
    print(json.dumps(receipt, ensure_ascii=False))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
