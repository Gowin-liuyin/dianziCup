"""Integrate the complete independently reviewed fan-in without touching shared defaults."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
SOURCE = "ccbdf7ebb88e0245e72bcb0f52984e08739fe473"
BASE = "9726363e0d9b33467ba40a06a8bde9548b46bccf"
paths = subprocess.check_output(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", SOURCE], cwd=ROOT, text=True).splitlines()
allowed = {
    "backend/src/ai_intel/revalidation/execution_contracts.py",
    "backend/src/ai_intel/revalidation/fan_in.py",
    "backend/src/ai_intel/revalidation/runtime_policy.py",
    "backend/src/ai_intel/revalidation/verified_content.py",
    "backend/tests/contract/test_r16_fan_in_contracts.py",
    "backend/tests/integration/test_r16_fan_in_pg.py",
    "backend/tests/integration/test_r16_revalidation_runtime_pg.py",
    "backend/tests/unit/test_r16_fan_in_outcomes.py",
    "backend/tests/unit/test_r16_fan_in_runtime.py",
    "backend/tests/unit/test_r16_verified_content.py",
    "backend/tests/unit/test_r16_runtime_drive.py",
}
if set(paths) != allowed:
    raise RuntimeError("unexpected frozen fan-in file scope")
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
files = []
for relative in paths:
    path = ROOT / relative
    prior = subprocess.run(["git", "show", BASE + ":" + relative], cwd=ROOT, capture_output=True)
    if prior.returncode == 0:
        if not path.exists() or path.read_bytes().replace(b"\r\n", b"\n") != prior.stdout.replace(b"\r\n", b"\n"):
            raise RuntimeError("existing local edit protected: " + relative)
    elif path.exists():
        raise RuntimeError("unknown local file protected: " + relative)
    payload = subprocess.check_output(["git", "show", SOURCE + ":" + relative], cwd=ROOT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    files.append({"path": relative, "source_sha": SOURCE, "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)})
(RUN / "fanin_batch13_inputs.json").write_text(json.dumps({"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "files": files, "new_default_validation": "not_run", "whole_task_accepted": False}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"files": len(files), "new_default_validation": "not_run"}))
