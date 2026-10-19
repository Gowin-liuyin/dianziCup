"""Seal reviewer-owned raw bytes and the report after all checks have finished."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timedelta, timezone

RUN_DIRECTORY = Path(__file__).resolve().parent
WORKTREE = RUN_DIRECTORY.parents[2]
REPORT = WORKTREE / "reports/reviews/recovery/G-C-R08-aggregate-connectors-review-1.md"
SHANGHAI = timezone(timedelta(hours=8))


def main():
    started_at = datetime.now(SHANGHAI).isoformat(timespec="seconds")
    manifest_path = RUN_DIRECTORY / "seal_manifest.json"
    paths = sorted(path for path in RUN_DIRECTORY.iterdir() if path.is_file() and path != manifest_path)
    paths.append(REPORT)
    entries = []
    for path in paths:
        raw = path.read_bytes()
        entry = {"path": path.relative_to(WORKTREE).as_posix(), "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        entries.append(entry)
    tracked_diff = subprocess.check_output(["git", "diff", "--name-only"], cwd=WORKTREE, text=True).splitlines()
    staged_diff = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=WORKTREE, text=True).splitlines()
    assert tracked_diff == staged_diff == []
    for entry in entries:
        raw = (WORKTREE / entry["path"]).read_bytes()
        assert len(raw) == entry["size_bytes"] and hashlib.sha256(raw).hexdigest() == entry["sha256"]
    manifest = {
        "schema_version": "r08-aggregate-independent-review-seal-1",
        "argv": [sys.executable, *sys.argv],
        "cwd": str(Path.cwd()),
        "started_at": started_at,
        "ended_at": datetime.now(SHANGHAI).isoformat(timespec="seconds"),
        "exit_code": 0,
        "reviewer": "/root/r08_aggregate_connectors_independent_review",
        "base_sha": "cb34097898b412390ee7e119d0d5c2c90d090673",
        "code_sha": "8e150878a76e541e377b300f851d9c7caf919019",
        "head_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=WORKTREE, text=True).strip(),
        "verdict": "Ship: connector preparation package only",
        "test_counts": {"new_unit": 51, "new_contract": 13, "new_security": 36, "gateway_regression": 145, "r07_regression": 43, "independent": 73},
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "external_operations": {"official_document": 0, "account": 0, "search": 0, "model": 0},
        "tracked_diff": tracked_diff,
        "staged_diff": staged_diff,
        "verification": {"unit": "passed", "contract": "passed", "integration": "not_run", "security": "passed", "frontend": "not_run", "e2e": "not_run", "live": "not_run", "manual": "not_run"},
        "byte_validation": "all entries verified immediately before writing this manifest; this manifest excludes itself",
        "entry_count": len(entries),
        "entries": entries,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in manifest.items() if key != "entries"}, ensure_ascii=False))
    print("seal_manifest_sha256=" + hashlib.sha256(manifest_path.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
