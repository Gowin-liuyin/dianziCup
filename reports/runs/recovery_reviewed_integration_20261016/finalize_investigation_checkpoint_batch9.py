"""Finalize the stopped explicit checkpoint after preserving three exact raw evidence paths."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent


def clock():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


started = clock()
prior = json.loads((RUN / "investigation_batch9_checkpoint_receipt.json").read_text())
allowed = set(prior["explicit_paths"]) | {
    ".gitattributes",
    "reports/runs/recovery_reviewed_integration_20261016/resume_investigation_checkpoint_batch9.py",
    "reports/runs/recovery_reviewed_integration_20261016/investigation_batch9_checkpoint_receipt.json",
    "reports/runs/recovery_reviewed_integration_20261016/investigation_batch9_staged_boundary.log",
    "reports/runs/recovery_reviewed_integration_20261016/investigation_batch9_staged_diff_check.log",
    "reports/runs/recovery_reviewed_integration_20261016/finalize_investigation_checkpoint_batch9.py",
}
staged = set(subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"], cwd=ROOT).decode().split("\0")) - {""}
if not staged <= allowed:
    raise RuntimeError("unknown staged ownership")
if hashlib.sha256((ROOT / "frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest() != "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d":
    raise RuntimeError("protected user file changed")
records = []
arguments_by_label = [
    ("add", ["git", "add", "--", ".gitattributes", "reports/tasks/R14.md", "reports/runs/recovery_reviewed_integration_20261016/finalize_investigation_checkpoint_batch9.py"]),
    ("raw", ["git", "add", "--renormalize", "--", "reports/runs/recovery_reviewed_integration_20261016/investigation_batch9_staged_diff_check.log"]),
    ("guard", [str(ROOT / "backend/.venv/Scripts/python.exe"), "-I", str(RUN / "check_staged_boundary.py")]),
    ("diff", ["git", "diff", "--cached", "--check"]),
    ("commit", ["git", "commit", "-m", "checkpoint G-D: mount durable investigations and recovery dispatch; partial validation"]),
]
try:
    for label, arguments in arguments_by_label:
        begin = clock()
        result = subprocess.run(arguments, cwd=ROOT, capture_output=True, timeout=120)
        (RUN / ("investigation_batch9_final_" + label + ".log")).write_bytes(result.stdout + result.stderr)
        records.append({"started_at": begin, "ended_at": clock(), "cwd": str(ROOT), "command": arguments, "exit_code": result.returncode})
        print(json.dumps({"label": label, "exit_code": result.returncode}), flush=True)
        if result.returncode:
            raise RuntimeError("checkpoint blocked: " + label)
finally:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    (RUN / "investigation_batch9_checkpoint_final_receipt.json").write_text(json.dumps({"started_at": started, "ended_at": clock(), "head_sha": head, "commands": records, "push": "not_run", "stage_accepted": False}, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"head_sha": head, "stage_accepted": False}), flush=True)
