"""Bind the UI source commit and evidence files without changing their bytes."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
from zoneinfo import ZoneInfo

WORKSPACE = Path(__file__).resolve().parents[3]
RUN_DIRECTORY = Path(__file__).resolve().parent
SOURCE_COMMIT = "c5ad9de9d31a28f927d45dcbd4589fa840a9101f"
SOURCE_PATHS = [
    "frontend/src/features/events/event-workspace.tsx",
    "frontend/src/features/events/event-workspace.test.tsx",
    "frontend/src/features/events/event-detail-view.tsx",
    "frontend/src/features/events/event-detail-view.test.tsx",
    "frontend/src/features/events/event-detail.fixture.ts",
    "frontend/src/features/events/event-display.tsx",
    "frontend/src/features/events/events.css",
    "frontend/e2e/r17_event_detail_fixture.spec.ts",
]


def artifact_record(path: Path) -> dict[str, str | int]:
    """Keep both local bytes and LF-canonical text hashes for Windows checkout."""
    content = path.read_bytes()
    record: dict[str, str | int] = {"path": path.relative_to(WORKSPACE).as_posix(), "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return record
    record["sha256_lf"] = hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest()
    return record


source_records = []
for source_path in SOURCE_PATHS:
    record = artifact_record(WORKSPACE / source_path)
    git_content = subprocess.run(["git", "show", f"{SOURCE_COMMIT}:{source_path}"], cwd=WORKSPACE, check=True, capture_output=True).stdout
    assert record["sha256_lf"] == hashlib.sha256(git_content).hexdigest(), source_path
    source_records.append(record)

evidence_paths = sorted(path for path in RUN_DIRECTORY.rglob("*") if path.is_file() and path.name != "artifact_manifest.json")
evidence_paths.append(WORKSPACE / "reports/tasks/R17-event-detail-ui.md")
evidence_records = [artifact_record(path) for path in evidence_paths]
credential_pattern = re.compile(rb"(?:sk-[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9._-]{20,}|(?:password|api_key)\s*[:=]\s*['\"][A-Za-z0-9_-]{20,}['\"])")
credential_like_matches = sum(len(credential_pattern.findall(path.read_bytes())) for path in evidence_paths)
assert credential_like_matches == 0
fixture_markers = ["隔离 Fixture：九维状态与历史证据", "fixture_scope_unavailable", "fixture_cvss_score", "这是修订 1 的保存片段"]
bundle_matches = sum(text.count(marker) for path in (WORKSPACE / "frontend/dist/assets").glob("*.js") for text in [path.read_text(encoding="utf-8")] for marker in fixture_markers)
assert bundle_matches == 0

unit_result = json.loads((RUN_DIRECTORY / "regression-tests.json").read_text(encoding="utf-8"))
browser_result = json.loads((RUN_DIRECTORY / "browser.json").read_text(encoding="utf-8"))
manifest = {
    "task": "R17 event detail UI current schema2 slice",
    "status": "awaiting_review",
    "implementation": "complete_limited_slice",
    "whole_R17_implementation": "partial",
    "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "baseline_commit": "c3a2abc9a5246993eabb351d26cfeb51d0270b31",
    "source_commit": SOURCE_COMMIT,
    "source_files": source_records,
    "evidence_files": evidence_records,
    "unit": {"total": unit_result["numTotalTests"], "passed": unit_result["numPassedTests"], "failed": unit_result["numFailedTests"], "skipped": unit_result["numPendingTests"], "mode": "isolated_fixture_and_existing_regression"},
    "browser": {"expected": browser_result["stats"]["expected"], "unexpected": browser_result["stats"]["unexpected"], "skipped": browser_result["stats"]["skipped"], "flaky": browser_result["stats"]["flaky"], "mode": "explicit_isolated_fixture", "new": 3, "existing": 4},
    "credential_like_pattern_matches": credential_like_matches,
    "production_bundle_fixture_marker_matches": bundle_matches,
    "live": "not_run",
    "real_backend_integration": "not_run",
    "manual": "author_visual_check_only_independent_review_pending",
    "push": "not_run",
}
(RUN_DIRECTORY / "artifact_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"source_commit": SOURCE_COMMIT, "sources": len(source_records), "evidence_files": len(evidence_records), "unit_passed": manifest["unit"]["passed"], "browser_expected": manifest["browser"]["expected"], "credential_like_pattern_matches": credential_like_matches, "production_fixture_markers": bundle_matches}))
