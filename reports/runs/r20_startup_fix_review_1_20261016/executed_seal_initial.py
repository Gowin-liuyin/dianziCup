"""Summarize independently executed samples and seal only review-owned artifacts."""

from __future__ import annotations

import datetime
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent


def main() -> None:
    receipts = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(RUN.glob("*.receipt.json"))]
    primary_commands = {"default_native": 1, "original_boundaries": 10, "real_pdf_parent": 1, "measured_boundaries": 2, "semantic_coverage_only": 0, "semantic_coverage_recheck": 1}
    observations = []
    cpu_seconds = 0.0
    for prefix in ("default_native", "original_boundaries", "real_pdf_parent"):
        payload = json.loads((RUN / f"{prefix}.observations.json").read_text(encoding="utf-8"))
        observations.extend(payload["records"])
        cpu_seconds += payload["observed_descendant_cpu_seconds"]
    custom_samples = []
    for prefix in ("initial_cpu_exhausted", "pdf_coverage_async", "semantic_coverage_positive"):
        payload = json.loads((RUN / f"{prefix}.json").read_text(encoding="utf-8"))
        custom_samples.append(prefix)
        observations.extend(payload["processes"])
        cpu_seconds += payload["observed_cpu_seconds"]
    worker_command_wall = sum(receipt["wall_seconds"] for receipt in receipts if receipt["name"] in primary_commands)
    actual_sample_ids = [row["actual_case_id"] for row in observations]
    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for receipt in receipts:
        for key, value in receipt.get("junit_counts", {}).items():
            counts[key] += value
    prior_red = ET.parse(ROOT / "reports/runs/r20_process_startup_fix_20261016/red_startup.xml").getroot().find("testsuite").attrib
    state = json.loads((ROOT / "progress/task_state.json").read_text(encoding="utf-8"))["recovery"]["R20"]
    pdf = json.loads((RUN / "pdf_coverage_async.json").read_text(encoding="utf-8"))
    pdf_result = json.loads(pdf["stdout"].splitlines()[-1])
    assert len(pdf_result["pages"]) == 4
    source_paths = ["backend/src/ai_intel/infrastructure/process_limits.py", "backend/src/ai_intel/ingestion/parsing/_pdf_worker.py", "backend/src/ai_intel/ingestion/parsing/pdf_text.py", "backend/src/ai_intel/infrastructure/models/semantic.py", "backend/tests/unit/test_r20_process_startup.py", "backend/tests/unit/test_r20_native_cpu_guard.py", "backend/pyproject.toml"]
    source_identities = []
    for path in source_paths:
        blob = subprocess.run(["git", "rev-parse", f"HEAD:{path}"], cwd=ROOT, capture_output=True, check=True).stdout.decode().strip()
        current_blob = subprocess.run(["git", "hash-object", path], cwd=ROOT, capture_output=True, check=True).stdout.decode().strip()
        assert blob == current_blob
        source_identities.append({"path": path, "git_blob": blob, "working_sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest()})
    summary = {"primary_worker_samples": sum(primary_commands.values()), "primary_worker_concurrency": 1, "command_samples": primary_commands, "sample_ids": sorted(set(actual_sample_ids)), "custom_sample_ids": custom_samples, "worker_commands_wall_seconds": worker_command_wall, "observed_descendant_cpu_seconds": cpu_seconds, "observed_process_count": len(observations), "all_observed_processes_signaled": all(row["signaled"] for row in observations), "cpu_measurement_limitation": "Scanner can miss a fast exited descendant before obtaining a handle; root CreateProcess children are synchronously retained. These are observed values, not an absolute complete-tree bound.", "budget_cpu_seconds": 45, "budget_wall_seconds": 180, "junit_counts": counts, "preserved_author_red_counts": {key: prior_red[key] for key in ("tests", "failures", "errors", "skipped")}, "R20_frozen_state": state, "source_identities": source_identities, "pdf_raw_result_independently_checked_pages": len(pdf_result["pages"]), "frozen_sha": "535c0a537bc24cb52c64511c72eeb4ea3ae5bc34", "code_sha": "41c61491b4429cc47dd970b201d9b2551cbb3a7f", "baseline_sha": "c3a2abc9a5246993eabb351d26cfeb51d0270b31"}
    assert summary["primary_worker_samples"] <= 15 and worker_command_wall < 180 and cpu_seconds < 45
    (RUN / "execution_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts = [{"relative_path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(RUN.rglob("*")) if path.is_file() and path.name != "review_artifact_manifest.json"]
    report = ROOT / "reports/reviews/recovery/G-F-R20-startup-fix-review-1.md"
    if report.exists():
        artifacts.append({"relative_path": str(report.relative_to(ROOT)).replace("\\", "/"), "bytes": report.stat().st_size, "sha256": hashlib.sha256(report.read_bytes()).hexdigest()})
    manifest = {"task": "R20-startup-fix-review-1", "frozen_sha": summary["frozen_sha"], "code_sha": summary["code_sha"], "sealed_shanghai": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="seconds"), "artifacts": artifacts}
    (RUN / "review_artifact_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("primary_worker_samples", "worker_commands_wall_seconds", "observed_descendant_cpu_seconds", "observed_process_count", "all_observed_processes_signaled", "junit_counts")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
