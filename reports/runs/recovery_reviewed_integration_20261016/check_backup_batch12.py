"""Check the qualified operator slice without connecting to any runtime database."""

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
checks = [
    ("unit", ["-m", "pytest", "tests/unit/test_r20_backup_restore.py", "tests/unit/test_t05_content_store_boundaries.py", "tests/unit/test_t06_access_scope_boundaries.py", "-q", "--no-cov", "--junitxml=" + str(RUN / "backup_batch12_unit.xml")]),
    ("mypy", ["-m", "mypy", "--strict", "../scripts/backup_restore.py"]),
    ("ruff", ["-m", "ruff", "check", "--config", "pyproject.toml", "../scripts/backup_restore.py", "tests/unit/test_r20_backup_restore.py", "tests/integration/test_r20_backup_restore_pg.py"]),
    ("format", ["-m", "ruff", "format", "--config", "pyproject.toml", "--check", "../scripts/backup_restore.py", "tests/unit/test_r20_backup_restore.py", "tests/integration/test_r20_backup_restore_pg.py"]),
]
receipts = []
for label, arguments in checks:
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    result = subprocess.run([str(PYTHON), *arguments], cwd=ROOT / "backend", env=environment, capture_output=True, timeout=120)
    (RUN / ("backup_batch12_" + label + ".log")).write_bytes(result.stdout + result.stderr)
    receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "command": [str(PYTHON), *arguments], "cwd": str(ROOT / "backend"), "exit_code": result.returncode, "scope": "offline unit and static only; no PG/Redis/MinIO/search/index rebuild/live or product model calls"}
    (RUN / ("backup_batch12_" + label + ".json")).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    receipts.append(receipt)
    print(json.dumps({"label": label, "exit_code": result.returncode}))
    if result.returncode:
        break
(RUN / "backup_batch12_checks.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8", newline="\n")
