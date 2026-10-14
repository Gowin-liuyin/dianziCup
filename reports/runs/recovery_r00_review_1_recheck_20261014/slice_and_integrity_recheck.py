"""Recheck capability acceptance on explicit synthetic copies and immutable hashes."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from recheck_commands import run, REVIEW, OUTPUT, SHA

sys.path.insert(0, str(REVIEW / "tests/plan"))
from test_verify_plan import copy_plan_root

root = copy_plan_root(OUTPUT / "synthetic_slice_positive")
manifest = json.loads((root / "contracts/task_manifest.json").read_text(encoding="utf-8"))
state = json.loads((root / "progress/task_state.json").read_text(encoding="utf-8"))
reference = "reports/reviews/synthetic_independent_slice.md"
(root / reference).write_text("Explicit synthetic structural review only. No product or live verification.\n", encoding="utf-8")
manifest["recovery"]["authority"].update(status="accepted", review_ref=reference)
for task in state["tasks"].values():
    task["status"] = "pending"
for package in ("R00", "R01", "R02"):
    state["recovery_tasks"][package].update(status="accepted", implementation="complete", evidence=[reference], review_ref=reference)
    state["recovery_tasks"][package]["verification"] = dict.fromkeys(state["recovery_tasks"][package]["verification"], "passed")
    for slice_id in manifest["recovery"]["work_packages"][package]["output_slices"]:
        task_id = manifest["recovery"]["capability_slices"][slice_id]["original_task"]
        state["tasks"][task_id]["slice_acceptance"][slice_id].update(status="accepted", evidence=[reference], review_ref=reference)


def write_state(document: dict) -> None:
    (root / "progress/task_state.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


(root / "contracts/task_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
write_state(state)
run("needed_slice_positive", ["python", str(REVIEW / "scripts/verify_plan.py"), "--root", str(root)])
missing_evidence = copy.deepcopy(state)
missing_evidence["tasks"]["T06"]["slice_acceptance"]["R01:T06"].update(evidence=[], review_ref=None)
write_state(missing_evidence)
run("accepted_slice_missing_evidence", ["python", str(REVIEW / "scripts/verify_plan.py"), "--root", str(root)])
write_state(state)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


frozen = json.loads((REVIEW / "contracts/baselines/plan_baseline_recovery_r00.json").read_text(encoding="utf-8"))
hashes = []
for relative, expected in frozen["source_hashes"].items():
    blob = subprocess.check_output(["git", "show", SHA + ":" + relative], cwd=REVIEW)
    actual = (REVIEW / relative).read_bytes()
    prior_blob = subprocess.check_output(["git", "show", "d752fe0c8f14dd4c35b39863cfba0d1c902fffae:" + relative], cwd=REVIEW)
    hashes.append({"path": relative, "baseline": expected, "git_blob": digest(blob), "windows_bytes": digest(actual),
                   "byte_equal_blob": actual == blob, "hash_matches": digest(actual) == expected,
                   "semantic_equal_prior": json.loads(blob) == json.loads(prior_blob)})
preserved = []
for relative in ["docs/decisions/CR-R%02d.md" % number for number in range(1, 10)] + [
    "progress/task_state.json", "contracts/baselines/plan_baseline_recovery_r00.json", "contracts/baselines/plan_baseline_t01.json",
    "contracts/schemas/public_api_v2.json", "contracts/schemas/public_api_v2_examples.json",
    "progress/history/task_state_pre_recovery_8e265dc.json.txt", "reports/runs/plan_audit_20261014/nvd-response.json"]:
    prior = subprocess.check_output(["git", "show", "d752fe0c8f14dd4c35b39863cfba0d1c902fffae:" + relative], cwd=REVIEW)
    current = subprocess.check_output(["git", "show", SHA + ":" + relative], cwd=REVIEW)
    preserved.append({"path": relative, "unchanged_git_bytes": prior == current})
indexed = {str(path.relative_to(REVIEW)).replace("\\", "/"): digest(path.read_bytes())
           for directory in ("scripts", "backend/src") for path in (REVIEW / directory).rglob("*.py")}
record = {"candidate": SHA, "tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=REVIEW).decode().strip(),
          "frozen_source_hashes": hashes, "unchanged_inputs": preserved,
          "positive_whole_t06_status": state["tasks"]["T06"]["status"],
          "positive_r20_t06_status": state["tasks"]["T06"]["slice_acceptance"]["R20:T06"]["status"],
          "indexed_source_hashes": indexed}
(OUTPUT / "recheck_integrity.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: value for key, value in record.items() if key != "indexed_source_hashes"}, ensure_ascii=False, indent=2))
