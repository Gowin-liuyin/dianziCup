"""Run one fixed local UI repair check and preserve its actual byte output."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

WORKSPACE = Path(__file__).resolve().parents[3]
RUN_DIRECTORY = Path(__file__).resolve().parent
FRONTEND = WORKSPACE / "frontend"
sys.stdout.reconfigure(encoding="utf-8")
CHECKS = {
    "events-tests": ["npm.cmd", "run", "test", "--", "--run", "src/features/events/event-detail-view.test.tsx", "src/features/events/event-workspace.test.tsx", "--maxWorkers=1", "--no-file-parallelism", "--reporter=json", f"--outputFile={RUN_DIRECTORY / 'events-tests.json'}"],
    "typecheck": ["npm.cmd", "run", "typecheck"],
    "lint": ["npm.cmd", "run", "lint"],
    "build": ["npm.cmd", "run", "build"],
    "browser-probes": ["node", "node_modules/@playwright/test/cli.js", "test", "--config", str(RUN_DIRECTORY / "browser-probes.config.mjs")],
    "browser": ["node", "node_modules/@playwright/test/cli.js", "test", "--config", str(RUN_DIRECTORY / "browser.config.mjs")],
}
label = sys.argv[1]
output_label = sys.argv[2] if len(sys.argv) > 2 else label
source_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=WORKSPACE, check=True, capture_output=True, text=True).stdout.strip()
start = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
environment = dict(os.environ)
if label.startswith("browser"):
    environment["PLAYWRIGHT_BROWSERS_PATH"] = "C:/Users/yinha/.codex/cache/dianzi/r01_playwright_1248"
result = subprocess.run(CHECKS[label], cwd=FRONTEND, env=environment, capture_output=True, check=False)
end = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
(RUN_DIRECTORY / f"{output_label}.stdout.log").write_bytes(result.stdout)
(RUN_DIRECTORY / f"{output_label}.stderr.log").write_bytes(result.stderr)
receipt = {"label": output_label, "command": CHECKS[label], "cwd": str(FRONTEND), "source_commit": source_commit, "start": start, "end": end, "exit_code": result.returncode}
(RUN_DIRECTORY / f"{output_label}.command.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
with (RUN_DIRECTORY / "commands.jsonl").open("a", encoding="utf-8") as output:
    output.write(json.dumps(receipt, ensure_ascii=False) + "\n")
print(json.dumps(receipt, ensure_ascii=False))
print(result.stdout.decode("utf-8", errors="replace")[-1800:])
print(result.stderr.decode("utf-8", errors="replace")[-700:])
sys.exit(result.returncode)
