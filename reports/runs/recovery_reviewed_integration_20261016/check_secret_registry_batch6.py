"""在真实根 checkout 运行安全登记回归与原 T06 仓库扫描门。"""

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
environment = os.environ.copy()
environment["PYTHONPATH"] = str(ROOT / "backend/src")
environment["PYTHONIOENCODING"] = "utf-8"
for name in tuple(environment):
    if name.startswith(("GENERATION_", "DEEPSEEK_", "FOFA_", "HUNTER_", "QUAKE_", "ZOOMEYE_", "LANGSMITH_", "LANGCHAIN_")) or name == "TEST_DATABASE_URL":
        environment.pop(name)
mode = sys.argv[1] if len(sys.argv) > 1 else "all"
assert mode in {"all", "registry", "gate"}
label = "secret_registry_batch6" + ("" if mode == "all" else "_" + mode)
xml = RUN / (label + ".xml")
assert not xml.exists()
tests = []
if mode in {"all", "registry"}:
    tests.append("tests/security/test_r20_secret_provenance.py")
if mode in {"all", "gate"}:
    tests.append("tests/security/test_t06_authentication_and_scope.py::test_audit_and_sources_carry_no_secret_values_t06_c06")
command = [sys.executable, "-m", "pytest", "-o", "addopts=", "-q", *tests, "--junitxml=" + str(xml)]
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
tick = time.monotonic()
child = subprocess.Popen(command, cwd=ROOT / "backend", env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
(RUN / (label + "_started.json")).write_text(json.dumps({"started_at": started, "command": command, "owned_pid": child.pid, "maximum_seconds": 120}, indent=2) + "\n", encoding="utf-8")
try:
    stdout, stderr = child.communicate(timeout=120)
    exit_code = child.returncode
except subprocess.TimeoutExpired:
    child.kill()
    stdout, stderr = child.communicate()
    exit_code = 124
output = stdout + stderr
(RUN / (label + ".log")).write_bytes(output)
cases = ElementTree.parse(xml).findall(".//testcase") if xml.exists() else []
counts = {"total": len(cases), "failed": sum(case.find("failure") is not None for case in cases), "errors": sum(case.find("error") is not None for case in cases), "skipped": sum(case.find("skipped") is not None for case in cases)}
counts["passed"] = counts["total"] - counts["failed"] - counts["errors"] - counts["skipped"]
receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "duration_seconds": time.monotonic() - tick, "command": command, "cwd": str(ROOT / "backend"), "exit_code": exit_code, "owned_pid": child.pid, "owned_pid_exited": child.poll() is not None, "counts": counts, "log_sha256": hashlib.sha256(output).hexdigest(), "source_sha": "3b2fc48bb16afd5fea78520e55830b1ffb5d43b1", "root_source_manifest": "secret_registry_batch6.json", "actual_secret_value_scan": "not_run", "full_linux_ci": "not_run"}
(RUN / (label + "_run.json")).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
raise SystemExit(exit_code)
