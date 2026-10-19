"""Recheck frozen author/reviewer raw evidence and the original author's two Git-bound controls."""

import hashlib
import json
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
before = json.loads((RUN / "prior_evidence_before.json").read_text())
for package in before:
    directory = Path(package["root"])
    for member in package["members"]:
        raw = (directory / member["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != member["sha256"] or len(raw) != member["bytes"]:
            raise RuntimeError("original raw member drift")
author = Path(before[0]["root"])
controls = []
for relative in ("reports/runs/recovery_r17_sbom_workbench_20261016/raw_manifest.json", "reports/runs/recovery_r17_sbom_workbench_20261016/raw_manifest.sha256"):
    frozen = subprocess.check_output(["git", "show", "7a653880af12e4160ca8edf26fccbaf5d1e6f0f0:" + relative], cwd=ROOT)
    raw = (author / relative).read_bytes()
    if frozen != raw:
        raise RuntimeError("author original control drift")
    controls.append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest(), "raw_equals_frozen_git": True})
for package in before:
    directory = Path(package["root"])
    relative = "reports/runs/" + ("recovery_r17_sbom_workbench_20261016" if directory == author else "recovery_r17_sbom_workbench_review1_20261016") + "/raw_manifest.json"
    if hashlib.sha256((directory / relative).read_bytes()).hexdigest() != package["manifest_sha256"]:
        raise RuntimeError("original canonical manifest drift")
report = {"checked_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"), "original_author_120_files": "passed (118 member byte checks + 2 frozen Git controls)", "original_reviewer_272_members": "passed", "original_raw_mismatches": 0, "author_controls": controls, "review_control_sha_before_not_separately_recorded": True}
(RUN / "prior_evidence_after.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(report))
