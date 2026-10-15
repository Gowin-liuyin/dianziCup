"""Bind fixed frontend source and unmodified command receipts without reading secrets."""

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

directory = Path(__file__).resolve().parent
repository = directory.parents[2]
source_sha = "fccc0b918c58b18e66e8eb67cbfc8aadd4c1fb62"
baseline_sha = "31c2866ff19227e5f6ee24f1f966660c0d4ba383"
changed_files = subprocess.check_output(["git", "diff", "--name-only", baseline_sha, source_sha, "--", "frontend"], cwd=repository, text=True, encoding="utf-8").splitlines()
hashes = []
for relative_path in changed_files:
    working = (repository / relative_path).read_bytes().replace(b"\r\n", b"\n")
    committed = subprocess.check_output(["git", "show", f"{source_sha}:{relative_path}"], cwd=repository).replace(b"\r\n", b"\n")
    if working != committed:
        raise ValueError(f"Source differs from freeze: {relative_path}")
    hashes.append({"path": relative_path, "sha256_lf": hashlib.sha256(working).hexdigest()})

browser_runs = []
for label, sha in [("source-fixture-browser-first", "c9331835525d7470fdd022b1250b8a473ec1d95c"), ("source-fixture-browser-role-fix", "73e729db82404268871ff058cd3dcfd6a31bb32f"), ("source-fixture-browser-final", source_sha)]:
    log = (directory / f"{label}.log").read_text(encoding="utf-8")
    parsed, _ = json.JSONDecoder().raw_decode(log[log.index("{"):])
    observations = []
    for suite in parsed["suites"]:
        for spec in suite.get("specs", []):
            for test in spec["tests"]:
                for result in test["results"]:
                    for attachment in result.get("attachments", []):
                        if attachment["name"] == "fixture-request-observation":
                            observations.append(json.loads(base64.b64decode(attachment["body"])))
    browser_runs.append({"label": label, "source_sha": sha, "mode": "isolated fixture only", "stats": parsed["stats"], "request_observations": observations})

patterns = {"private_key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "aws_access_key": r"\bAKIA[0-9A-Z]{16}\b", "github_token": r"\b(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}\b", "openai_key": r"\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}\b"}
findings = []
text_files = [path for path in directory.rglob("*") if path.is_file() and path.suffix in {".log", ".json", ".jsonl", ".md"} and path.name != "evidence-summary.json"]
for path in text_files:
    for name, pattern in patterns.items():
        if re.search(pattern, path.read_text(encoding="utf-8")):
            findings.append({"file": str(path.relative_to(directory)), "pattern": name})
if findings:
    raise ValueError("Credential-shaped text found; no value printed")
summary = {
    "recorded_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
    "baseline_sha": baseline_sha, "source_sha": source_sha,
    "source_files": hashes, "browser_runs": browser_runs,
    "cbm": {"version": "0.11.0", "scope": "frontend/src only", "nodes": 188, "edges": 645, "partial": 0, "fast_excluded_tests": 13},
    "credential_pattern_scan": {"scope": "text receipts only, no real credentials injected; not a known-secret fragment scan", "files": len(text_files), "patterns": list(patterns), "findings": findings},
    "artifact_bytes_before_summary": sum(path.stat().st_size for path in directory.rglob("*") if path.is_file()),
    "implementation_status": "awaiting_review", "live": "not_run; controlled root real-admin test pending",
    "source_network_requests_by_author": 0, "product_model_calls_by_author": 0,
}
(directory / "evidence-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"source_sha": source_sha, "source_files": len(hashes), "browser_runs": len(browser_runs), "pattern_findings": len(findings), "artifact_bytes": summary["artifact_bytes_before_summary"]}, ensure_ascii=False))
staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=repository, text=True, encoding="utf-8").splitlines()
manifest = []
for relative in staged:
    if relative != "reports/tasks/R17-source-jobs.md" and not relative.startswith("reports/runs/recovery_r17_source_jobs_20261015/"):
        raise ValueError(f"Unexpected evidence staging path: {relative}")
    manifest.append({"path": relative, "sha256": hashlib.sha256((repository / relative).read_bytes()).hexdigest()})
(directory / "delivery-manifest.json").write_text(json.dumps({"source_sha": source_sha, "evidence_files_before_manifest": manifest, "state": "awaiting_review"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
