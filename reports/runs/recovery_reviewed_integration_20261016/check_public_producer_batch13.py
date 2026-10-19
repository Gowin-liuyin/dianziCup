"""Check public producer registration and existing authentication without runtime IO."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import batch13_checks_helper as checks

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
checks.QUALIFIED = "c18cd5ea7ac0848cad5f6ac9e3896b8517eb875d"
paths = [
    "tests/unit/test_r18_public_producer_fix1_health.py",
    "tests/unit/test_r18_public_producer_fix2_declared.py",
    "tests/unit/test_r18_public_producer_fix3_origins.py",
    "tests/unit/test_r18_public_read_boundaries.py",
    "tests/contract/test_r18_public_producer_contract.py",
    "tests/security/test_r18_public_read_security.py",
    "tests/contract/test_r18_default_public_read_mount.py",
    "tests/contract/test_r14_default_investigation_mount.py",
]
result = checks.execute("public_producer_batch13_unit", [str(ROOT / "backend/.venv/Scripts/python.exe"), "-m", "pytest", *paths, "-q", "--no-cov", "--junitxml=" + str(RUN / "public_producer_batch13_unit.xml")])
counts = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
path = RUN / "public_producer_batch13_unit.xml"
if path.exists():
    for suite in ET.parse(path).getroot().iter("testsuite"):
        for key in counts:
            counts[key] += int(suite.get(key, 0))
(RUN / "public_producer_batch13_checks.json").write_text(json.dumps({"exit_code": int(result), "counts": counts, "integration": "not_run", "live": "not_run", "whole_task_accepted": False}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"exit_code": int(result), "counts": counts}))
raise SystemExit(result)
