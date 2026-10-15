"""Bind recorded fixture checks to exact source files without reading credentials."""

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

directory = Path(__file__).resolve().parent
repository = directory.parents[2]
source_sha = "471c54760e8fe016fcd26aca89d17a334d7b0303"
paths = subprocess.check_output(
    ["git", "diff", "--name-only", "cafbe7f", source_sha, "--", "frontend"],
    cwd=repository, text=True, encoding="utf-8",
).splitlines()
source_files = []
for relative_path in paths:
    content = (repository / relative_path).read_bytes()
    committed = subprocess.check_output(["git", "show", f"{source_sha}:{relative_path}"], cwd=repository)
    normalized = content.replace(b"\r\n", b"\n")
    if normalized != committed.replace(b"\r\n", b"\n"):
        raise ValueError(f"Working source differs from frozen source: {relative_path}")
    source_files.append({"path": relative_path, "sha256_lf": hashlib.sha256(normalized).hexdigest()})

browser_results = []
for label, sha in [
    ("r04-fixture-browser-first", "2363fc4389ee80500a06bd73b7e37f9e374a9458"),
    ("r04-fixture-browser-count-fix", "6e42c9242e8af067ee14e39c585e801220ab0dd7"),
    ("r04-fixture-browser-focus-final", source_sha),
]:
    log = (directory / f"{label}.log").read_text(encoding="utf-8")
    parsed, _ = json.JSONDecoder().raw_decode(log[log.index("{"):])
    attachments = []
    for suite in parsed["suites"]:
        for spec in suite.get("specs", []):
            for test in spec["tests"]:
                for result in test["results"]:
                    for attachment in result.get("attachments", []):
                        if attachment["name"] == "fixture-401-request-counts":
                            attachments.append(json.loads(base64.b64decode(attachment["body"])))
    browser_results.append({"label": label, "source_sha": sha, "mode": "isolated fixture only", "stats": parsed["stats"], "request_counts": attachments})

patterns = {
    "private_key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "aws_access_key": r"\bAKIA[0-9A-Z]{16}\b",
    "github_token": r"\b(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}\b",
    "openai_key": r"\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}\b",
}
findings = []
for path in directory.rglob("r04*.log"):
    log = path.read_text(encoding="utf-8")
    for pattern_name, pattern in patterns.items():
        if re.search(pattern, log):
            findings.append({"path": path.name, "pattern": pattern_name})
if findings:
    raise ValueError("Unexpected credential-shaped text in R04 logs")

summary = {
    "recorded_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
    "source_sha": source_sha,
    "contract_sha": "099c5b1af4cea9df9f6c72894ee36782b7f4c8c3",
    "source_files": source_files,
    "browser_results": browser_results,
    "cbm": {"scope": "frontend/src only", "version": "0.11.0", "nodes": 151, "edges": 505, "partial": 0, "tests_excluded_by_fast_mode": 9},
    "credential_pattern_scan": {"findings": findings, "pattern_names": list(patterns), "scope": "R04 text logs only; no real account injected; not a known-secret fragment scan"},
    "live": "not_run: business routes and controlled real session regression await backend integration",
    "manual_hidden_page": "blocked: previous native visibility probe remained visible",
    "review": "awaiting_review",
}
(directory / "r04-evidence-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"source_sha": source_sha, "source_files": len(source_files), "browser_runs": len(browser_results), "credential_pattern_findings": len(findings)}, ensure_ascii=False))
staged_paths = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=repository, text=True, encoding="utf-8").splitlines()
manifest_files = []
for staged_path in staged_paths:
    if not (staged_path.startswith("reports/runs/recovery_hacker_ui_20261015/") or staged_path in ["docs/design/recovery_hacker_workbench.md", "reports/tasks/R17-frontend-preparation.md"]):
        raise ValueError(f"Unexpected file in evidence staging: {staged_path}")
    manifest_files.append({"path": staged_path, "sha256": hashlib.sha256((repository / staged_path).read_bytes()).hexdigest()})
(directory / "r04-delivery-manifest.json").write_text(json.dumps({"source_sha": source_sha, "evidence_files_before_manifest": manifest_files, "state": "awaiting_review"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
