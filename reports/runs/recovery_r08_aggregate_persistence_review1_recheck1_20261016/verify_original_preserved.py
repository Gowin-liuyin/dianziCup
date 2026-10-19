"""Verify the first review's sealed artifacts without changing its worktree or evidence."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

original_root = Path("D:/wt/r08-persistence-review1")
original_manifest_path = original_root / "reports/runs/recovery_r08_aggregate_persistence_review1_20261016/artifact_manifest.json"
manifest_bytes = original_manifest_path.read_bytes()
manifest = json.loads(manifest_bytes)
mismatches = [entry["path"] for entry in manifest["files"] if
    hashlib.sha256((original_root / entry["path"]).read_bytes()).hexdigest() != entry["sha256"]
    or len((original_root / entry["path"]).read_bytes()) != entry["size_bytes"]]
receipt = {"recorded_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
    "original_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
    "original_manifest_matches_previously_observed_hash": hashlib.sha256(manifest_bytes).hexdigest() ==
        "28d5eacb9c6ff36eb18981926f87d8afd63761345cbc2cc821e0ce0a2248fcfd",
    "files": len(manifest["files"]), "mismatches": mismatches,
    "red_log_sha256": hashlib.sha256((original_root /
        "reports/runs/recovery_r08_aggregate_persistence_review1_20261016/independent_boundaries_final.log").read_bytes()).hexdigest(),
    "probe_sha256": hashlib.sha256((original_root /
        "reports/runs/recovery_r08_aggregate_persistence_review1_20261016/test_review_boundaries.py").read_bytes()).hexdigest()}
(Path(__file__).parent / "original_review_preserved.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(json.dumps(receipt))
assert not mismatches and receipt["original_manifest_matches_previously_observed_hash"]
