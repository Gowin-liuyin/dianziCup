"""Keep exact offline command evidence and the source SHA actually checked."""

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
ZONE = ZoneInfo("Asia/Shanghai")


def record(label: str, argv: list[str], cwd: Path) -> int:
    started = datetime.now(ZONE).isoformat()
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "backend/src")
    source_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    result = subprocess.run(argv, cwd=cwd, env=environment, capture_output=True, check=False)
    (RUN / f"{label}.stdout.log").write_bytes(result.stdout)
    (RUN / f"{label}.stderr.log").write_bytes(result.stderr)
    receipt = {
        "argv": argv,
        "cwd": str(cwd),
        "started_at_shanghai": started,
        "ended_at_shanghai": datetime.now(ZONE).isoformat(),
        "exit_code": result.returncode,
        "source_sha": source_sha,
        "base_material_sha": "6199ad193d36da17c6597ee286aae40af887d425",
        "pythonpath": environment["PYTHONPATH"],
    }
    (RUN / f"{label}.command.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt))
    print(result.stdout.decode("utf-8", errors="replace")[-5000:])
    print(result.stderr.decode("utf-8", errors="replace")[-1500:])
    return result.returncode


if __name__ == "__main__":
    record(sys.argv[1], sys.argv[3:], ROOT / sys.argv[2])
