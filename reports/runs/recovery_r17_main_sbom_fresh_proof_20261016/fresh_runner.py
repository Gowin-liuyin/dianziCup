"""Record direct fresh-Git verification without a test resource adapter."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
label = sys.argv[1]
node = "C:/Program Files/nodejs/node.exe"
commands = {
    "install": ["C:/Program Files/nodejs/npm.cmd", "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
    "unit_main": [node, "node_modules/vitest/vitest.mjs", "run", "--reporter=json", "--outputFile=" + str(RUN / "unit_main_result.json")],
    "lint": [node, "node_modules/eslint/bin/eslint.js", "."],
    "typecheck": [node, "node_modules/typescript/bin/tsc", "--noEmit"],
    "build": ["C:/Program Files/nodejs/npm.cmd", "run", "build"],
}
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
result = subprocess.run(commands[label], cwd=ROOT / "frontend", capture_output=True)
(RUN / (label + ".log")).write_bytes(result.stdout + result.stderr)
receipt = {"argv": commands[label], "cwd": str(ROOT / "frontend"), "started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "exit_code": result.returncode, "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "resource_adapter": False, "main_buildinfo_sha256": hashlib.sha256(Path("D:/dianzi/frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest()}
(RUN / (label + "_command.json")).write_text(json.dumps(receipt, indent=2), encoding="utf8")
print(json.dumps(receipt), flush=True)
raise SystemExit(result.returncode)
