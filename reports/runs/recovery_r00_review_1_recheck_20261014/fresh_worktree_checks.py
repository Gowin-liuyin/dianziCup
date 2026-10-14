"""Verify the immutable candidate in a newly created managed worktree."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from recheck_commands import run, REVIEW, OUTPUT, SHA

FRESH = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r00-recheck-clean\dianzi")
LINUX_FRESH = "/mnt/c/Users/yinha/.codex/worktrees/recovery-r00-recheck-clean/dianzi"
if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=FRESH).decode().strip() != SHA:
    raise ValueError("Wrong fresh candidate")
run("fresh_git_sha", ["git", "rev-parse", "HEAD", "HEAD^{tree}"], FRESH)
run("fresh_git_status", ["git", "status", "--short"], FRESH)
run("fresh_git_autocrlf", ["git", "config", "--get", "core.autocrlf"], FRESH)
run("fresh_baseline_windows", ["python", "scripts/verify_plan.py", "--baseline", "contracts/baselines/plan_baseline_recovery_r00.json"], FRESH)
run("fresh_baseline_wsl", ["wsl", "--cd", LINUX_FRESH, "--exec", "python3", "scripts/verify_plan.py", "--baseline", "contracts/baselines/plan_baseline_recovery_r00.json"], FRESH)
baseline = json.loads((FRESH / "contracts/baselines/plan_baseline_recovery_r00.json").read_text(encoding="utf-8"))
run("fresh_wsl_source_hashes", ["wsl", "--exec", "sha256sum"] + [LINUX_FRESH + "/" + relative for relative in baseline["source_hashes"]], FRESH)
record = {"candidate": SHA, "fresh_worktree": str(FRESH), "source_hashes": [], "review_source_equal_fresh": True}
for relative, expected in baseline["source_hashes"].items():
    actual = (FRESH / relative).read_bytes()
    blob = subprocess.check_output(["git", "show", SHA + ":" + relative], cwd=FRESH)
    record["source_hashes"].append({"path": relative, "baseline": expected, "fresh_windows": hashlib.sha256(actual).hexdigest(),
                                   "git_blob": hashlib.sha256(blob).hexdigest(), "byte_equal_blob": actual == blob})
for directory in ("scripts", "backend/src"):
    for path in (FRESH / directory).rglob("*.py"):
        relative = path.relative_to(FRESH)
        if path.read_bytes() != (REVIEW / relative).read_bytes():
            record["review_source_equal_fresh"] = False
            raise ValueError("Changed indexed source")
(OUTPUT / "fresh_integrity.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record, indent=2))
