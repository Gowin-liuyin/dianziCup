"""Verify the author's frozen manifest against exact bytes and Git blobs."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[3]
run = Path(__file__).parent
author = root / "reports/runs/recovery_r08_aggregate_persistence_20261016/artifact_manifest.json"
manifest = json.loads(author.read_text(encoding="utf-8"))
code_sha = manifest["code_sha"]
review_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
entries = []
for entry in manifest["files"]:
    path = root / entry["path"]
    raw = path.read_bytes()
    blob = subprocess.check_output(["git", "show", f'{review_sha}:{entry["path"]}'], cwd=root)
    if entry["basis"] == "git_blob":
        content = subprocess.check_output(["git", "show", f'{code_sha}:{entry["path"]}'], cwd=root)
    elif entry["basis"] == "canonical_text_lf":
        content = path.read_text(encoding="utf-8").replace("\r\n", "\n").encode()
    else:
        content = raw
    entries.append({"path": entry["path"], "basis": entry["basis"],
        "expected_sha256": entry["sha256"], "actual_basis_sha256": hashlib.sha256(content).hexdigest(),
        "declared_match": len(content) == entry["size_bytes"] and hashlib.sha256(content).hexdigest() == entry["sha256"],
        "raw_sha256": hashlib.sha256(raw).hexdigest(), "review_git_blob_sha256": hashlib.sha256(blob).hexdigest(),
        "raw_equals_git_blob": raw == blob,
        "frozen_code_equals_review_blob": content == blob if entry["basis"] == "git_blob" else None})
required = ["AGENTS.md", "docs/plan/00_execution_map.md", "docs/plan/12_recovery_task_cards_20261014.md",
    "docs/tasks/T23_poc_scores_impact.md", "docs/plan/03_data_contracts.md", "docs/plan/04_workflows_and_algorithms.md",
    "docs/plan/05_api_and_tool_contracts.md", "docs/plan/06_testing_and_evaluation.md",
    "contracts/schemas/public_api_v2.json", "progress/task_state.json", "progress/context_handoff.md",
    "docs/decisions/CR-R08_aggregate_persistence.md", "reports/tasks/R08-aggregate-persistence.md"]
receipt = {"reviewed_sha": review_sha,
    "reviewed_tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip(),
    "code_sha": code_sha, "code_tree": subprocess.check_output(["git", "rev-parse", f"{code_sha}^{{tree}}"], cwd=root, text=True).strip(),
    "recorded_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
    "author_manifest_raw_sha256": hashlib.sha256(author.read_bytes()).hexdigest(),
    "declared_files": len(entries), "declared_matches": sum(e["declared_match"] for e in entries),
    "entries": entries,
    "required_reads": [{"path": p, "size_bytes": len((root / p).read_bytes()),
        "sha256": hashlib.sha256((root / p).read_bytes()).hexdigest()} for p in required]}
(run / "author_material_audit.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
code_paths = [e["path"] for e in entries if e["basis"] == "git_blob"]
for name, argv in [
    ("targeted_diff_check", ["git", "diff", "--check", manifest["base_sha"], review_sha, "--", *code_paths,
        "reports/tasks/R08-aggregate-persistence.md"]),
    ("raw_diff_check", ["git", "diff", "--check", manifest["base_sha"], review_sha]),
    ("current_callers_rg", ["rg", "-n", "AggregateService|PostgresAggregateRepository|AggregateServerPolicy|save_observation|read_latest|collect_provider_aggregate_observation|read_current_provider_aggregate|collect_product_aggregate_observations|SafeAggregateCache", "backend/src", "frontend/src"]),
    ("code_frozen_diff", ["git", "diff", code_sha, review_sha, "--", "backend/src", "backend/tests"]),
]:
    result = subprocess.run(argv, cwd=root, capture_output=True)
    (run / f"{name}.log").write_bytes(result.stdout + result.stderr)
    receipt.setdefault("checks", []).append({"label": name, "argv": argv, "exit_code": result.returncode,
        "output_bytes": len(result.stdout) + len(result.stderr)})
(run / "author_material_audit.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: receipt[k] for k in ["reviewed_sha", "reviewed_tree", "code_sha", "code_tree",
    "author_manifest_raw_sha256", "declared_files", "declared_matches", "checks"]}))
assert all(entry["declared_match"] for entry in entries)
assert all(entry["frozen_code_equals_review_blob"] is not False for entry in entries)
