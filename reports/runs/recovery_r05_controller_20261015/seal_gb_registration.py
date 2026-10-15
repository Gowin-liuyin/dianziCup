"""Seal reviewed raw bytes and run the existing plan and credential regressions."""

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


archive = ROOT / "reports/runs/recovery_gb_checkpoint_review_1_20261015"
files = [path for path in archive.rglob("*") if path.is_file()]
inventory = [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(files)]
(archive / ".gitattributes").write_text("* -text whitespace=trailing-space,space-before-tab,cr-at-eol\n*.log -diff\n*.xml -diff\n", encoding="utf-8")
(RUN / "gb_review_archive_inventory.json").write_text(json.dumps({"recorded_at": now(), "files": inventory}, indent=2) + "\n", encoding="utf-8")
commands = [
    ("gb_registration_plan", [sys.executable, "-m", "pytest", "tests/plan", "-q", f"--junitxml={RUN / 'gb_registration_plan.xml'}"], ROOT),
    ("gb_registration_secret_test", [sys.executable, "-m", "pytest", "tests/security/test_t06_authentication_and_scope.py", "-q", "--no-cov", f"--junitxml={RUN / 'gb_registration_secret_test.xml'}"], ROOT / "backend"),
]
for name, argv, cwd in commands:
    start = now()
    with (RUN / f"{name}.log").open("wb") as output:
        result = subprocess.run(argv, cwd=cwd, stdout=output, stderr=subprocess.STDOUT, check=False)
    (RUN / f"{name}.json").write_text(json.dumps({"argv": argv, "cwd": str(cwd), "started_at": start, "ended_at": now(), "exit_code": result.returncode}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"check": name, "exit_code": result.returncode}), flush=True)
    if result.returncode:
        sys.exit(result.returncode)
