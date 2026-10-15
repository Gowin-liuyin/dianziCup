"""Capture only this preparation slice's fixed, local checks and their real timings."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
ZONE = timezone(timedelta(hours=8))
CHECKS = {
    "annotation_tests": [sys.executable, "-m", "unittest", "discover", "-s", "scripts/annotation/tests", "-v"],
    "ruff": [sys.executable, "-m", "ruff", "check", "scripts/annotation"],
    "format": [sys.executable, "-m", "ruff", "format", "--check", "scripts/annotation"],
    "mypy": [sys.executable, "-m", "mypy", "scripts/annotation/prepare.py", "--follow-imports=silent", "--follow-untyped-imports"],
    "verify_plan": [sys.executable, "scripts/verify_plan.py"],
    "plan_regression": [sys.executable, "-m", "pytest", "tests/plan/test_verify_plan.py", "tests/plan/test_recovery_plan.py", "-q"],
    "real_candidate": [sys.executable, "scripts/annotation/prepare.py", "validate", "--input", "benchmarks/manifests/r19_public_dev_candidate_v1.json"],
}

receipts = []
prefix = sys.argv[1]
names = sys.argv[2:] or list(CHECKS)
for name in names:
    command = CHECKS[name]
    start = datetime.now(ZONE).isoformat(timespec="seconds")
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False, timeout=90)
    end = datetime.now(ZONE).isoformat(timespec="seconds")
    log = f"{prefix}_{name}.log"
    (RUN / log).write_text(result.stdout + result.stderr, encoding="utf-8")
    receipts.append({"command": command, "cwd": str(ROOT), "start": start, "end": end, "exit_code": result.returncode, "log": log})
    print(name, result.returncode)
(RUN / f"{prefix}_commands.json").write_text(json.dumps(receipts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
raise SystemExit(int(any(receipt["exit_code"] for receipt in receipts)))
