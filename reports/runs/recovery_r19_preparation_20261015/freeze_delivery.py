"""Bind this exact preparation code, report and local run evidence for independent review."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
ZONE = timezone(timedelta(hours=8))
CODE_SHA = "81b38d5559219d5818e6169da32cd7b98e33d392"
SOURCE_FILES = [
    "benchmarks/schemas/candidate_case_v1.json",
    "benchmarks/manifests/r19_public_dev_candidate_v1.json",
    "scripts/annotation/prepare.py",
    "scripts/annotation/tests/test_prepare.py",
    "docs/runbooks/annotation_preparation.md",
]
start = datetime.now(ZONE).isoformat(timespec="seconds")
head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
assert head == CODE_SHA
diff = subprocess.run(["git", "diff", "--check", CODE_SHA + "^", CODE_SHA], cwd=ROOT, capture_output=True, text=True, check=False)
(RUN / "frozen_diff_check.log").write_text(diff.stdout + diff.stderr, encoding="utf-8")
assert diff.returncode == 0
hashes = {}
for relative in SOURCE_FILES:
    blob = subprocess.run(["git", "show", CODE_SHA + ":" + relative], cwd=ROOT, capture_output=True, check=True).stdout
    hashes[relative] = {"git_blob_sha256": hashlib.sha256(blob).hexdigest(), "observed_file_sha256": hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()}
evidence_files = [ROOT / "reports/tasks/R19-preparation.md", *RUN.glob("*")]
evidence_hashes = {
    path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted(evidence_files)
    if path.is_file() and path.name != "delivery_manifest.json"
}
manifest = {
    "schema_version": 1, "task": "R19-preparation", "status": "awaiting_review",
    "implementation": "complete_for_preparation_slice", "whole_r19_implementation": "partial",
    "baseline_code_sha": "0a45185ae3ffb73a6d186b98421e26a52f78bfc6", "frozen_code_sha": CODE_SHA,
    "worktree": str(ROOT), "branch": "codex/r19-annotation-preparation", "frozen_at": datetime.now(ZONE).isoformat(timespec="seconds"),
    "code_file_hashes": hashes, "report_and_run_file_hashes": evidence_hashes,
    "observed_line_endings_note": "Git blob and checkout hashes recorded separately; autocrlf can change filesystem bytes in another checkout.",
    "verification": {"unit_contract_security_cli_integration": "passed", "frontend": "not_run", "e2e": "not_run", "live": "not_run", "manual": "not_run"},
    "test_results": {"annotation_tests": {"passed": 27, "failed": 0, "skipped": 0, "log": "final3_annotation_tests.log"}, "existing_plan_regression": {"passed": 47, "failed": 0, "skipped": 0, "log": "final2_plan_regression.log"}},
    "current_real_dataset": {"real_candidates": 1, "synthetic_candidates_in_public_manifest": 0, "human_labels": 0, "human_gold_labels": 0, "status": "awaiting_human_label", "split": "dev", "license": "unknown"},
    "formal_evaluation": {"status": "not_run", "numerator": None, "denominator": None},
    "independence": "R04 approved real original-document slice permits preparation; R07-R16 and independent dual human/adjudication/freeze remain required for final R19.",
    "scope_limits": ["No real holdout or answers accessed", "No actual human identity verification", "No DB/API/network/DPAPI/model calls", "No public contracts/locks/progress changes", "No push or accepted status"],
    "freeze_commands": [{"command": ["git", "diff", "--check", CODE_SHA + "^", CODE_SHA], "cwd": str(ROOT), "start": start, "end": datetime.now(ZONE).isoformat(timespec="seconds"), "exit_code": diff.returncode, "log": "frozen_diff_check.log"}],
}
with (RUN / "delivery_manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
    json.dump(manifest, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print("DELIVERY_FROZEN: preparation awaiting_review; 1 real candidate; 0 human gold")
