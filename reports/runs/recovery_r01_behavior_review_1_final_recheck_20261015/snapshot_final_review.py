"""Capture immutable source identity and summarize independent versus controller evidence."""

import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

candidate = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r01-recheck-final\dianzi")
artifact = Path(__file__).parent
controller = Path(r"D:\dianzi\reports\runs\recovery_r01_controller_20261014")


def git(*arguments):
    return subprocess.run(["git", *arguments], cwd=candidate, capture_output=True, text=True, check=True).stdout.strip()


counts = {"backend_unit": {"passed": 59, "skipped": 0, "coverage_percent": 64.00, "unit_floor": 60}, "backend_security": {"passed": 63, "failed": 0, "skipped": 0}, "frontend_test": {"passed": 42, "failed": 0, "skipped": 0}, "backend_contract_fixture": {"passed": 108, "failed": 0, "skipped": 0, "deselected": 1}, "independent_security_and_login_probe": {"passed": 12, "failed": 0, "kind": "8 classification methods with parameterized subtests + 4 login methods, synthetic input only"}, "visitor_browser_probe": {"executed_ui_cases": 0, "kind": "missing browser at default cache; not a business failure"}, "visitor_browser_probe_private_cache": {"passed": 2, "failed": 0, "kind": "real browser with controlled HTTP, visitor only", "environment_overrides": {"PLAYWRIGHT_BROWSERS_PATH": "C:\\Users\\yinha\\.codex\\cache\\dianzi\\r01_playwright_1248"}}, "classification_provenance": {"kind": "missing retained log in candidate WT; not business failure"}, "classification_provenance_main_evidence": {"records": 36, "paths": 7, "kind": "candidate plus hash-pinned retained main evidence; no copies into WT"}}
commands = []
for path in artifact.glob("*.json"):
    if path.name in {"snapshot.json", "commands.json", "classification_provenance.json", "visitor_browser_receipt.json", "controller_receipts.json"}:
        continue
    record = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(record, dict) and "argv" in record:
        record["counts"] = counts.get(record["id"], {"tests": "not_applicable"})
        commands.append(record)
commands.sort(key=lambda entry: (entry["started_at"], entry["id"]))
(artifact / "commands.json").write_text(json.dumps(commands, ensure_ascii=False, indent=2), encoding="utf-8")
receipts = {}
for filename in ("classifier_actual_secrets_candidate.json", "classifier_actual_secrets_candidate.command.json", "browser_e2e_retry_4.command.json", "browser_e2e_retry_4.xml", "browser_e2e_retry_4.stdout.log", "browser_e2e_retry_4.stderr.log"):
    receipts[filename] = {"path": str(controller / filename), "raw_sha256": hashlib.sha256((controller / filename).read_bytes()).hexdigest()}
exact = json.loads((controller / "classifier_actual_secrets_candidate.json").read_text(encoding="utf-8-sig"))
exact_command = json.loads((controller / "classifier_actual_secrets_candidate.command.json").read_text(encoding="utf-8-sig"))
browser_command = json.loads((controller / "browser_e2e_retry_4.command.json").read_text(encoding="utf-8-sig"))
receipts["exact_summary"] = {"actor": "controller, not this independent reviewer", "candidate_sha": exact_command["candidate_sha"], "started_at": exact_command["started_at"], "ended_at": exact_command["ended_at"], "exit_code": exact_command["exit_code"], "exact_secret_refs": exact_command["exact_secret_refs"], "exact_scan": exact["exact_scan"], "credential_values_in_output": exact_command["credential_values_in_output"], "finding_categories": dict(Counter(item["category"] for item in exact["findings"]))}
receipts["authenticated_browser_summary"] = {"actor": "controller, not this independent reviewer", **{name: browser_command[name] for name in ("started_at", "ended_at", "elapsed_seconds", "cwd", "frontend_code_sha", "backend_code_sha", "exit_code", "trace_video_failure_screenshot")}, "tests": 3, "failed": 0, "errors": 0, "skipped": 0}
(artifact / "controller_receipts.json").write_text(json.dumps(receipts, ensure_ascii=False, indent=2), encoding="utf-8")
listing = git("ls-tree", "-r", "HEAD", "--", "backend/src", "frontend/src", "scripts")
provenance = json.loads((artifact / "classification_provenance.json").read_text())
snapshot = {"captured_at": datetime.now().astimezone().isoformat(timespec="seconds"), "candidate_root": str(candidate), "candidate_sha": git("rev-parse", "HEAD"), "candidate_tree": git("rev-parse", "HEAD^{tree}"), "branch": git("branch", "--show-current"), "git_status_short": git("status", "--short"), "baseline": "fd4f1d42e1ad2e39ff7c80897fd50511c3faf299", "source_index_scopes": ["backend/src", "frontend/src", "scripts"], "source_index_listing_sha256": hashlib.sha256(listing.encode()).hexdigest(), "source_index_listing": listing.splitlines(), "classification_target_locations_by_record": dict(Counter(row["target_location"] for row in provenance["records"])), "cbm_cache": "/tmp/dianzi-cbm-r01-final-d30eeab-20261015", "cbm_version": "0.11.0", "command_records": len(commands), "limits": {"actual_secret_exact_scan_by_reviewer": "not_run; controller receipt separately verified", "authenticated_browser_by_reviewer": "not_run; controller receipt separately verified", "pg_redis_search_worker_cross_process_session_live_providers": "not_run by reviewer", "runtime_tls_tmpfs_deployment": "not_reviewed here", "dependency_issue_4": "still open in this frozen candidate"}}
(artifact / "snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({name: snapshot[name] for name in ("captured_at", "candidate_sha", "candidate_tree", "git_status_short", "source_index_listing_sha256", "classification_target_locations_by_record", "command_records")}))
