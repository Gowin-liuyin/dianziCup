"""Run related SDK checks using normal venv initialization, preserving the failed collection."""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
environment = os.environ.copy()
environment.update({"APP_ENV": "test", "DATA_MODE": "fixture", "PYTHONIOENCODING": "utf-8", "PYTHONPATH": os.pathsep.join([str(ROOT / "sdk/python"), str(ROOT / "backend/src")])})
for name in ("DATABASE_URL", "REDIS_URL", "GENERATION_API_KEY", "REVALIDATION_CURSOR_SIGNING_KEY", "FOFA_API_KEY", "HUNTER_API_KEY", "QUAKE_API_KEY", "ZOOMEYE_API_KEY"):
    environment.pop(name, None)
label = "sdk_batch10_related_fix1"
command = [str(ROOT / "backend/.venv/Scripts/python.exe"), "-m", "pytest", "tests/test_six_read_tools.py", "tests/test_public_extension_models.py", "tests/test_public_extension_models_fix1.py", "tests/test_client.py", "tests/test_models.py", "tests/test_mcp_adapter.py", "tests/test_output_budget.py", "tests/test_wire_formats.py", "tests/test_sdk_async_boundaries.py", "tests/test_sdk_total_deadline.py", "tests/test_cli.py", "tests/test_cli_fix1_regressions.py", "-q", "--junitxml=" + str(RUN / (label + ".xml"))]
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
with (RUN / (label + ".log")).open("wb") as output:
    result = subprocess.run(command, cwd=ROOT / "sdk/python", env=environment, stdout=output, stderr=subprocess.STDOUT, timeout=180)
receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "command": command, "cwd": str(ROOT / "sdk/python"), "exit_code": result.returncode, "timeout_seconds": 180, "baseline_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "scope": "changed six-tool/model/client/MCP paths and related unit/contract regressions; package distributions/native cancellation/stdio resource suites remain not_run in this batch", "initial_collection": "sdk_batch10_unit.log/xml preserved; direct base interpreter did not initialize pywin32.pth; environment failure before tests", "mode": "offline synthetic fixtures; no live/backend HTTP/model/PG/source"}
(RUN / (label + ".json")).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"exit_code": result.returncode, "scope": receipt["scope"]}))
raise SystemExit(result.returncode)
