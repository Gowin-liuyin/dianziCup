"""Run frozen fan-in offline regressions without database or model credentials."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import batch13_checks_helper as checks

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
checks.QUALIFIED = "ccbdf7ebb88e0245e72bcb0f52984e08739fe473"
paths = [
    "tests/contract/test_r16_fan_in_contracts.py",
    "tests/unit/test_r16_fan_in_outcomes.py",
    "tests/unit/test_r16_fan_in_runtime.py",
    "tests/unit/test_r16_runtime_drive.py",
    "tests/unit/test_r16_verified_content.py",
]
label = "fanin_batch13_unit"
code = checks.execute(label, [checks.PYTHON, "-m", "pytest", *paths, "-q", "--no-cov", "--junitxml=" + str(RUN / (label + ".xml"))])
counts = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
if (RUN / (label + ".xml")).exists():
    for suite in ET.parse(RUN / (label + ".xml")).getroot().iter("testsuite"):
        for key in counts:
            counts[key] += int(suite.get(key, 0))
receipt = {"exit_code": int(code), "counts": counts, "integration": "not_run", "live": "not_run", "whole_task_accepted": False}
(RUN / "fanin_batch13_checks.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
raise SystemExit(code)
