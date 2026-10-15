"""Freeze recheck source identity and actual command records; no secrets read."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

candidate = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r01-recheck\dianzi")
artifact = Path(__file__).parent


def git(*arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=candidate, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


counts = {
    "backend_unit": {"passed": 57, "failed": 0, "skipped": 0, "coverage_percent": 63.83, "unit_floor_percent": 60},
    "backend_security": {"passed": 32, "failed": 1, "skipped": 0},
    "frontend_test": {"passed": 39, "failed": 0, "skipped": 0, "test_files": 5},
    "script_contract_fixture": {"passed": 108, "failed": 0, "skipped": 0, "deselected": 1, "complete_real_pg_contract": False},
    "backend_recheck_probe": {"passed": 4, "failed": 0, "kind": "independent isolated router unit boundary; no PG"},
    "frontend_recheck_probe": {"passed": 5, "failed": 0, "kind": "independent component with mocked HTTP; not browser"},
    "script_frontend_legacy_gbk": {"passed": 39, "failed": 0, "skipped": 0, "lint_typecheck_build": "passed", "environment_overrides": {"PYTHONIOENCODING": "gbk"}},
    "classification_evidence": {"historical_files": 2, "pattern_matches": 11, "physical_lines": 7, "source_blobs": 2, "earlier_review_log_matches": 1, "kind": "byte/provenance verification only, not classification implementation acceptance"},
}
records = []
for filename in artifact.glob("*.json"):
    if filename.name in {"commands.json", "snapshot.json", "classification_evidence.json"}:
        continue
    entry = json.loads(filename.read_text(encoding="utf-8-sig"))
    if isinstance(entry, dict) and "argv" in entry:
        entry["counts"] = counts.get(entry["id"], {"tests": "not_applicable"})
        records.append(entry)
records.sort(key=lambda item: (item["started_at"], item["id"]))
(artifact / "commands.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
source_tree = git("ls-tree", "-r", "HEAD", "--", "backend/src", "frontend/src", "scripts")
document_paths = ["AGENTS.md", "docs/plan/00_execution_map.md", "docs/plan/03_data_contracts.md", "docs/plan/05_api_and_tool_contracts.md", "docs/plan/06_testing_and_evaluation.md", "docs/plan/08_code_style.md", "docs/plan/09_operations_delivery.md", "docs/plan/12_recovery_task_cards_20261014.md", "docs/tasks/T02_project_skeleton.md", "docs/tasks/T03_development_services.md", "docs/tasks/T06_authentication_and_scope.md", "docs/tasks/T40_frontend_shell.md", "contracts/schemas/public_api_v2.json", "progress/task_state.json", "progress/context_handoff.md"]
snapshot = {
    "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "candidate_root": str(candidate),
    "candidate_sha": git("rev-parse", "HEAD"),
    "candidate_tree": git("rev-parse", "HEAD^{tree}"),
    "branch": git("branch", "--show-current"),
    "git_status_short": git("status", "--short"),
    "recheck_baseline": "4a17ca7b967a10d6077ba5219984a2d1a74cf320",
    "original_baseline": "f0b154ee0e10100bc9a9d293ebeded13926d0a42",
    "source_index_scopes": ["backend/src", "frontend/src", "scripts"],
    "source_index_listing_sha256": hashlib.sha256(source_tree.encode()).hexdigest(),
    "source_index_listing": source_tree.splitlines(),
    "document_hashes": {relative: hashlib.sha256((candidate / relative).read_bytes()).hexdigest() for relative in document_paths},
    "cbm_cache": "/tmp/dianzi-cbm-r01-behavior-recheck-fd4f1d4-20261015",
    "cbm_binary": "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp",
    "cbm_version": "0.11.0",
    "command_records": len(records),
    "verification_limits": {"real_pg_worker_compose_browser_live_manual": "not_run by reviewer", "authorized_secret_exact_scan": "not_run by reviewer; secrets not accessed", "secret_classification_rejection_regressions": "not_run: classifier not implemented in candidate", "dependency_upgrade": "not in candidate, no opinion on another frozen SHA"},
}
(artifact / "snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({key: snapshot[key] for key in ("captured_at", "candidate_sha", "candidate_tree", "branch", "git_status_short", "source_index_listing_sha256", "command_records")}))
