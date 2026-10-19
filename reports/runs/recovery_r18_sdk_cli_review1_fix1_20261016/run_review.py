"""Record bounded independent review commands with raw output and exact timing."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="milliseconds")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    if not options.label.replace("_", "").isalnum() or not options.command:
        raise SystemExit("invalid review command")
    log = RUN / f"{options.label}.log"
    receipt = RUN / f"{options.label}.json"
    if log.exists() or receipt.exists():
        raise SystemExit("existing review evidence must not be overwritten")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "sdk/python")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["REVIEW_RUN_LABEL"] = options.label
    started = now()
    try:
        result = subprocess.run(
            options.command, cwd=ROOT, env=environment, capture_output=True, timeout=180
        )
        stdout, stderr, status = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as error:
        stdout, stderr, status = error.stdout or b"", error.stderr or b"", 124
    except OSError:
        stdout, stderr, status = b"", b"process could not be started", 127
    finished = now()
    log.write_bytes(stdout + b"\n--- stderr ---\n" + stderr)
    tests = None
    for argument in options.command:
        if argument.startswith("--junitxml="):
            junit = ROOT / argument.split("=", 1)[1]
            if junit.exists():
                suites = ET.parse(junit).getroot()
                suite = suites if suites.tag == "testsuite" else suites.find("testsuite")
                if suite is not None:
                    counts = {
                        name: int(suite.get(name, "0"))
                        for name in ("tests", "failures", "errors", "skipped")
                    }
                    counts["passed"] = (
                        counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
                    )
                    tests = counts
    record = {
        "command": options.command,
        "cwd": str(ROOT),
        "started_at": started,
        "finished_at": finished,
        "exit_code": status,
        "log_path": str(log.relative_to(ROOT)),
        "test_counts": tests,
        "python": sys.version,
        "python_executable": sys.executable,
        "pythonpath_override": environment["PYTHONPATH"],
        "fixture_only": True,
        "product_credentials_loaded": False,
    }
    receipt.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"label": options.label, "exit_code": status, "test_counts": tests}))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
