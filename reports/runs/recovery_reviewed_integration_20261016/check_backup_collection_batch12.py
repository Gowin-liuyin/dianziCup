"""Collect the imported Windows PG cases and verify plan structure without provisioning."""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
PYTHON = ROOT / "backend/.venv/Scripts/python.exe"
environment = dict(os.environ)
environment.update({"APP_ENV": "test", "DATA_MODE": "fixture", "PYTHONPATH": str(ROOT) + os.pathsep + str(ROOT / "backend/src")})
receipts = []
for label, command, cwd in [
    ("collect", [str(PYTHON), "-m", "pytest", "tests/integration/test_r20_backup_restore_pg.py", "--collect-only", "--no-cov", "-q"], ROOT / "backend"),
    ("plan", [str(PYTHON), "scripts/verify_plan.py"], ROOT),
]:
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, timeout=60)
    (RUN / ("backup_batch12_" + label + ".log")).write_bytes(result.stdout + result.stderr)
    receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "command": command, "cwd": str(cwd), "exit_code": result.returncode, "scope": "collect and structural checks only; no PG/source/model/resource operations"}
    receipts.append(receipt)
    print(json.dumps({"label": label, "exit_code": result.returncode}))
(RUN / "backup_batch12_collection_checks.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8", newline="\n")
