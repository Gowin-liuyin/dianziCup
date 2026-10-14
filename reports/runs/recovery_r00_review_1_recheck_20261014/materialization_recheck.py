"""Verify byte preservation after Git materializes the already-approved frozen paths."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from recheck_commands import run, REVIEW, OUTPUT, LINUX, SHA

relative_paths = ("contracts/requirements.json", "contracts/task_manifest.json", "fixtures/synthetic/pilot_cases.json")
before = {relative: hashlib.sha256((REVIEW / relative).read_bytes()).hexdigest() for relative in relative_paths}
expected_old_fixture = "1907ff5308b9d6fbf143e173e2ac7df50f1dcf5622a23c3d9fab4a39c5120228"
if before[relative_paths[2]] != expected_old_fixture:
    raise ValueError("Unexpected fixture changes; refusing to overwrite")
if subprocess.check_output(["git", "status", "--short"], cwd=REVIEW).strip():
    raise ValueError("Unexpected checkout changes; refusing to overwrite")
if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REVIEW).decode().strip() != SHA:
    raise ValueError("Wrong frozen SHA")
run("rehydrate_frozen_fixture", ["git", "restore", "--source", SHA, "--worktree", "--", relative_paths[2]])
run("baseline_windows_after_materialization", ["python", "scripts/verify_plan.py", "--baseline", "contracts/baselines/plan_baseline_recovery_r00.json"])
run("baseline_wsl_after_materialization", ["wsl", "--cd", LINUX, "--exec", "python3", "scripts/verify_plan.py", "--baseline", "contracts/baselines/plan_baseline_recovery_r00.json"])
run("wsl_hashes_after_materialization", ["wsl", "--exec", "sha256sum"] + [LINUX + "/" + relative for relative in relative_paths])
fresh = OUTPUT / "fresh_frozen_files"
fresh.mkdir(parents=True, exist_ok=True)
run("fresh_checkout_index", ["git", "-c", "core.autocrlf=true", "checkout-index", "--prefix=" + fresh.as_posix() + "/", "--", ".gitattributes", *relative_paths])
run("git_status_final", ["git", "status", "--short"])
baseline = json.loads((REVIEW / "contracts/baselines/plan_baseline_recovery_r00.json").read_text(encoding="utf-8"))
record = {"candidate": SHA, "before": before, "paths": []}
for relative in relative_paths:
    blob = subprocess.check_output(["git", "show", SHA + ":" + relative], cwd=REVIEW)
    actual = (REVIEW / relative).read_bytes()
    fresh_bytes = (fresh / relative).read_bytes()
    record["paths"].append({"path": relative, "baseline": baseline["source_hashes"][relative], "git_blob": hashlib.sha256(blob).hexdigest(),
                             "review_after": hashlib.sha256(actual).hexdigest(), "fresh_checkout": hashlib.sha256(fresh_bytes).hexdigest(),
                             "after_equals_blob": actual == blob, "fresh_equals_blob": fresh_bytes == blob})
(OUTPUT / "materialization_integrity.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record, indent=2))
