"""Seal raw independent recheck evidence; do not mutate tracked business or historical evidence."""

import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
REPORT = ROOT / "reports/reviews/recovery/G-D-R11-manifest-parser-review-1-recheck.md"
MANIFEST = RUN / "artifact_manifest.json"


def git(*arguments):
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, check=True).stdout.decode().strip()


def main():
    paths = sorted([path for path in RUN.iterdir() if path.is_file() and path != MANIFEST] + [REPORT])
    entries = []
    for path in paths:
        raw = path.read_bytes()
        entries.append({"path": path.relative_to(ROOT).as_posix(), "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "representation": "raw_working_bytes"})
    manifest = {
        "schema_version": 1,
        "recorded_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "task": "R11/T24 manifest parser review 1 two Must recheck",
        "verdict": "scoped_ship",
        "review_branch": git("branch", "--show-current"),
        "review_head_sha": git("rev-parse", "HEAD"),
        "review_commit_sha": None,
        "code_sha": "64dcd946601cd0e0f7435f59019ee709e3738a35",
        "material_sha": "37e492b4e26fc5b6197b60d2494926d4181a21c3",
        "material_manifest_sha256": "c0cb74e7019bf4588e76143d3b019f9ac0c3aa35fc36397f964808bd64689a68",
        "initial_review_manifest_sha256": "1c644e365aaf9bf1d5ad9a273f0c85da669f3609162b51cad6cbfc980051c0e0",
        "initial_review_probe_sha256": "ac13a06334ea163e5c3f95da0d7592aaa7c61a232b1ed7178be6b99983ab2b1c",
        "original_manifest_sha256": "e1827675743d736036c0d6ded14ce3243280ef96dd694033a431253066d30a92",
        "evidence_verified": {"fixed_artifacts": 84, "fixed_source_proofs": 5, "original_artifacts_baseline": 102, "original_current_unchanged": 100, "approved_original_changes": ["backend/src/ai_intel/assets/manifest_parser.py", ".gitattributes"], "initial_review_files": 80, "old_failure_decompressed_bytes": 41951937},
        "tracked_diff": git("diff", "--name-status"),
        "tracked_cached_diff": git("diff", "--cached", "--name-status"),
        "report": REPORT.relative_to(ROOT).as_posix(),
        "closed_findings": [{"id": 1, "priority": "P2", "status": "closed", "title": "permission set semantic identity"}, {"id": 2, "priority": "P2", "status": "closed", "title": "timestamp actual offset and UTC representability"}],
        "new_must_findings": [],
        "tests": {
            "original_65": {"passed": 65, "unit": 32, "contract": 1, "security": 32, "failed": 0, "errors": 0, "skipped": 0},
            "added_36": {"passed": 36, "failed": 0, "errors": 0, "skipped": 0},
            "related_112": {"passed": 112, "failed": 0, "errors": 0, "skipped": 0, "note": "separate existing related regression"},
            "original_review_38": {"passed": 37, "failed": 1, "errors": 0, "skipped": 0, "overall_exit_code": 1, "remaining_failure": "unconfirmed CSV dialect exploratory probe; no Must; original input/expectation preserved"},
            "independent_28": {"passed": 28, "failed": 0, "errors": 0, "skipped": 0, "rerun_is_not_another_28_cases": True},
        },
        "verification": {"unit": "passed", "contract": "passed", "security": "passed", "integration": "not_run", "frontend": "not_run", "e2e": "not_run", "live": "not_run", "manual": "not_run", "original_review_38_overall": "failed", "fullsuite": "not_run"},
        "limits": "pure candidate fix only; no whole R11/T24/G-D or old four CPU/fullsuite closure",
        "external_calls": {"network": 0, "model": 0, "postgres": 0, "service_start": 0, "actual_asset_access_or_scan": 0, "paid_batch": 0},
        "files": entries,
    }
    if manifest["tracked_diff"] or manifest["tracked_cached_diff"]:
        raise RuntimeError("Tracked files changed during read-only recheck")
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for entry in json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]:
        raw = (ROOT / entry["path"]).read_bytes()
        if len(raw) != entry["size_bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise RuntimeError("Review evidence changed during seal")
    print(json.dumps({"manifest": str(MANIFEST), "sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(), "files": len(entries), "verified": len(entries), "report": str(REPORT), "code_sha": manifest["code_sha"], "material_sha": manifest["material_sha"], "closed": [1, 2], "verdict": "scoped_ship"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
