"""Execute the independent reviewer original probe read-only against this owned source."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PROBE = Path("D:/wt/r07-input-review1/reports/runs/recovery_r07_input_review1_20261016/test_review_probe.py")
stamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%H%M%S")
report = RUN / ("independent_original_" + stamp + ".xml")
command = [sys.executable, "-m", "pytest", "-q", str(PROBE), "--no-cov", "--junitxml", str(report)]
environment = os.environ.copy()
environment["PYTHONDONTWRITEBYTECODE"] = "1"
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
result = subprocess.run(command, cwd=ROOT / "backend", env=environment, capture_output=True, text=True)
report.with_suffix(".log").write_text(result.stdout + result.stderr, encoding="utf-8")
cases = ElementTree.parse(report).findall(".//testcase")
receipt = {"command": command, "cwd": str(ROOT / "backend"), "started_at": started,
           "completed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "exit_code": result.returncode,
           "tests": len(cases), "failed": sum(case.find("failure") is not None for case in cases),
           "errors": sum(case.find("error") is not None for case in cases),
           "skipped": sum(case.find("skipped") is not None for case in cases)}
report.with_suffix(".json").write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt))
print((result.stdout + result.stderr)[-3500:])
raise SystemExit(result.returncode)
