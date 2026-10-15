"""Run independent review commands and retain timestamps, exits, and raw output."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    directory = Path(__file__).resolve().parent
    started = datetime.now(timezone(timedelta(hours=8)))
    with (directory / f"{args.name}.log").open("wb") as output:
        try:
            result = subprocess.run(command, cwd=args.cwd, stdout=output, stderr=subprocess.STDOUT, timeout=args.timeout, check=False)
            exit_code = result.returncode
            timed_out = False
        except subprocess.TimeoutExpired:
            exit_code = 124
            timed_out = True
    ended = datetime.now(timezone(timedelta(hours=8)))
    receipt = {"command": command, "cwd": args.cwd, "started_at": started.isoformat(timespec="seconds"), "ended_at": ended.isoformat(timespec="seconds"), "exit_code": exit_code, "timed_out": timed_out, "log": str(directory / f"{args.name}.log")}
    (directory / f"{args.name}.receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    print((directory / f"{args.name}.log").read_text(encoding="utf-8", errors="replace")[-12000:])
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
