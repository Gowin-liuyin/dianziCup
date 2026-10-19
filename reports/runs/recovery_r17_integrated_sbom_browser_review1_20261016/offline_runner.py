"""Record independent commands without changing product source or assertions."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]

def execute(label, argv, cwd):
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    result = subprocess.run(argv, cwd=cwd, capture_output=True)
    (RUN / (label + ".log")).write_bytes(result.stdout + result.stderr)
    receipt = {"argv": argv, "cwd": str(cwd), "started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "exit_code": result.returncode, "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "main_buildinfo_sha256": hashlib.sha256(Path("D:/dianzi/frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest()}
    (RUN / (label + "_command.json")).write_text(json.dumps(receipt, indent=2), encoding="utf8")
    print(json.dumps(receipt), flush=True)
    return result.returncode

if __name__ == "__main__":
    label = sys.argv[1]
    node = "C:/Program Files/nodejs/node.exe"
    commands = {
        "unit_fresh": [node, "node_modules/vitest/vitest.mjs", "run", "--reporter=json", "--outputFile=" + str(RUN / "unit_fresh_result.json")],
        "unit_adapter": [node, "node_modules/vitest/vitest.mjs", "run", "--reporter=json", "--outputFile=" + str(RUN / "unit_adapter_result.json")],
        "lint": [node, "node_modules/eslint/bin/eslint.js", "."],
        "typecheck": [node, "node_modules/typescript/bin/tsc", "--noEmit"],
        "build": ["C:/Program Files/nodejs/npm.cmd", "run", "build"],
    }
    raise SystemExit(execute(label, commands[label], ROOT / "frontend"))
