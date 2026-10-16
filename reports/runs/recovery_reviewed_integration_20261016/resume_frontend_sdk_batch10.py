"""Preserve CRLF command output while correcting only its exact Git whitespace attributes."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
initial = json.loads((RUN / "frontend_sdk_batch10_checkpoint_receipt.json").read_text())
expected_paths = set(initial["paths"])
staged = set(subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"], cwd=ROOT).decode().split("\0")) - {""}
if staged != expected_paths:
    raise RuntimeError("unexpected staged change; refusing to resume")
attributes_path = ROOT / ".gitattributes"
lines = attributes_path.read_text(encoding="utf-8").splitlines()
raw_paths = {relative for relative in expected_paths if relative.startswith(RUN.relative_to(ROOT).as_posix() + "/") and Path(relative).suffix in {".log", ".xml"}}
updated = []
for line in lines:
    relative = line.removesuffix(" -text")
    if relative in raw_paths:
        line = relative + " -text whitespace=trailing-space,space-before-tab,cr-at-eol"
    updated.append(line)
extras = ["resume_frontend_sdk_batch10.py", "frontend_sdk_batch10_checkpoint_receipt.json", "frontend_sdk_batch10_checkpoint_add.log", "frontend_sdk_batch10_checkpoint_boundary.log", "frontend_sdk_batch10_checkpoint_diff.log"]
for name in extras:
    if name.endswith(".log"):
        updated.append((RUN / name).relative_to(ROOT).as_posix() + " -text whitespace=trailing-space,space-before-tab,cr-at-eol")
attributes_path.write_text("\n".join(updated) + "\n", encoding="utf-8", newline="\n")
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
receipts = []
paths = [".gitattributes", *((RUN / name).relative_to(ROOT).as_posix() for name in extras)]
for label, command in [
    ("add", ["git", "add", "--", *paths]),
    ("boundary", [str(ROOT / "backend/.venv/Scripts/python.exe"), "-I", str(RUN / "check_staged_boundary.py")]),
    ("diff", ["git", "diff", "--cached", "--check"]),
    ("commit", ["git", "commit", "-m", "checkpoint G-E: mount revision-bound investigations and six-tool SDK; default review pending"]),
]:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=120)
    (RUN / ("frontend_sdk_batch10_resumed_" + label + ".log")).write_bytes(result.stdout + result.stderr)
    receipts.append({"label": label, "command": command, "exit_code": result.returncode})
    if result.returncode:
        raise RuntimeError("resume stopped before next step: " + label)
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
(RUN / "frontend_sdk_batch10_resumed_receipt.json").write_text(json.dumps({"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "head_sha": head, "commands": receipts, "correction": "exact generated raw CRLF logs/XML use cr-at-eol; actual non-CR trailing whitespace count is zero; bytes unchanged; initial diff exit2 preserved", "stage_accepted": False, "push": "not_run", "user_file_sha256": hashlib.sha256((ROOT / "frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest()}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"head_sha": head, "stage_accepted": False, "push": "not_run"}))
