"""Record static checks and precise owned-file scope with actual local timestamps."""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
FILES = ["src/ai_intel/enrichment/job_service.py", "tests/unit/test_r07_idempotency_namespace.py", "tests/contract/test_r07_idempotency_namespace_contract.py", "tests/integration/test_r07_idempotency_scope_pg.py", "tests/integration/test_r07_idempotency_scope_api_pg.py", "tests/security/test_r07_idempotency_scope_security.py", "tests/r07_idempotency_scope_helpers.py"]
commands = [[sys.executable, "-m", "ruff", "check", *FILES], [sys.executable, "-m", "ruff", "format", "--check", *FILES], [sys.executable, "-m", "mypy", "src/ai_intel/enrichment/job_service.py"], ["git", "diff", "--check"]]
receipts = []
for index, command in enumerate(commands):
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    result = subprocess.run(command, cwd=ROOT / "backend", capture_output=True, text=True)
    (RUN / f"static_{index}.log").write_bytes((result.stdout + result.stderr).encode())
    receipts.append({"started_at": started, "completed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "command": command, "cwd": str(ROOT / "backend"), "exit_code": result.returncode})
(RUN / "static.json").write_bytes(json.dumps(receipts, indent=2).encode())
print(json.dumps({"checks": len(receipts), "exits": [item["exit_code"] for item in receipts]}))
raise SystemExit(next((item["exit_code"] for item in receipts if item["exit_code"]), 0))
