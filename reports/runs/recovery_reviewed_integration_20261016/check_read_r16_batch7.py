"""在主控候选源复跑两个独立离线集合，不将其计入live或完整阶段门。"""

import concurrent.futures
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


def execute_case(label, files):
    environment = os.environ.copy()
    environment.update({"PYTHONPATH": str(ROOT / "backend/src"), "PYTHONIOENCODING": "utf-8", "APP_ENV": "test", "DATA_MODE": "fixture", "SOURCE_POLLING_ENABLED": "false", "ENRICHMENT_GENERATION_ENABLED": "false"})
    command = [str(PYTHON), "-m", "pytest", *files, "-q", "--no-cov", "--junitxml=" + str(RUN / (label + ".xml"))]
    receipt = {"label": label, "started_at": clock(), "command": command, "cwd": str(ROOT / "backend"), "mode": "explicit fixture unit/contract; no PG/model/source", "baseline_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "working_source_manifest": "read_r16_batch7_integration.json", "timeout_seconds": 120}
    path = RUN / (label + ".json")
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    with (RUN / (label + ".log")).open("wb") as output:
        process = subprocess.Popen(command, cwd=ROOT / "backend", env=environment, stdout=output, stderr=subprocess.STDOUT)
        receipt["owned_pid"] = process.pid
        timed_out = False
        try:
            process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            process.wait(timeout=10)
    receipt.update({"ended_at": clock(), "exit_code": process.returncode, "timed_out": timed_out, "xml_generated": (RUN / (label + ".xml")).exists(), "log": str(RUN / (label + ".log"))})
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"label": label, "exit_code": process.returncode, "timed_out": timed_out}))
    return process.returncode


cases = [
    ("read_batch7_offline", ["tests/unit/test_r14_tool_gateway.py", "tests/unit/test_r14_tool_gateway_fix1.py", "tests/unit/test_r14_read_adapters.py", "tests/contract/test_r14_tool_gateway_contract.py", "tests/contract/test_r14_tool_gateway_review_negative.py"]),
    ("r16_batch7_offline", ["tests/unit/test_r16_revalidation_runtime.py", "tests/unit/test_r16_assessment_candidates.py", "tests/contract/test_r16_assessment_candidate_contracts.py"]),
]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    futures = [executor.submit(execute_case, label, files) for label, files in cases]
    results = [future.result() for future in futures]
raise SystemExit(0 if all(result == 0 for result in results) else 1)
