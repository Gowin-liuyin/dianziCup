"""保留独立审查命令的原字节输出与真实执行元数据。"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
WORKTREE = RUN.parents[2]


def main() -> None:
    label, cwd_name, *command = sys.argv[1:]
    if not label.replace("_", "").isalnum() or not command:
        raise ValueError("invalid command label")
    if (RUN / f"{label}.json").exists():
        raise ValueError("receipt already exists")
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith(("TEST_", "DIANZI_")) or name.endswith("_API_KEY"):
            environment.pop(name)
    environment["PYTHONPATH"] = str(WORKTREE / "backend/src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    try:
        completed = subprocess.run(
            command, cwd=WORKTREE / cwd_name, env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, check=False,
        )
        output, exit_code = completed.stdout, completed.returncode
    except subprocess.TimeoutExpired as failure:
        output = (failure.stdout or b"") + b"\nINDEPENDENT_REVIEW_TIMEOUT_60_SECONDS\n"
        exit_code = 124
    (RUN / f"{label}.log").write_bytes(output)
    receipt = {
        "name": label, "cwd": str(WORKTREE / cwd_name), "argv": command,
        "started_at": started,
        "finished_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "exit_code": exit_code, "log": f"{label}.log", "log_bytes": len(output),
        "log_sha256": hashlib.sha256(output).hexdigest(),
        "head_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=WORKTREE, text=True).strip(),
    }
    (RUN / f"{label}.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=True), flush=True)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
