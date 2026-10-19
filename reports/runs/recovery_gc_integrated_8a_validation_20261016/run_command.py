"""Capture exact command receipts without recording environment values."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
ZONE = dt.timezone(dt.timedelta(hours=8))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--cwd", default=str(ROOT))
    parser.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
    if not argv:
        raise ValueError("a command is required")
    receipt_path = RUN / f"{args.label}.command.json"
    if receipt_path.exists():
        raise ValueError("label already used")
    receipt = {
        "label": args.label,
        "argv": argv,
        "cwd": args.cwd,
        "started_at": dt.datetime.now(ZONE).isoformat(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "tree": subprocess.check_output(["git", "show", "-s", "--format=%T", "HEAD"], cwd=ROOT, text=True).strip(),
        "environment_names": sorted(name for name in os.environ if name.startswith(("DIANZI_", "TEST_", "UV_", "PYTHON", "NODE", "npm_"))),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    with (RUN / f"{args.label}.stdout.log").open("wb") as stdout, (RUN / f"{args.label}.stderr.log").open("wb") as stderr:
        result = subprocess.run(argv, cwd=args.cwd, stdout=stdout, stderr=stderr, check=False)
    receipt.update(ended_at=dt.datetime.now(ZONE).isoformat(), exit_code=result.returncode)
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"label": args.label, "exit_code": result.returncode, "receipt": str(receipt_path)}))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
