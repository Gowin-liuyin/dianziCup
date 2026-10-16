"""Record one bounded offline integration run of merged workflow, recovery and root mounts."""

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
environment.update({"APP_ENV": "test", "DATA_MODE": "fixture", "SOURCE_POLLING_ENABLED": "false", "ENRICHMENT_GENERATION_ENABLED": "false", "PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(ROOT / "backend/src")})
for key in ("DATABASE_URL", "REDIS_URL", "GENERATION_API_KEY", "REVALIDATION_CURSOR_SIGNING_KEY"):
    environment.pop(key, None)
commands = [
    ("investigation_batch9_offline", [str(PYTHON), "-m", "pytest", "tests/unit/test_r14_langgraph_workflow.py", "tests/unit/test_r14_langgraph_workflow_fix1.py", "tests/unit/test_r14_default_runtime.py", "tests/unit/test_r14_preclaim_recovery.py", "tests/unit/test_r14_terminal_outbox_selection.py", "tests/unit/test_r14_qa_citation_prompt_fix1.py", "tests/contract/test_r14_langgraph_workflow_contract.py", "tests/contract/test_r14_qa_citation_prompt_wire_fix1.py", "tests/contract/test_r14_default_investigation_mount.py", "tests/contract/test_r11_default_assessment_mount.py", "tests/contract/test_r15_default_recommendation_mount.py", "tests/unit/test_r16_revalidation_runtime.py", "-q", "--no-cov", "--junitxml=" + str(RUN / "investigation_batch9_offline.xml")]),
    ("investigation_batch9_mypy", [str(PYTHON), "-m", "mypy", "src/ai_intel/api/app.py", "src/ai_intel/api/investigation_routes.py", "src/ai_intel/investigation", "src/ai_intel/workers/runtime.py", "src/ai_intel/workers/investigation.py", "src/ai_intel/workers/jobs.py", "src/ai_intel/infrastructure/outbox.py"]),
]
results = []
for label, command in commands:
    receipt = {"started_at": clock(), "command": command, "cwd": str(ROOT / "backend"), "label": label, "timeout_seconds": 180, "mode": "explicit offline unit/contract fixtures; no real PG/Redis/model/source", "baseline_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "source_receipt": "investigation_runtime_batch9_integration.json"}
    path = RUN / (label + ".json")
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    with (RUN / (label + ".log")).open("wb") as log:
        process = subprocess.Popen(command, cwd=ROOT / "backend", env=environment, stdout=log, stderr=subprocess.STDOUT)
        receipt["owned_pid"] = process.pid
        timeout = False
        try:
            process.wait(timeout=180)
        except subprocess.TimeoutExpired:
            timeout = True
            process.kill()
            process.wait(timeout=10)
    receipt.update({"ended_at": clock(), "exit_code": process.returncode, "timed_out": timeout})
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    results.append(receipt)
    print(json.dumps({"label": label, "exit_code": process.returncode, "timed_out": timeout}), flush=True)
(RUN / "investigation_batch9_check_receipts.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8", newline="\n")
raise SystemExit(0 if all(item["exit_code"] == 0 for item in results) else 1)
