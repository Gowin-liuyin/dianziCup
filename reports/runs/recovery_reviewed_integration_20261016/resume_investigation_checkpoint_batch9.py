"""Resume only the known stopped checkpoint; preserve its first failed receipt and logs."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
initial = json.loads((RUN / "investigation_batch9_checkpoint_receipt.json").read_text())
allowed = set(initial["explicit_paths"])
allowed.update({
    ".gitattributes",
    "reports/runs/recovery_reviewed_integration_20261016/resume_investigation_checkpoint_batch9.py",
    "reports/runs/recovery_reviewed_integration_20261016/investigation_batch9_checkpoint_receipt.json",
    "reports/runs/recovery_reviewed_integration_20261016/investigation_batch9_staged_boundary.log",
    "reports/runs/recovery_reviewed_integration_20261016/investigation_batch9_staged_diff_check.log",
})
staged = set(subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"], cwd=ROOT).decode().split("\0")) - {""}
if not staged <= allowed:
    raise RuntimeError("unknown staged files; do not alter their ownership")
protected_hash = hashlib.sha256((ROOT / "frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest()
if protected_hash != "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d":
    raise RuntimeError("protected user file changed")
records = []
commands = [
    ("add", ["git", "add", "--", *sorted(allowed)]),
    ("raw_evidence", ["git", "add", "--renormalize", "--", "reports/runs/recovery_reviewed_integration_20261016/investigation_batch9_offline.log", "reports/runs/recovery_reviewed_integration_20261016/investigation_batch9_offline.xml"]),
    ("guard", [str(ROOT / "backend/.venv/Scripts/python.exe"), "-I", str(RUN / "check_staged_boundary.py")]),
    ("diff", ["git", "diff", "--cached", "--check"]),
    ("commit", ["git", "commit", "-m", "checkpoint G-D: mount durable investigations and recovery dispatch; partial validation"]),
]
try:
    for label, arguments in commands:
        begin = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
        result = subprocess.run(arguments, cwd=ROOT, capture_output=True, timeout=120)
        (RUN / ("investigation_batch9_resume_" + label + ".log")).write_bytes(result.stdout + result.stderr)
        records.append({"command": arguments, "cwd": str(ROOT), "started_at": begin, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "exit_code": result.returncode})
        print(json.dumps({"label": label, "exit_code": result.returncode}), flush=True)
        if result.returncode:
            raise RuntimeError("checkpoint remains blocked: " + label)
finally:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "head_sha": head, "commands": records, "initial_failure_retained": "investigation_batch9_checkpoint_receipt.json", "protected_user_file_sha256": protected_hash, "push": "not_run", "stage_accepted": False}
    (RUN / "investigation_batch9_checkpoint_resumed_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"head_sha": head, "stage_accepted": False}), flush=True)
