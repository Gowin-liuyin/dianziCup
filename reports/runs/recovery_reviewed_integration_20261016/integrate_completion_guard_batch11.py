"""Import the independently exercised final-transaction completion boundary."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
SOURCE = "968c71b6ed5e3991edd49bedfef765b36fdbda3d"
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
paths = subprocess.check_output(["git", "diff", "--name-only", "26fa0814a3a947a072f9d6fdf0e346814512c5d0", SOURCE, "--", "backend"], cwd=ROOT, text=True).splitlines()
if len(paths) != 3:
    raise RuntimeError("unexpected reviewed completion port closure")
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
pending = []
for relative in paths:
    target = ROOT / relative
    tracked = subprocess.run(["git", "show", head + ":" + relative], cwd=ROOT, capture_output=True)
    if target.exists() and (tracked.returncode or target.read_bytes().replace(b"\r\n", b"\n") != tracked.stdout.replace(b"\r\n", b"\n")):
        raise RuntimeError("existing working changes; refusing overwrite: " + relative)
    raw = subprocess.check_output(["git", "show", SOURCE + ":" + relative], cwd=ROOT)
    pending.append((target, raw, {"path": relative, "source_sha": SOURCE, "raw_sha256": hashlib.sha256(raw).hexdigest()}))
for target, raw, _ in pending:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
(RUN / "completion_guard_batch11_inputs.json").write_text(json.dumps({"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "baseline_sha": head, "review_sha": "e98f82f8dd3a40b1f617a77ab0a4457c66dfb849", "files": [record for _, _, record in pending], "scope": "158offline/27realPG qualified optional port; R16 consumer/default integration not_run", "whole_tasks_accepted": False}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"files": len(pending), "whole_tasks_accepted": False}))
