"""Capture complete local command receipts without writing credential-bearing argv."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PYTHON = Path("D:/dianzi/backend/.venv/Scripts/python.exe")


def execute(name: str, argv: list[str], *, cwd: Path | None = None) -> int:
    started = datetime.now(ZoneInfo("Asia/Shanghai"))
    clock = time.perf_counter()
    env = dict(os.environ, PYTHONPATH=str(ROOT / "backend/src"))
    result = subprocess.run(argv, cwd=cwd or ROOT / "backend", env=env, capture_output=True)
    output = result.stdout + result.stderr
    for key in ("TEST_DATABASE_URL", "R12_OPENSEARCH_PASSWORD"):
        secret = env.get(key, "")
        if secret:
            output = output.replace(secret.encode(), b"[redacted]")
    if env.get("TEST_DATABASE_URL"):
        from sqlalchemy.engine import make_url

        password = make_url(env["TEST_DATABASE_URL"]).password or ""
        if password:
            output = output.replace(password.encode(), b"[redacted]")
            for offset in range(len(password) - 7):
                output = output.replace(
                    password[offset : offset + 8].encode(), b"[redacted-fragment]"
                )
    (RUN / f"{name}.log").write_bytes(output)
    receipt = {
        "argv": argv,
        "cwd": str(cwd or ROOT / "backend"),
        "started_at": started.isoformat(),
        "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "elapsed_seconds": time.perf_counter() - clock,
        "exit_code": result.returncode,
        "code_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT)
        .decode()
        .strip(),
        "log": f"{name}.log",
    }
    (RUN / f"{name}.command.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"name": name, "exit_code": result.returncode}))
    print(output.decode(errors="replace")[-1600:])
    return result.returncode


if __name__ == "__main__":
    name = sys.argv[1]
    arguments = sys.argv[2:]
    raise SystemExit(execute(name, [str(PYTHON), *arguments]))
