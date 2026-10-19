"""Seal exact evidence bytes and record the explicitly excluded cache/temp paths."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
REPORT = ROOT / "reports/tasks/G-C-integrated-8a-validation.md"
ZONE = timezone(timedelta(hours=8))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    started = datetime.now(ZONE).isoformat()
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == "8a1b04d48346d8550f0326a77f003246a0ebbab5"
    assert subprocess.check_output(["git", "status", "--short", "--untracked-files=no"], cwd=ROOT, text=True) == ""
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT, text=True).splitlines()
    allowed = ("reports/tasks/G-C-integrated-8a-validation.md", "reports/runs/recovery_gc_integrated_8a_validation_20261016/")
    assert all(path == allowed[0] or path.startswith(allowed[1]) for path in untracked)
    receipts = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(RUN.glob("*.command.json"))]
    (RUN / "command_index.json").write_text(json.dumps(receipts, indent=2), encoding="utf-8")
    (RUN / "instrumentation_issues.json").write_text(json.dumps({
        "initial_generic_launcher": {"label": "backend_full_pure", "observed_outer_exit": 1, "tests_executed": 0, "exception": "FileNotFoundError WinError2; argparse REMAINDER consumed --cwd as the command", "ended_at": None, "ended_at_note": "Not captured; not reconstructed", "actual_test_receipt": "backend_full_pure_actual.command.json"},
        "cbm_schema_first_attempt": {"label": "cbm_schema", "exit_code": 1, "error": "missing required argument project", "corrected_receipt": "cbm_schema_actual.command.json"},
        "pg_temp_move_first_attempt": {"label": "pg_temp_relocation", "exit_code": 1, "stage": "hashing before Move-Item", "error": "Windows PowerShell subprocess did not expose Get-FileHash", "source_still_present_and_destination_absent_observed": True, "corrected_receipt": "pg_temp_relocation_actual.command.json"},
        "browser_planned_count": 7, "browser_actual_selected_file_count": 3,
        "no_product_test_outcome_or_expectation_changed": True,
    }, indent=2), encoding="utf-8")
    external = []
    external_root = Path("D:/wt/gc-8a-validation-tmp")
    for folder in ("backend_pytest_tmp", "privacy_recheck", "pg_pytest_tmp", "generation_boundary"):
        for path in sorted((external_root / folder).rglob("*")):
            if path.is_symlink() or path.is_junction():
                external.append({"path": str(path), "symlink_or_junction": True, "content_not_followed": True})
            elif path.is_file():
                external.append({"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)})
    (RUN / "external_temporary_manifest.json").write_text(json.dumps({"root": str(external_root), "files": external, "contains_only_this_reviewers_synthetic_test_temporary_outputs": True}, indent=2), encoding="utf-8")
    source_docs = [
        ROOT / "AGENTS.md", ROOT / "docs/plan/00_execution_map.md",
        ROOT / "docs/plan/11_full_delivery_recovery_20261014.md", ROOT / "docs/plan/12_recovery_task_cards_20261014.md",
        *[ROOT / "docs/plan" / name for name in ("03_data_contracts.md", "05_api_and_tool_contracts.md", "06_testing_and_evaluation.md")],
        *[ROOT / "docs/decisions" / name for name in ("CR-R06_failed_response_receipts.md", "CR-R07_typed_signal_claim_v3.md", "CR-R07_enrichment_candidate_seam.md", "CR-R11_version_comparison_dependencies.md")],
        ROOT / "progress/task_state.json", ROOT / "progress/context_handoff.md",
        *[Path("D:/dianzi/reports/reviews/recovery") / name for name in (
            "G-C-R06-failed-response-review-1-recheck.md", "G-C-R07-core-review-1-recheck-v2.md", "G-C-R07-public-signals-review-1-recheck.md", "G-C-R07-model-fields-review-1-recheck.md", "G-B-R05-generation-predispatch-timeout-review-1.md", "G-D-R11-version-ranges-review-1-recheck.md", "G-E-R17-event-detail-ui-review-1-recheck.md", "G-F-R20-startup-fix-review-1.md")],
    ]
    (RUN / "read_authority_manifest.json").write_text(json.dumps([{"path": str(path), "bytes": path.stat().st_size, "raw_sha256": sha256(path)} for path in source_docs], indent=2), encoding="utf-8")
    (RUN / "final_scope.json").write_text(json.dumps({"head": "8a1b04d48346d8550f0326a77f003246a0ebbab5", "tree": "c614a6cb784c8fab422a14479d14ea4b6303493c", "tracked_status": "", "untracked_paths": untracked, "no_main_worktree_writes": True, "no_commit_push_or_acceptance": True}, indent=2), encoding="utf-8")
    excluded_names = {"artifact_manifest.json", "artifact_manifest.sha256", "seal.json", "raw_attributes.txt"}
    files = [REPORT] + [path for path in sorted(RUN.rglob("*")) if path.is_file() and "mypy_cache" not in path.relative_to(RUN).parts and path.name not in excluded_names]
    attributes = [f"{path.relative_to(ROOT).as_posix()} -text" for path in files]
    attributes += [f"{RUN.relative_to(ROOT).as_posix()}/{name} -text" for name in sorted(excluded_names)]
    (RUN / "raw_attributes.txt").write_text("\n".join(attributes) + "\n", encoding="utf-8")
    files.append(RUN / "raw_attributes.txt")
    artifacts = [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "raw_sha256": sha256(path)} for path in files]
    manifest = {"sealed_at": datetime.now(ZONE).isoformat(), "head": "8a1b04d48346d8550f0326a77f003246a0ebbab5", "tree": "c614a6cb784c8fab422a14479d14ea4b6303493c", "artifacts": artifacts, "excluded": {"cache": str(RUN / "mypy_cache"), "external_temporary_files": "external_temporary_manifest.json", "manifest_and_sidecar_and_seal": "No circular self-reference"}, "raw_attributes": "raw_attributes.txt; exact paths only, not applied by reviewer"}
    manifest_path = RUN / "artifact_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    digest = sha256(manifest_path)
    (RUN / "artifact_manifest.sha256").write_text(digest + "  artifact_manifest.json\n", encoding="utf-8")
    for artifact in artifacts:
        path = ROOT / artifact["path"]
        assert path.stat().st_size == artifact["bytes"] and sha256(path) == artifact["raw_sha256"]
    seal = {"started_at": started, "ended_at": datetime.now(ZONE).isoformat(), "exit_code": 0, "artifact_count": len(artifacts), "all_artifact_hashes_verified": True, "manifest_sha256": digest, "report_sha256": sha256(REPORT), "raw_attributes_sha256": sha256(RUN / "raw_attributes.txt"), "external_tmp_file_entries": len(external), "python_script_sha256": sha256(Path(__file__)), "tracked_status": ""}
    (RUN / "seal.json").write_text(json.dumps(seal, indent=2), encoding="utf-8")
    print(json.dumps(seal, indent=2))


if __name__ == "__main__":
    main()
