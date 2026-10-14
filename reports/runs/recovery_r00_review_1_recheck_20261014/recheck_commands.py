"""Capture the frozen R00 repair review without changing product files."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, r"D:\dianzi\reports\runs\recovery_r00_review_1_20261014")
import run_commands as runner

OUTPUT = Path(r"D:\dianzi\reports\runs\recovery_r00_review_1_recheck_20261014")
OUTPUT.mkdir(parents=True, exist_ok=True)
runner.OUTPUT = OUTPUT
run = runner.run
REVIEW = runner.REVIEW
LINUX = "/mnt/c/Users/yinha/.codex/worktrees/recovery-r00-review/dianzi"
SHA = "15d0272bd2a9e25d19397d8147e9c3cbe6016f9b"


if __name__ == "__main__":
    run("git_frozen", ["git", "rev-parse", "HEAD", "HEAD^{tree}"])
    run("git_status_start", ["git", "status", "--short"])
    run("plan_tests", ["python", "-m", "unittest", "discover", "-s", "tests/plan", "-v"])
    run("baseline_windows", ["python", "scripts/verify_plan.py", "--baseline", "contracts/baselines/plan_baseline_recovery_r00.json"])
    run("baseline_wsl", ["wsl", "--cd", LINUX, "--exec", "python3", "scripts/verify_plan.py", "--baseline", "contracts/baselines/plan_baseline_recovery_r00.json"])
    run("all_pending_negative", ["python", "scripts/verify_plan.py", "--root", r"D:\dianzi\reports\runs\recovery_r00_review_1_20261014\temporary_copies\accepted_r02_missing_slices"])
    uv = [r"C:\Users\yinha\.local\bin\uv.exe", "run", "--locked", "--offline", "--no-sync"]
    paths = [str(REVIEW / "scripts/verify_plan.py"), str(REVIEW / "tests/plan")]
    run("ruff", uv + ["ruff", "check"] + paths, Path(r"D:\dianzi\backend"))
    run("format", uv + ["ruff", "format", "--check"] + paths, Path(r"D:\dianzi\backend"))
    run("mypy", uv + ["mypy", "--follow-imports=skip", str(REVIEW / "scripts/verify_plan.py")], Path(r"D:\dianzi\backend"))
    run("git_diff_check", ["git", "diff", "--check", "d752fe0c8f14dd4c35b39863cfba0d1c902fffae", SHA, "--", ".gitattributes", "contracts", "scripts", "tests/plan", "docs", "progress"])
    run("git_status_end", ["git", "status", "--short"])
    print(json.dumps({"run_directory": str(OUTPUT), "candidate": SHA}))
