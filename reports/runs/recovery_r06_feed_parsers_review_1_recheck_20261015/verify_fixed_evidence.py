"""Verify fixed Git blobs and lossless diagnostic archives without dumping their content."""

from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path("D:/wt/r06-feed-review-recheck")
RUN = Path(__file__).resolve().parent
AUTHOR_RUN = ROOT / "reports/runs/recovery_r06_feed_parsers_20261015"
TARGET = "cb9e3c53f5504b7c6ed3b65e40ba0b92c124fd9f"
CODE = "6b7dd7e881bb822e83b55f8302f7aefe565f4940"
BASELINE = "7ed73540c001a4e7f5b5fa5dc2948c4b4635590f"


def git(*arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def main() -> None:
    manifest = json.loads((AUTHOR_RUN / "delivery_files.json").read_bytes())
    checked: list[dict[str, object]] = []
    checkout_transformations: list[str] = []
    for record in manifest["files"]:
        payload = git("show", f"{TARGET}:{record['path']}")
        digest = hashlib.sha256(payload).hexdigest()
        checked.append({"path": record["path"], "bytes": len(payload), "sha256": digest})
        assert digest == record["sha256"], record["path"]
        assert len(payload) == record["bytes"], record["path"]
        local_payload = (ROOT / record["path"]).read_bytes()
        if payload != local_payload:
            assert (
                git("hash-object", "--path", record["path"], record["path"]).strip()
                == git("rev-parse", f"{TARGET}:{record['path']}").strip()
            )
            checkout_transformations.append(record["path"])
    assert len(checked) == manifest["file_count_without_self"] == 159
    assert sum(int(record["bytes"]) for record in checked) == manifest["total_bytes_without_self"]
    archives = json.loads((AUTHOR_RUN / "large_diagnostic_archives.json").read_bytes())
    compressed_checks: list[dict[str, object]] = []
    for record in archives["archives"]:
        payload = git(
            "show", f"{TARGET}:reports/runs/recovery_r06_feed_parsers_20261015/{record['archive']}"
        )
        original = gzip.decompress(payload)
        assert hashlib.sha256(payload).hexdigest() == record["archive_sha256"]
        assert len(payload) == record["archive_bytes"]
        assert hashlib.sha256(original).hexdigest() == record["original_sha256"]
        assert len(original) == record["original_bytes"]
        compressed_checks.append({"archive": record["archive"], "original_hash_match": True})
    code_paths = [
        "backend/src/ai_intel/ingestion/sources/arxiv_atom.py",
        "backend/src/ai_intel/ingestion/sources/trailofbits_rss.py",
        "backend/tests/unit/test_r06_feed_parsers.py",
        "backend/tests/contract/test_r06_archived_feed_replay.py",
    ]
    code_checks = []
    for path in code_paths:
        payload = git("show", f"{TARGET}:{path}")
        assert payload == git("show", f"{CODE}:{path}")
        code_checks.append(
            {
                "path": path,
                "git_blob": git("rev-parse", f"{TARGET}:{path}").decode().strip(),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    changed_paths = git("diff", "--name-only", BASELINE, TARGET).decode().splitlines()
    assert (
        "reports/runs/recovery_r06_feed_parsers_20261015/doh_05_trailofbits_feed.body"
        not in changed_paths
    )
    result = {
        "target": TARGET,
        "target_tree": git("rev-parse", f"{TARGET}^{{tree}}").decode().strip(),
        "src_tree": git("rev-parse", f"{TARGET}:backend/src").decode().strip(),
        "code_src_tree": git("rev-parse", f"{CODE}:backend/src").decode().strip(),
        "baseline": BASELINE,
        "worktree_status": git("status", "--short").decode(),
        "manifest_files": checked,
        "checkout_transformations_verified_through_git_filter": checkout_transformations,
        "archives": compressed_checks,
        "fixed_code_files": code_checks,
        "changed_paths": changed_paths,
        "raw_trailofbits_added_to_candidate": False,
    }
    (RUN / "evidence_verification_result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "verified_manifest_blobs": len(checked),
                "verified_lossless_archives": len(compressed_checks),
                "identical_code_files": len(code_checks),
                "target_tree": result["target_tree"],
                "src_tree": result["src_tree"],
                "checkout_transformations": checkout_transformations,
                "worktree_status": result["worktree_status"],
            }
        )
    )


if __name__ == "__main__":
    main()
