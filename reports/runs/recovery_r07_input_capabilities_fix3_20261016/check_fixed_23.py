"""Replay the first frozen 23 reviewer inputs read-only against the final source."""

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
PROBE = ROOT / "reports/runs/recovery_r07_input_capabilities_20261016/fix2_original_test_review_probe.py"
ZONE = ZoneInfo("Asia/Shanghai")
report = RUN / "fixed_first_23.xml"
selection = (
    "not seen_and_omitted_required_context_together_is_failed and "
    "not model_cannot_supply_server_context_gaps and "
    "not context_gaps_are_immutable_and_computed_from_the_original_block"
)
command = [sys.executable, "-m", "pytest", "-q", str(PROBE), "-k", selection,
           "--no-cov", "--junitxml", str(report)]
environment = os.environ.copy()
environment["PYTHONDONTWRITEBYTECODE"] = "1"
started = datetime.now(ZONE).isoformat()
result = subprocess.run(command, cwd=ROOT / "backend", env=environment, capture_output=True, text=True)
report.with_suffix(".log").write_text(result.stdout + result.stderr, encoding="utf-8")
cases = ElementTree.parse(report).findall(".//testcase")
assert len(cases) == 23
receipt = {"command": command, "cwd": str(ROOT / "backend"), "started_at": started,
           "completed_at": datetime.now(ZONE).isoformat(), "exit_code": result.returncode,
           "tests": len(cases), "failed": sum(case.find("failure") is not None for case in cases),
           "errors": sum(case.find("error") is not None for case in cases),
           "skipped": sum(case.find("skipped") is not None for case in cases)}
report.with_suffix(".json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(json.dumps(receipt))
print((result.stdout + result.stderr)[-1000:])
raise SystemExit(result.returncode)
