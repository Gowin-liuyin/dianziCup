"""Preserve raw Git bytes, worktree hashes, checks and review-only evidence."""

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess

workspace = Path("D:/wt/r06-doc-review1")
run_directory = workspace / "reports/runs/recovery_r06_document_workspace_review_1_20261015"
source_commit = "aa17db32c314555363bb4bca3105c2b434939b29"
metadata_commit = "475f71e48f93e9888dfcf09954a7ce13e590add5"
baseline_commit = "1ca2ea34c224e23776431fa6eac5fe6549d8c65f"


def git(*arguments: str) -> bytes:
    """Read exact subprocess output without shell text encoding conversion."""
    return subprocess.check_output(["git", *arguments], cwd=workspace)


paths = git("diff", "--name-only", baseline_commit, source_commit, "--", "frontend", "docs/design/recovery/r06_document_workspace.md").decode().splitlines()
source_files = []
for relative in paths:
    raw_blob = git("show", f"{source_commit}:{relative}")
    worktree_bytes = (workspace / relative).read_bytes()
    source_files.append({
        "path": relative,
        "blob_id": git("rev-parse", f"{source_commit}:{relative}").decode().strip(),
        "git_raw_bytes": len(raw_blob), "git_raw_sha256": hashlib.sha256(raw_blob).hexdigest(),
        "worktree_bytes": len(worktree_bytes), "worktree_sha256": hashlib.sha256(worktree_bytes).hexdigest(),
        "git_crlf": raw_blob.count(b"\r\n"), "worktree_crlf": worktree_bytes.count(b"\r\n"),
        "equal_after_crlf_normalization": raw_blob.replace(b"\r\n", b"\n") == worktree_bytes.replace(b"\r\n", b"\n"),
    })
checks = []
for label, final, pathspec in [
    ("source_diff_check", source_commit, ["frontend", "docs/design/recovery/r06_document_workspace.md", "reports/tasks/R06-document-workspace.md"]),
    ("whole_metadata_diff_check", metadata_commit, []),
]:
    arguments = ["git", "diff", "--check", baseline_commit, final, "--", *pathspec]
    result = subprocess.run(arguments, cwd=workspace, capture_output=True)
    (run_directory / f"{label}.log").write_bytes(result.stdout + result.stderr)
    checks.append({"command": arguments, "exit": result.returncode, "output_bytes": len(result.stdout + result.stderr)})
contract_paths = ["docs/decisions/CR-R04-R06_document_read_api.md", "backend/src/ai_intel/api/document_contracts.py"]
contracts = []
for relative in contract_paths:
    contract_bytes = git("show", f"225c0fcd501d85d355513a44308083407b18bb2a:{relative}")
    current_bytes = (Path("D:/wt/r06-integration") / relative).read_bytes()
    contracts.append({"path": relative, "frozen_commit": "225c0fcd501d85d355513a44308083407b18bb2a", "raw_sha256": hashlib.sha256(contract_bytes).hexdigest(), "root_worktree_sha256": hashlib.sha256(current_bytes).hexdigest(), "same_after_crlf_normalization": contract_bytes.replace(b"\r\n", b"\n") == current_bytes.replace(b"\r\n", b"\n")})
metadata = {
    "recorded_at": datetime.now().astimezone().isoformat(), "workspace": str(workspace),
    "head": git("rev-parse", "HEAD").decode().strip(), "head_tree": git("rev-parse", "HEAD^{tree}").decode().strip(),
    "source_commit": source_commit, "source_tree": git("rev-parse", f"{source_commit}^{{tree}}").decode().strip(),
    "frontend_tree_source": git("rev-parse", f"{source_commit}:frontend").decode().strip(),
    "frontend_tree_head": git("rev-parse", "HEAD:frontend").decode().strip(),
    "source_files": source_files, "contracts": contracts, "diff_checks": checks,
    "metadata_only_document_change": "docs/design/recovery/r06_document_workspace.md differs between aa17 and 475f by intentional freeze metadata; frontend trees are identical",
    "cbm": {"executable": "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "version": "0.11.0", "cache": "/tmp/r06-document-workspace-review1-cbm", "scope": "/mnt/d/wt/r06-doc-review1/frontend/src", "mode": "fast", "nodes": 288, "edges": 1074, "test_files_excluded_by_tool": 19},
}
(run_directory / "source_audit.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"source_files": len(source_files), "all_frontend_source_bytes_match_after_normalization": all(item["equal_after_crlf_normalization"] for item in source_files if item["path"].startswith("frontend/")), "checks": checks}, ensure_ascii=False))
