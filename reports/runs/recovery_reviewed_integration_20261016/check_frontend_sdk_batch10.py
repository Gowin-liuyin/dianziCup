"""Validate the reviewed SDK and default investigation mount without external services."""

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
PYTHON = Path("C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe")
NODE = "C:/Program Files/nodejs/node.exe"
protected = ROOT / "frontend/tsconfig.tsbuildinfo"
expected = "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
if hashlib.sha256(protected.read_bytes()).hexdigest() != expected:
    raise RuntimeError("protected user file changed before checks")


def clock():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


environment = os.environ.copy()
environment.update({"APP_ENV": "test", "DATA_MODE": "fixture", "SOURCE_POLLING_ENABLED": "false", "ENRICHMENT_GENERATION_ENABLED": "false", "PYTHONIOENCODING": "utf-8", "PYTHONPATH": os.pathsep.join([str(ROOT / "backend/.venv/Lib/site-packages"), str(ROOT / "sdk/python"), str(ROOT / "backend/src")])})
for name in ("DATABASE_URL", "REDIS_URL", "GENERATION_API_KEY", "REVALIDATION_CURSOR_SIGNING_KEY", "FOFA_API_KEY", "HUNTER_API_KEY", "QUAKE_API_KEY", "ZOOMEYE_API_KEY"):
    environment.pop(name, None)
checks = [
    ("frontend_batch10_unit", ROOT / "frontend", [NODE, "node_modules/vitest/vitest.mjs", "run", "--maxWorkers=1", "--reporter=default", "--reporter=junit", "--outputFile.junit=" + str(RUN / "frontend_batch10_unit.xml")]),
    ("frontend_batch10_typecheck", ROOT / "frontend", [NODE, "node_modules/typescript/bin/tsc", "--noEmit", "--incremental", "false"]),
    ("frontend_batch10_lint", ROOT / "frontend", [NODE, "node_modules/eslint/bin/eslint.js", "."]),
    ("frontend_batch10_build", ROOT / "frontend", [NODE, "node_modules/vite/bin/vite.js", "build", "--outDir", "D:/dianzi-runtime-cache/root-investigation-ui-batch10-20261016"]),
    ("sdk_batch10_unit", ROOT / "sdk/python", [str(PYTHON), "-m", "pytest", "tests", "-q", "--junitxml=" + str(RUN / "sdk_batch10_unit.xml")]),
]
receipts = []
for label, directory, command in checks:
    receipt = {"started_at": clock(), "command": command, "cwd": str(directory), "baseline_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "mode": "offline fixtures only; no browser/PG/Redis/model/source live", "timeout_seconds": 180}
    with (RUN / (label + ".log")).open("wb") as output:
        try:
            result = subprocess.run(command, cwd=directory, env=environment, stdout=output, stderr=subprocess.STDOUT, timeout=180)
            receipt.update({"exit_code": result.returncode, "timed_out": False})
        except subprocess.TimeoutExpired:
            receipt.update({"exit_code": None, "timed_out": True})
    receipt["ended_at"] = clock()
    receipt["user_buildinfo_unchanged"] = hashlib.sha256(protected.read_bytes()).hexdigest() == expected
    receipts.append(receipt)
    (RUN / (label + ".json")).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"label": label, "exit_code": receipt["exit_code"], "timed_out": receipt["timed_out"], "user_buildinfo_unchanged": receipt["user_buildinfo_unchanged"]}), flush=True)
    if not receipt["user_buildinfo_unchanged"]:
        raise RuntimeError("protected user file changed during check")
(RUN / "frontend_sdk_batch10_check_receipts.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8", newline="\n")
raise SystemExit(0 if all(receipt["exit_code"] == 0 for receipt in receipts) else 1)
