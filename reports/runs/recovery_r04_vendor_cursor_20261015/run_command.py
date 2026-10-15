"""Record bounded subprocess commands without loading secret stores."""

import argparse
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--cwd", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    root = Path(__file__).parent
    environment = {
        key: value
        for key, value in os.environ.items()
        if not any(word in key.upper() for word in ("KEY", "TOKEN", "PASSWORD", "SECRET"))
    }
    environment["PYTHONPATH"] = str(Path(args.cwd) / "src")
    coverage_root = Path(tempfile.gettempdir()) / "dianzi-r04-vendor-cursor-20261015"
    coverage_root.mkdir(exist_ok=True)
    environment["COVERAGE_FILE"] = str(coverage_root / (args.name + ".coverage"))
    environment.pop("VIRTUAL_ENV", None)
    started_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    started = time.monotonic()
    with (root / f"{args.name}.log").open("w", encoding="utf-8") as output:
        result = subprocess.run(
            command,
            cwd=args.cwd,
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
            timeout=300,
            check=False,
        )
    receipt = {
        "command": command,
        "cwd": args.cwd,
        "started_at": started_at,
        "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "duration_seconds": round(time.monotonic() - started, 3),
        "exit_code": result.returncode,
    }
    (root / f"{args.name}.receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, ensure_ascii=False))
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
