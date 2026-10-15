"""Bind staged canonical report/run blobs and fixed code for a new independent recheck."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
CODE_SHA = "22d809f7803d539a2b551eb878ceae5333182d83"
ZONE = timezone(timedelta(hours=8))
assert subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip() == CODE_SHA
sources = [
    "scripts/annotation/prepare.py", "scripts/annotation/tests/test_prepare.py",
    "scripts/annotation/tests/test_prepare_fix1.py", "docs/runbooks/annotation_preparation.md",
    "benchmarks/schemas/candidate_case_v1.json", "benchmarks/manifests/r19_public_dev_candidate_v1.json",
]
code_hashes = {
    path: hashlib.sha256(subprocess.run(["git", "show", CODE_SHA + ":" + path], cwd=ROOT, capture_output=True, check=True).stdout).hexdigest()
    for path in sources
}
paths = [ROOT / "reports/tasks/R19-preparation-fix1.md", *RUN.glob("*")]
evidence_hashes = {}
for path in sorted(paths):
    if not path.is_file() or path.name == "delivery_manifest.json":
        continue
    relative = path.relative_to(ROOT).as_posix()
    blob = subprocess.run(["git", "show", ":" + relative], cwd=ROOT, capture_output=True, check=True).stdout
    evidence_hashes[relative] = {"canonical_git_blob_sha256": hashlib.sha256(blob).hexdigest(), "observed_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
review_run = Path("D:/wt/r19-preparation-review-1/reports/runs/recovery_r19_preparation_review_1_20261015")
fixture_root = Path("C:/Users/yinha/AppData/Local/Temp/r19-review-only-synthetic-9d7uhd1i")
review_paths = [
    review_run / "probe_cli_boundaries.py", review_run / "boundary_probes.json", review_run / "followup_probes.json",
    Path("D:/wt/r19-preparation-review-1/reports/reviews/recovery/G-C-R19-preparation-review-1.md"),
    *(fixture_root / name for name in ["base_synthetic.json", "alias_refers_other_family_cross_split.json", "claimed_humans_are_synthetic_only.json", "orphan_adjudication.json", "orphan_duplicate_adjudications.json", "orphan_export.json"]),
]
before = json.loads((RUN / "before_review_reproduction.json").read_text(encoding="utf-8"))
after = json.loads((RUN / "after_review_reproduction.json").read_text(encoding="utf-8"))
assert len(before["records"]) == len(after["records"]) == 7
assert all(record["exit_code"] == 0 for record in before["records"])
assert all(record["exit_code"] == 2 for record in after["records"])
manifest = {
    "schema_version": 1, "task": "R19-preparation-fix1", "status": "awaiting_review",
    "original_reviewed_tip": "a0c76800202a9869c4e24918b84893ebcec52a61", "frozen_code_sha": CODE_SHA,
    "frozen_at": datetime.now(ZONE).isoformat(timespec="seconds"), "worktree": str(ROOT),
    "canonical_code_file_sha256": code_hashes, "report_and_run_hashes": evidence_hashes,
    "reviewer_public_synthetic_input_hashes": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in review_paths},
    "original_reports_and_materials": "Preserved without edits; old report remains bound to its old code and original independent Must fix verdict.",
    "regression_results": {"annotation_tests": {"passed": 40, "failed": 0, "skipped": 0, "original": 27, "new": 13}, "plan_tests": {"passed": 47, "failed": 0, "skipped": 0}, "review_replay": {"before_exit_0": 7, "after_exit_2": 7}},
    "verification": {"unit_contract_security_cli_integration": "passed_for_slice", "frontend": "not_run", "e2e": "not_run", "live": "not_run", "manual": "not_run"},
    "real_candidates": 1, "real_human_labels": 0, "human_gold_count": 0, "formal_evaluation": {"status": "not_run", "numerator": None, "denominator": None},
    "identity_guard_limit": "Exact family/alias/document/URI values share a conservative split guard; incidental cross-type equal strings may over-isolate. Quote/hash/topic/ordinary relations do not merge identities or product entities.",
    "external_scope": "Public explicit synthetic reviewer inputs only; no actual human identities/holdout/DB/API/network/secrets; no push or accepted status.",
}
with (RUN / "delivery_manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
    json.dump(manifest, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print("FIX1_FROZEN: 3 Musts for independent recheck; 7 original exit0 -> 7 exit2")
