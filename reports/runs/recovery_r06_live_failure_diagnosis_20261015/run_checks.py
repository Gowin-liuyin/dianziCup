"""Record isolated local check commands without reading or emitting credentials."""

import json
import os
import subprocess
import sys
from pathlib import Path

from replay_originals import RUN, current_time

ROOT = RUN.parents[2]
BACKEND = ROOT / "backend"
PYTHON = str(BACKEND / ".venv/Scripts/python.exe")
commands = [
    ("synthetic_release_red_recheck", [PYTHON, "-m", "pytest", "--no-cov", "-q", str(RUN / "test_minimal_release_regressions.py"), "--junitxml=" + str(RUN / "synthetic_release_red_recheck.xml")]),
    ("existing_source_regression", [PYTHON, "-m", "pytest", "--no-cov", "-q",
        "tests/unit/test_r06_github_release_adapter.py", "tests/unit/test_r06_catalog_pages.py",
        "tests/unit/test_r06_source_boundary_regressions.py", "tests/unit/test_r06_feed_parsers.py",
        "tests/unit/test_r06_avid_record_adapter.py", "tests/unit/test_r06_source_worker.py",
        "--junitxml=" + str(RUN / "existing_source_regression.xml")]),
]
receipts = []
for label, argv in commands:
    started_at = current_time()
    result = subprocess.run(argv, cwd=BACKEND, env=dict(os.environ, PYTHONUTF8="1"),
                            capture_output=True, encoding="utf-8", timeout=90)
    (RUN / (label + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
    receipt = {"label": label, "argv": argv, "cwd": str(BACKEND), "started_at": started_at,
               "finished_at": current_time(), "exit_code": result.returncode,
               "environment_override": {"PYTHONUTF8": "1"}}
    receipts.append(receipt)
    (RUN / "check_commands.json").write_text(json.dumps(receipts, indent=2), encoding="utf-8")
(RUN / "check_commands.json").write_text(json.dumps(receipts, indent=2), encoding="utf-8")
print(json.dumps(receipts, indent=2))
