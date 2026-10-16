"""Verify the integrated workbench without modifying the user's incremental build cache."""

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
FRONTEND = ROOT / "frontend"
NODE = Path("C:/Program Files/nodejs/node.exe")
PROTECTED = FRONTEND / "tsconfig.tsbuildinfo"
BEFORE = hashlib.sha256(PROTECTED.read_bytes()).hexdigest()
if BEFORE != "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d":
    raise RuntimeError("protected user cache changed before validation")


def clock():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


commands = [
    ("assessment_frontend_batch8_unit", [str(NODE), "node_modules/vitest/vitest.mjs", "run", "--reporter=default", "--reporter=junit", "--outputFile=" + str(RUN / "assessment_frontend_batch8_unit.xml")]),
    ("assessment_frontend_batch8_typecheck", [str(NODE), "node_modules/typescript/bin/tsc", "--noEmit", "--incremental", "false"]),
    ("assessment_frontend_batch8_lint", [str(NODE), "node_modules/eslint/bin/eslint.js", "."]),
    ("assessment_frontend_batch8_build", [str(NODE), "node_modules/vite/bin/vite.js", "build", "--outDir", "D:/dianzi-runtime-cache/root-assessment-ui-batch8-20261016", "--emptyOutDir"]),
]
receipts = []
for label, command in commands:
    receipt = {"label": label, "started_at": clock(), "command": command, "cwd": str(FRONTEND), "mode": "offline UI/contract fixture, not browser live", "timeout_seconds": 180}
    path = RUN / (label + ".json")
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    with (RUN / (label + ".log")).open("wb") as output:
        process = subprocess.Popen(command, cwd=FRONTEND, env=os.environ.copy(), stdout=output, stderr=subprocess.STDOUT)
        receipt["owned_pid"] = process.pid
        timed_out = False
        try:
            process.wait(timeout=180)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            process.wait(timeout=10)
    receipt.update({"ended_at": clock(), "exit_code": process.returncode, "timed_out": timed_out, "log": label + ".log"})
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    receipts.append(receipt)
    print(json.dumps({"label": label, "exit_code": process.returncode, "timed_out": timed_out}), flush=True)
    if hashlib.sha256(PROTECTED.read_bytes()).hexdigest() != BEFORE:
        raise RuntimeError("protected user cache changed during validation")
(RUN / "assessment_frontend_batch8_receipts.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8", newline="\n")
raise SystemExit(0 if all(record["exit_code"] == 0 for record in receipts) else 1)
