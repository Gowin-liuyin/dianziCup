"""Bind the narrow touch-target repair and preserve before/after evidence."""

from __future__ import annotations

import base64
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

WORKSPACE = Path(__file__).resolve().parents[3]
RUN_DIRECTORY = Path(__file__).resolve().parent
SOURCE_COMMIT = "592b49d6920a4b25db094212eab1d74ca964b1c2"
SOURCE_PATHS = ["frontend/src/features/events/events.css", "frontend/e2e/r17_event_detail_fixture.spec.ts"]


def record_file(path: Path) -> dict[str, str | int]:
    """Record raw bytes and canonical LF text without editing the input."""
    content = path.read_bytes()
    record: dict[str, str | int] = {"path": path.relative_to(WORKSPACE).as_posix(), "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return record
    record["sha256_lf"] = hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest()
    return record


probe_sha = hashlib.sha256((RUN_DIRECTORY / "review-fixture-probes.spec.ts").read_bytes()).hexdigest()
assert probe_sha == "999901b621a1e59f927e5937e0ad20219faf40253be2a892ac5d90207c70aa05"
browser_result = json.loads((RUN_DIRECTORY / "browser.json").read_text(encoding="utf-8"))
target_sizes = []
for suite in browser_result["suites"]:
    for spec in suite["specs"]:
        for test_result in spec["tests"]:
            for result in test_result["results"]:
                for attachment in result["attachments"]:
                    if attachment["name"].startswith("fact-target-metrics-"):
                        target_sizes.append(json.loads(base64.b64decode(attachment["body"])))
assert sorted(item["width"] for item in target_sizes) == [390, 1366]
for viewport_metrics in target_sizes:
    required_height = 44 if viewport_metrics["width"] == 390 else 40
    assert all(item["bounds"]["height"] >= required_height and item["minHeight"] == f"{required_height}px" for item in viewport_metrics["factTargetMetrics"])
(RUN_DIRECTORY / "target-size-summary.json").write_text(json.dumps(target_sizes, indent=2) + "\n", encoding="utf-8")

source_records = []
for source_path in SOURCE_PATHS:
    record = record_file(WORKSPACE / source_path)
    content = subprocess.run(["git", "cat-file", "blob", f"{SOURCE_COMMIT}:{source_path}"], cwd=WORKSPACE, capture_output=True, check=True).stdout
    assert record["sha256_lf"] == hashlib.sha256(content).hexdigest()
    source_records.append(record)

unit = json.loads((RUN_DIRECTORY / "events-tests.json").read_text(encoding="utf-8"))
original_probe = json.loads((RUN_DIRECTORY / "browser-probes-original.json").read_text(encoding="utf-8"))
fixed_probe = json.loads((RUN_DIRECTORY / "browser-probes.json").read_text(encoding="utf-8"))
evidence_paths = sorted(path for path in RUN_DIRECTORY.rglob("*") if path.is_file() and path.name != "artifact_manifest.json")
evidence_paths.append(WORKSPACE / "reports/tasks/R17-event-detail-ui-fix1.md")
manifest = {
    "task": "R17 event detail UI finding 1 touch-target repair",
    "status": "awaiting_review",
    "whole_R17_implementation": "partial",
    "baseline_commit": "e594cbbcaf82a0ccc36fc0b1cd9f4988da330127",
    "source_commit": SOURCE_COMMIT,
    "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "source_files": source_records,
    "evidence_files": [record_file(path) for path in evidence_paths],
    "original_probe_sha256": probe_sha,
    "original_probe_stats": original_probe["stats"],
    "fixed_probe_stats": fixed_probe["stats"],
    "browser_stats": browser_result["stats"],
    "unit": {"total": unit["numTotalTests"], "passed": unit["numPassedTests"], "failed": unit["numFailedTests"], "skipped": unit["numPendingTests"]},
    "full_352_regression": "not_run_this_css_only_repair",
    "real_backend_integration": "not_run",
    "live": "not_run",
    "independent_fix_review": "pending_root_dispatch",
    "push": "not_run",
}
(RUN_DIRECTORY / "artifact_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"source_commit": SOURCE_COMMIT, "source_files": len(source_records), "evidence_files": len(evidence_paths), "original_probe": original_probe["stats"], "fixed_probe": fixed_probe["stats"], "browser": browser_result["stats"], "unit": manifest["unit"]}, ensure_ascii=False))
