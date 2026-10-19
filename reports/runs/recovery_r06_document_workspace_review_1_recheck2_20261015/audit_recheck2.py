"""Preserve fixed Git bytes and unchanged probes, recording corrected probe differences."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess

workspace = Path("D:/wt/r06-doc-recheck2")
run_directory = workspace / "reports/runs/recovery_r06_document_workspace_review_1_recheck2_20261015"
source_commit = "2f5c7ef225ce2d29da2438a4d5caa51cdc6a9231"
metadata_commit = "0a8a3b826cf47185e8de5af555948dfedb2bc3f0"
baseline_commit = "ef3a0583179a27ccdaca05b771afccc90429dc35"

def git(*arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=workspace)

files = []
for relative in git("diff", "--name-only", baseline_commit, source_commit, "--", "frontend").decode().splitlines():
    blob = git("show", f"{source_commit}:{relative}")
    local = (workspace / relative).read_bytes()
    files.append({"path": relative, "blob_id": git("rev-parse", f"{source_commit}:{relative}").decode().strip(), "git_bytes": len(blob), "git_sha256": hashlib.sha256(blob).hexdigest(), "worktree_bytes": len(local), "worktree_sha256": hashlib.sha256(local).hexdigest(), "git_crlf": blob.count(b"\r\n"), "worktree_crlf": local.count(b"\r\n"), "same_after_crlf_normalization": blob.replace(b"\r\n", b"\n") == local.replace(b"\r\n", b"\n")})
checks = []
for label, final in [("source_diff_check", source_commit), ("metadata_diff_check", metadata_commit)]:
    arguments = ["git", "diff", "--check", baseline_commit, final, "--", "frontend", "docs/design/recovery/r06_document_workspace.md", "reports/tasks/R06-document-workspace.md"]
    result = subprocess.run(arguments, cwd=workspace, capture_output=True)
    (run_directory / f"{label}.log").write_bytes(result.stdout + result.stderr)
    checks.append({"command": arguments, "exit": result.returncode})
prior_directory = Path("D:/dianzi/reports/runs/recovery_r06_document_workspace_review_1_recheck_20261015")
inputs = []
for name in ["review.test.ts", "review.browser.spec.ts", "recheck.race.test.ts", "catalog_privacy.test.ts", "catalog_privacy.browser.spec.ts", "native_cache.browser.spec.ts", "native_cache_fixture.mjs"]:
    old_hash = hashlib.sha256((prior_directory / name).read_bytes()).hexdigest()
    new_hash = hashlib.sha256((run_directory / name).read_bytes()).hexdigest()
    inputs.append({"file": name, "original_sha256": old_hash, "copied_sha256": new_hash, "same": old_hash == new_hash})
result = subprocess.run(["git", "diff", "--no-index", "--", str(run_directory / "catalog_privacy.browser.spec.ts"), str(run_directory / "catalog_privacy.corrected.browser.spec.ts")], cwd=workspace, capture_output=True)
(run_directory / "legacy_corrected_probe.diff").write_bytes(result.stdout + result.stderr)
record = {"recorded_at": datetime.now().astimezone().isoformat(), "head": git("rev-parse", "HEAD").decode().strip(), "head_tree": git("rev-parse", "HEAD^{tree}").decode().strip(), "source_commit": source_commit, "source_tree": git("rev-parse", f"{source_commit}^{{tree}}").decode().strip(), "frontend_tree_source": git("rev-parse", f"{source_commit}:frontend").decode().strip(), "frontend_tree_head": git("rev-parse", "HEAD:frontend").decode().strip(), "files": files, "inputs": inputs, "checks": checks, "corrected_probe_sha256": hashlib.sha256((run_directory / "catalog_privacy.corrected.browser.spec.ts").read_bytes()).hexdigest(), "legacy_corrected_diff_exit": result.returncode, "legacy_corrected_diff_meaning": "exit 1 means different files, not a test failure", "previous_report_sha256": hashlib.sha256(Path("D:/dianzi/reports/reviews/recovery/G-C-R06-document-workspace-review-1-recheck.md").read_bytes()).hexdigest(), "previous_server_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd="D:/wt/r06-doc-recheck1").decode().strip(), "cbm": {"version": "0.11.0", "executable": "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "scope": "/mnt/d/wt/r06-doc-recheck2/frontend/src", "cache": "/tmp/r06-document-workspace-recheck2-cbm", "nodes": 292, "edges": 1090, "test_files_excluded": 21}}
(run_directory / "source_audit.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"source_files": len(files), "source_matches": all(item["same_after_crlf_normalization"] for item in files), "inputs_unchanged": all(item["same"] for item in inputs), "corrected_probe_sha256": record["corrected_probe_sha256"], "checks": checks}, ensure_ascii=False))
