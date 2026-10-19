"""Run the integrated frozen offline suites and preserve every exit without changing gates."""

import json
import os
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "reports/runs/recovery_integrated_offline_20261016_1238"
RUN.mkdir(exist_ok=False)


def clock() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert head == "52b7143d6412935325ba344a92a61d31d7f9ddb8"
environment = os.environ.copy()
environment["PYTHONPATH"] = str(ROOT / "backend/src")
environment["TIKTOKEN_CACHE_DIR"] = "D:/dianzi-runtime-cache/tiktoken-o200k-base-20261016"
for name in tuple(environment):
    if name.startswith("TEST_"):
        del environment[name]
command = [str(ROOT / "backend/.venv/Scripts/python.exe"), "-m", "pytest", "tests/unit", "tests/contract",
           "--ignore=tests/contract/test_r14_tool_gateway_pg.py",
           "--ignore=tests/contract/test_r14_tool_gateway_review_pg.py",
           "--junitxml=" + str(RUN / "offline.xml"),
           "--cov-report=json:" + str(RUN / "coverage.json")]
started = clock()
with (RUN / "stdout.log").open("xb") as stdout, (RUN / "stderr.log").open("xb") as stderr:
    result = subprocess.run(command, cwd=ROOT / "backend", env=environment,
                            stdout=stdout, stderr=stderr, timeout=900, check=False)
counts = {name: 0 for name in ("tests", "failures", "errors", "skipped")}
if (RUN / "offline.xml").exists():
    for suite in ET.parse(RUN / "offline.xml").getroot().iter("testsuite"):
        for name in counts:
            counts[name] += int(suite.get(name, "0"))
receipt = {"started_at": started, "ended_at": clock(), "cwd": str(ROOT / "backend"),
           "head": head, "command": command, "exit_code": result.returncode, "counts": counts,
           "product_live": False, "separate_pg_not_run_cases": 20, "coverage_threshold_changed": False,
           "test_resource_environment_removed": True,
           "tokenizer_cache": environment["TIKTOKEN_CACHE_DIR"]}
(RUN / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
raise SystemExit(result.returncode)
