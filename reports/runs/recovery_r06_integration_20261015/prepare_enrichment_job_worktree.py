"""Prepare an isolated integration workspace without advancing the stage gate."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE = Path("D:/wt/r07-enrichment-jobs")
RUN = Path(__file__).parent
assert not WORKSPACE.exists()
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
steps = [
    (ROOT, ["git", "worktree", "add", "-b", "codex/r07-enrichment-jobs", str(WORKSPACE), "8a1b04d48346d8550f0326a77f003246a0ebbab5"]),
    (WORKSPACE, ["git", "merge", "--no-ff", "71e594cb958bd93d21fb7ed66574b3cba4cc47e1", "-m", "G-C develop enrichment jobs against frozen publication candidate; review pending"]),
    (WORKSPACE, ["git", "cherry-pick", "d8a3189bb7bc1cfde24825f5478920e37eac9556"]),
]
receipt = {"started_at": started, "workspace": str(WORKSPACE), "purpose": "root-only durable integration development; publication three Must still open; single dimension independent review pending", "accepted": False, "push_attempts": 0, "steps": []}
for index, (cwd, argv) in enumerate(steps):
    with (RUN / f"prepare_enrichment_jobs_{index}.log").open("xb") as output:
        result = subprocess.run(argv, cwd=cwd, stdout=output, stderr=subprocess.STDOUT, timeout=120)
    receipt["steps"].append({"cwd": str(cwd), "argv": argv, "exit_code": result.returncode})
    (RUN / "prepare_enrichment_job_worktree_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if result.returncode:
        raise SystemExit(result.returncode)
receipt["head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=WORKSPACE, text=True).strip()
receipt["ended_at"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
(RUN / "prepare_enrichment_job_worktree_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
