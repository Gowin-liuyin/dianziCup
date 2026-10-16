"""Record bounded offline integration checks of the actual default HTTP application."""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
PYTHON = ROOT / "backend/.venv/Scripts/python.exe"


def clock():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


environment = os.environ.copy()
for name in (
    "DATABASE_URL", "REDIS_URL", "GENERATION_API_KEY", "EMBEDDING_API_KEY", "RERANKER_API_KEY",
    "FOFA_API_KEY", "HUNTER_API_KEY", "QUAKE_API_KEY", "REVALIDATION_CURSOR_SIGNING_KEY",
):
    environment.pop(name, None)
environment.update({"PYTHONPATH": str(ROOT / "backend/src"), "APP_ENV": "test", "DATA_MODE": "fixture", "SOURCE_POLLING_ENABLED": "false", "ENRICHMENT_GENERATION_ENABLED": "false", "PYTHONIOENCODING": "utf-8"})
commands = [
    ("assessment_batch8_offline", [str(PYTHON), "-m", "pytest", "tests/contract/test_r11_assessment_http_contracts.py", "tests/unit/test_r11_assessment_http_routes.py", "tests/contract/test_r11_default_assessment_mount.py", "tests/contract/test_r15_default_recommendation_mount.py", "tests/unit/test_r16_cursor_settings.py", "-q", "--no-cov", "--junitxml=" + str(RUN / "assessment_batch8_offline.xml")]),
    ("assessment_batch8_ruff", [str(PYTHON), "-m", "ruff", "check", "src/ai_intel/api/app.py", "src/ai_intel/assessment/http_contracts.py", "src/ai_intel/assessment/http_routes.py", "tests/contract/test_r11_default_assessment_mount.py"]),
    ("assessment_batch8_format", [str(PYTHON), "-m", "ruff", "format", "--check", "src/ai_intel/api/app.py", "src/ai_intel/assessment/http_contracts.py", "src/ai_intel/assessment/http_routes.py", "tests/contract/test_r11_default_assessment_mount.py"]),
    ("assessment_batch8_mypy", [str(PYTHON), "-m", "mypy", "src/ai_intel/api/app.py", "src/ai_intel/assessment/http_contracts.py", "src/ai_intel/assessment/http_routes.py", "src/ai_intel/infrastructure/settings.py"]),
]
receipts = []
for label, command in commands:
    receipt = {"label": label, "started_at": clock(), "command": command, "cwd": str(ROOT / "backend"), "mode": "explicit offline fixture, not live", "baseline_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "timeout_seconds": 120}
    destination = RUN / (label + ".json")
    destination.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    with (RUN / (label + ".log")).open("wb") as log:
        process = subprocess.Popen(command, cwd=ROOT / "backend", env=environment, stdout=log, stderr=subprocess.STDOUT)
        receipt["owned_pid"] = process.pid
        timed_out = False
        try:
            process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            process.wait(timeout=10)
    receipt.update({"ended_at": clock(), "exit_code": process.returncode, "timed_out": timed_out, "log": label + ".log"})
    destination.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    receipts.append(receipt)
    print(json.dumps({"label": label, "exit_code": process.returncode, "timed_out": timed_out}), flush=True)
(RUN / "assessment_batch8_check_receipts.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8", newline="\n")
raise SystemExit(0 if all(record["exit_code"] == 0 for record in receipts) else 1)
