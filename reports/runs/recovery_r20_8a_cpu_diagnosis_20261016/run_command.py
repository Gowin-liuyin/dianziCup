"""Record bounded local diagnostic commands without rewriting older evidence."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent


def run(name: str, argv: list[str], *, cwd: Path | None = None, timeout: int = 60) -> dict:
    started = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    begin = time.monotonic()
    environment = dict(os.environ)
    environment.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    completed = subprocess.run(argv, cwd=cwd or ROOT / "backend", env=environment,
                               capture_output=True, timeout=timeout, check=False)
    paths = {}
    for kind, payload in (("stdout", completed.stdout), ("stderr", completed.stderr)):
        path = RUN / f"{name}.{kind}.log"
        path.write_bytes(payload)
        paths[kind] = {"path": str(path), "sha256": hashlib.sha256(payload).hexdigest()}
    receipt = {"argv": argv, "cwd": str(cwd or ROOT / "backend"), "started_at": started,
               "ended_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
               "wall_seconds": time.monotonic() - begin, "exit_code": completed.returncode,
               "outputs": paths}
    (RUN / f"{name}.command.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"name": name, "exit_code": completed.returncode, "wall_seconds": receipt["wall_seconds"]}))
    return receipt


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2:])
