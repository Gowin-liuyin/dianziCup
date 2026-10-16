"""Freeze explicit compatibility decisions without including working implementation edits."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
paths = ["docs/decisions/CR-R14_shared_read_consumers.md", "docs/decisions/CR-R06_source_data_mode_persistence.md"]
if subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT).strip():
    raise RuntimeError("unrelated staged work must remain untouched")
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
checks = [
    ("add", ["git", "add", "--", *paths]),
    ("boundary", [str(ROOT / "backend/.venv/Scripts/python.exe"), "-I", str(RUN / "check_staged_boundary.py")]),
    ("diff", ["git", "diff", "--cached", "--check"]),
    ("commit", ["git", "commit", "-m", "checkpoint R14/R06: freeze shared-read and immutable source-mode contracts"]),
]
receipts = []
for label, command in checks:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=120)
    (RUN / ("internal_contracts_batch10_" + label + ".log")).write_bytes(result.stdout + result.stderr)
    receipts.append({"command": command, "exit_code": result.returncode})
    if result.returncode:
        raise RuntimeError("contract checkpoint stopped before next step: " + label)
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
(RUN / "internal_contracts_batch10_receipt.json").write_text(json.dumps({"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "explicit_paths": paths, "commit_sha": head, "commands": receipts, "product_stage": "not_accepted", "push": "not_run"}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"commit_sha": head, "product_stage": "not_accepted", "push": "not_run"}))
