"""Run exact request contracts and retain command failures separately from test failures."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
label = sys.argv[1]
python = ROOT / "backend/.venv/Scripts/python.exe"
assert python.is_file()
argv = [str(python), "-m", "pytest", "tests/contract/test_r07_enrichment_job_request.py", "--no-cov", "-q", "--junitxml=" + str(RUN / (label + ".xml"))]
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
with (RUN / (label + ".log")).open("xb") as output:
    result = subprocess.run(argv, cwd=ROOT / "backend", env=dict(os.environ, PYTHONIOENCODING="utf-8"), stdout=output, stderr=subprocess.STDOUT, timeout=60)
receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "cwd": str(ROOT / "backend"), "argv": argv, "exit_code": result.returncode, "code_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "working_tree": "request tests and contracts under development; not frozen or independently accepted"}
(RUN / (label + ".json")).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
raise SystemExit(result.returncode)
