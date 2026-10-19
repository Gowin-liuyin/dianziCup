"""Seal reviewer-owned fixed recheck evidence and verify each listed raw file."""

from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ElementTree

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
REPORT = ROOT / "reports/reviews/recovery/G-D-R11-version-ranges-review-1-recheck.md"
TARGET = RUN / "artifact_manifest.json"
files = sorted([path for path in RUN.rglob("*") if path.is_file() and "__pycache__" not in path.parts and path != TARGET] + [REPORT])
artifacts = []
for path in files:
    value = path.read_bytes()
    artifacts.append({"path": path.relative_to(ROOT).as_posix(), "bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()})
receipts = []
for path in sorted(RUN.glob("*.receipt.json")):
    item = json.loads(path.read_text(encoding="utf-8"))
    receipts.append({"path": path.relative_to(ROOT).as_posix(), "exit_code": item["exit_code"], "started_at": item["started_at"], "ended_at": item["ended_at"]})
test_counts = {}
for label in ("recheck_original_33", "recheck_new_67", "recheck_original_94", "recheck_original_175"):
    root = ElementTree.fromstring((RUN / f"{label}.xml").read_bytes())
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    test_counts[label] = {key: sum(int(suite.get(key, "0")) for suite in suites) for key in ("tests", "failures", "errors", "skipped")}
manifest = {"schema_version": 1, "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(), "reviewer": "/root/r11_version_ranges_independent_review", "task": "R11:T26 version-ranges fix1 independent scoped recheck", "verdict": "Ship only internal exact version preparation slice; original Must 1 and Should 2 closed", "source_fix_sha": "65838b42c0dcff863036968e39a1404aa323b3c9", "code_sha": "71e724131daf4d03372392d58cd17c764c3e2e40", "material_sha": "8f5fe818774349b41b0b5aceb45d69ba81410678", "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, check=True).stdout.decode().strip(), "branch": "codex/r11-version-ranges-review1-fix1", "author_manifest_sha256": "a90e7ed882d62c1312f000f7a5178a2d324ab07c92d1383e0dbb1a6df6cba861", "report": REPORT.relative_to(ROOT).as_posix(), "test_counts_no_cross_run_addition": test_counts, "environment_attempts_not_business_failures": {"long_worktree_creation": "tool error: filename too long; shorter worktree succeeded", "offline_sync_exit": 2, "offline_sync_reason": "jsonschema wheel access denied", "original_33_startup_exit": 1, "new_67_startup_exit": 1, "startup_cases": 0, "fallback": "Previous independent review same-lock environment with explicit PYTHONPATH to new worktree; runtime import verified"}, "preserved_failures": {"original_independent_33": "28 passed / 5 failed before fix", "new_boundaries_67": "6 passed / 61 failed before fix", "author_old_fullunit": "1627 passed / 4 R20 failures; 71.03% coverage at original 60% threshold; not rerun or closed"}, "not_checked": ["new clean environment install success", "full unit rerun", "PG/worker/API assessment integration", "real assets", "model", "external network/live", "frontend/e2e", "performance", "manual", "whole R11/T26/G-D"], "volatile_excluded": ["__pycache__"], "self_reference": "The manifest does not include its own bytes; final handoff provides its hash.", "receipts": receipts, "artifacts": artifacts}
TARGET.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
for item in artifacts:
    value = (ROOT / item["path"]).read_bytes()
    assert len(value) == item["bytes"]
    assert hashlib.sha256(value).hexdigest() == item["sha256"]
print(json.dumps({"manifest_path": str(TARGET), "manifest_sha256": hashlib.sha256(TARGET.read_bytes()).hexdigest(), "listed_artifact_files": len(artifacts), "including_manifest": len(artifacts) + 1, "verification_mismatches": 0, "created_at": manifest["created_at"]}, ensure_ascii=False, indent=2))
