"""Run review commands with separate logs and exact local timestamps."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOG_ROOT = Path(__file__).resolve().parent
TZ = timezone(timedelta(hours=8))


def main() -> None:
    helper = Path("C:/Users/yinha/.codex/worktrees/r05-semantic-independent-review/dianzi/backend/src/ai_intel/infrastructure/process_limits.py")
    specification = importlib.util.spec_from_file_location("review_process_limits", helper)
    limiter = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(limiter)
    resource_handle = limiter.bound_process_resources(memory_bytes=2 * 1024**3, cpu_seconds=30)
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("cwd")
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--env", action="append", default=[])
    parser.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
    environment = os.environ.copy()
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "RAYON_NUM_THREADS"):
        environment[key] = "2"
    for item in args.env:
        key, value = item.split("=", 1)
        environment[key] = value
    started = datetime.now(TZ).isoformat(timespec="seconds")
    timer = time.monotonic()
    with (LOG_ROOT / f"{args.name}.stdout.log").open("wb") as output:
        with (LOG_ROOT / f"{args.name}.stderr.log").open("wb") as error:
            try:
                result = subprocess.run(command, cwd=args.cwd, env=environment, stdout=output,
                                        stderr=error, timeout=args.timeout, check=False)
                code = result.returncode
            except subprocess.TimeoutExpired:
                code = 124
    metadata = {"name": args.name, "cwd": args.cwd, "argv": command,
                "started_at": started, "finished_at": datetime.now(TZ).isoformat(timespec="seconds"),
                "wall_seconds": round(time.monotonic() - timer, 3), "exit_code": code,
                "environment_overrides": {item.split("=", 1)[0]: item.split("=", 1)[1]
                                          for item in args.env}}
    (LOG_ROOT / f"{args.name}.command.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False))
    raise SystemExit(code)


if __name__ == "__main__":
    main()
