"""Capture bounded independent review commands without modifying the candidate."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

REVIEW = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r00-review\dianzi")
OUTPUT = Path(r"D:\dianzi\reports\runs\recovery_r00_review_1_20261014")
ZONE = timezone(timedelta(hours=8))


def run(name: str, argv: list[str], cwd: Path = REVIEW, seconds: int = 60) -> dict:
    """Save command output and exact exit status; timeout is a separate outcome."""
    start = datetime.now(ZONE).isoformat(timespec="seconds")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    try:
        result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=seconds)
        stdout, stderr, exit_code = result.stdout, result.stderr, result.returncode
        outcome = "completed"
    except subprocess.TimeoutExpired as error:
        stdout, stderr, exit_code = error.stdout or b"", error.stderr or b"", None
        outcome = "timeout"
    (OUTPUT / f"{name}.stdout.log").write_bytes(stdout)
    (OUTPUT / f"{name}.stderr.log").write_bytes(stderr)
    record = {"name": name, "argv": argv, "cwd": str(cwd), "started_at": start,
              "finished_at": datetime.now(ZONE).isoformat(timespec="seconds"),
              "exit_code": exit_code, "outcome": outcome,
              "stdout": f"{name}.stdout.log", "stderr": f"{name}.stderr.log"}
    (OUTPUT / f"{name}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False))
    return record


if __name__ == "__main__":
    run("plan_tests", ["python", "-m", "unittest", "discover", "-s", "tests/plan", "-v"])
    run("plan_baseline", ["python", "scripts/verify_plan.py", "--baseline", "contracts/baselines/plan_baseline_recovery_r00.json"])
    run("git_candidate", ["git", "rev-parse", "HEAD", "HEAD^{tree}"])
    run("git_diff_check", ["git", "diff", "--check", "b8199ce5dd0a7920ce5770e4f580fe23e0fe9f6b", "d752fe0c8f14dd4c35b39863cfba0d1c902fffae"])
    run("cbm_version", ["wsl", "--exec", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "--version"])
    run("cbm_help", ["wsl", "--exec", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "index_repository", "--help"])
