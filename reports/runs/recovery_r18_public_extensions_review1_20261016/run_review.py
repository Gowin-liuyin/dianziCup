"""Run read-only review checks and keep exact command receipts."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone, timedelta


RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
LOCAL_TIME = timezone(timedelta(hours=8))


def main() -> None:
    name, relative_cwd, *command = sys.argv[1:]
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = str(ROOT / "backend/src")
    started_at = datetime.now(LOCAL_TIME).isoformat()
    result = subprocess.run(
        command, cwd=ROOT / relative_cwd, env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    (RUN / f"{name}.stdout.log").write_bytes(result.stdout)
    (RUN / f"{name}.stderr.log").write_bytes(result.stderr)
    receipt = {
        "name": name, "argv": command, "cwd": str(ROOT / relative_cwd),
        "started_at": started_at, "finished_at": datetime.now(LOCAL_TIME).isoformat(),
        "exit_code": result.returncode,
        "stdout": f"{name}.stdout.log", "stderr": f"{name}.stderr.log",
    }
    (RUN / f"{name}.command.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, ensure_ascii=False))
    print(result.stdout.decode("utf-8", errors="replace")[-2200:])
    if result.stderr:
        print(result.stderr.decode("utf-8", errors="replace")[-1500:])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
