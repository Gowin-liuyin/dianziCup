"""Collect immutable source and execution metadata without reading private configuration."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

candidate = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r01-candidate\dianzi")
artifact = Path(__file__).parent


def git(*arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=candidate, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


source_listing = git("ls-tree", "-r", "HEAD", "--", "backend/src", "frontend/src", "scripts")
required_reads = ["AGENTS.md", "prompts/12_full_delivery_parallel_push.txt", "docs/plan/00_execution_map.md", "docs/plan/02_architecture.md", "docs/plan/03_data_contracts.md", "docs/plan/05_api_and_tool_contracts.md", "docs/plan/06_testing_and_evaluation.md", "docs/plan/08_code_style.md", "docs/plan/09_operations_delivery.md", "docs/plan/12_recovery_task_cards_20261014.md", "docs/tasks/T02_project_skeleton.md", "docs/tasks/T03_development_services.md", "docs/tasks/T06_authentication_and_scope.md", "docs/tasks/T40_frontend_shell.md", "contracts/schemas/public_api_v2.json", "contracts/schemas/public_api_v2_examples.json", "contracts/task_manifest.json", "progress/task_state.json", "progress/context_handoff.md"]
required_reads.extend(f"docs/decisions/CR-R{number:02}.md" for number in range(1, 10))
read_hashes = {relative: hashlib.sha256((candidate / relative).read_bytes()).hexdigest() for relative in required_reads}
schema = json.loads((candidate / "contracts/schemas/public_api_v2.json").read_text(encoding="utf-8"))
counts = {"backend_unit": {"passed": 57, "failed": 0, "skipped": 0, "coverage_percent": 63.27, "coverage_floor_percent": 60}, "backend_security": {"passed": 27, "failed": 1, "skipped": 0}, "backend_contract_fixture": {"passed": 106, "failed": 0, "skipped": 0, "deselected": 1}, "script_contract_fixture": {"passed": 106, "failed": 0, "skipped": 0, "deselected": 1}, "frontend_test": {"passed": 30, "failed": 0, "skipped": 0}, "frontend_behavior_probe_initial": {"tests": 0, "errors": 1, "kind": "review harness environment selection error; not business failure"}, "frontend_behavior_probe": {"passed": 7, "failed": 1, "skipped": 0, "kind": "independent mocked HTTP boundary probes"}, "frontend_audit": {"moderate": 1, "critical": 2, "kind": "npm package advisories, no exploit executed"}, "backend_behavior_probe": {"probes": 47, "matched": 43, "mismatches": 4, "kind": "observations, not an additional unit-test pass total"}, "frontend_e2e_discovery": {"discovered": 3, "executed": 0, "kind": "list only; reporter skipped entries do not mean browser tests ran"}}
commands = []
for filename in artifact.glob("*.json"):
    if filename.name in {"commands.json", "snapshot.json", "backend_behavior_results.json"}:
        continue
    record = json.loads(filename.read_text(encoding="utf-8-sig"))
    if isinstance(record, dict) and "argv" in record:
        record["counts"] = counts.get(record["id"], {"tests": "not_applicable"})
        commands.append(record)
commands.sort(key=lambda item: (item["started_at"], item["id"]))
(artifact / "commands.json").write_text(json.dumps(commands, ensure_ascii=False, indent=2), encoding="utf-8")
snapshot = {"captured_at": datetime.now().astimezone().isoformat(timespec="seconds"), "candidate_root": str(candidate), "candidate_sha": git("rev-parse", "HEAD"), "candidate_tree": git("rev-parse", "HEAD^{tree}"), "branch": git("branch", "--show-current"), "git_status_short": git("status", "--short"), "baseline_sha": "f0b154ee0e10100bc9a9d293ebeded13926d0a42", "source_index_scopes": ["backend/src", "frontend/src", "scripts"], "source_index_listing_sha256": hashlib.sha256(source_listing.encode()).hexdigest(), "source_index_listing": source_listing.splitlines(), "required_read_sha256": read_hashes, "public_schema_definitions": list(schema.get("$defs", {})), "cbm_cache": "/tmp/dianzi-cbm-r01-behavior-review-1-20261014", "cbm_binary": "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cbm_version": "0.11.0", "command_records": len(commands), "verification_limits": {"integration": "not_run: real isolated PG/Redis/OpenSearch; closed local port is only negative HTTP readiness probe", "e2e": "not_run: discovery only", "live": "not_run: no provider/source/model APIs", "manual": "not_run: no browser/manual visual review"}}
(artifact / "snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({key: snapshot[key] for key in ("captured_at", "candidate_sha", "candidate_tree", "branch", "git_status_short", "source_index_listing_sha256", "command_records", "public_schema_definitions")}, ensure_ascii=False))
