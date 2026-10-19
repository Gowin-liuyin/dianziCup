"""Seal review evidence and copy only the authorized report paths to the controller."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
MAIN = Path("D:/dianzi")
CODE = "456320b6c78e2936fd9f9767724ec3eb17f5c88b"
REPORT = ROOT / "reports/reviews/recovery/G-E-R18-public-extensions-review-1.md"
LOCAL_TIME = timezone(timedelta(hours=8))


def file_receipt(path: Path) -> dict[str, object]:
    content = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest()}


def main() -> None:
    command_receipts = []
    for path in sorted(RUN.glob("*.command.json")):
        command_receipts.append(json.loads(path.read_text(encoding="utf-8")))
    (RUN / "commands.json").write_text(json.dumps(command_receipts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    source_paths = [
        "AGENTS.md", "docs/plan/00_execution_map.md", "docs/plan/12_recovery_task_cards_20261014.md",
        "docs/plan/03_data_contracts.md", "docs/plan/04_workflows_and_algorithms.md",
        "docs/plan/05_api_and_tool_contracts.md", "docs/plan/06_testing_and_evaluation.md",
        "docs/plan/09_operations_delivery.md", "docs/tasks/T04_domain_contracts.md",
        "docs/tasks/T32_tool_gateway.md", "docs/tasks/T35_api_integration.md", "docs/tasks/T51_ci_cd_release_pipeline.md",
        "docs/decisions/CR-R09.md", "docs/decisions/CR-R18_public_envelopes_and_output_budget.md",
        "contracts/schemas/public_api_v2.json", "contracts/schemas/public_api_extensions_v1.json",
        "contracts/schemas/public_api_v2_examples.json", "backend/tests/contract/test_r18_public_extensions.py",
        "reports/tasks/R18-public-envelopes-output-budget.md", "progress/task_state.json", "progress/context_handoff.md",
        "backend/src/ai_intel/api/app.py", "backend/src/ai_intel/api/question_routes.py",
        "backend/src/ai_intel/api/job_routes.py", "backend/src/ai_intel/api/knowledge_contracts.py",
        "backend/src/ai_intel/api/question_contracts.py", "backend/src/ai_intel/api/document_contracts.py",
        "backend/src/ai_intel/answering/service.py", "frontend/src/api/question-client.ts",
        "frontend/src/api/source-client.ts", "frontend/src/api/question-contracts.ts",
    ]
    backend_tree = [file_receipt(path) for path in sorted((ROOT / "backend/src").rglob("*.py"))]
    source_manifest = {
        "code_sha": CODE, "scope": [file_receipt(ROOT / value) for value in source_paths],
        "cbm_source_scope": "backend/src only", "cbm_source_files": backend_tree,
        "cbm_source_manifest_sha256": hashlib.sha256(json.dumps(backend_tree, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "skill": {"path": "C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md",
                  "sha256": hashlib.sha256(Path("C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md").read_bytes()).hexdigest()},
        "external_reference": {"url": "https://www.first.org/cvss/v3.1/specification-document",
                               "section": "5 / Table 14", "read_at_date": "2026-10-16", "not_git_material": True},
    }
    (RUN / "source_scope.json").write_text(json.dumps(source_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    identity = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, check=False)
    if identity.returncode or identity.stdout.decode().strip() != CODE:
        raise RuntimeError("Review code identity changed")
    tracked = subprocess.run(["git", "diff", "--exit-code"], cwd=ROOT, capture_output=True, check=False)
    if tracked.returncode:
        raise RuntimeError("Tracked files changed during read-only review")
    manifest = {
        "schema_version": 1, "review_id": "G-E-R18-public-extensions-review-1",
        "reviewer": "/root/r18_public_extensions_first_independent_review", "reviewed_code_sha": CODE,
        "reviewed_range": CODE + "^.." + CODE, "verdict": "needs_changes_contract_slice_only",
        "must_fix": ["TaskDescriptor.poll_uri non-UUID tails accepted at schema line 1456"],
        "allowed_next_work": "Fix only the new pattern and add regression cases, freeze and independently recheck; producer/SDK/MCP implementation must preserve v2, opt in new profile, and enforce PG current evidence/ACL/scope and semantic safety gates. This is not R18/G-E acceptance.",
        "report_first_written_at": datetime.fromtimestamp(REPORT.stat().st_ctime, LOCAL_TIME).isoformat(),
        "sealed_at": datetime.now(LOCAL_TIME).isoformat(), "worktree": str(ROOT),
        "branch": "codex/r18-public-extensions-review1", "report": file_receipt(REPORT),
        "physical_pg_requests": 0, "paid_calls": 0, "cache_downloads": 0,
        "files": [file_receipt(path) for path in sorted(RUN.iterdir()) if path.is_file() and path.name != "manifest.json"],
    }
    (RUN / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_target = MAIN / REPORT.relative_to(ROOT)
    run_target = MAIN / RUN.relative_to(ROOT)
    if report_target.exists() or run_target.exists():
        raise RuntimeError("Controller output path already exists; refuse overwrite")
    report_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPORT, report_target)
    shutil.copytree(RUN, run_target)
    for record in [manifest["report"], *manifest["files"]]:
        copied = MAIN / record["path"]
        if hashlib.sha256(copied.read_bytes()).hexdigest() != record["sha256"]:
            raise RuntimeError("Copied evidence digest mismatch")
    print(json.dumps({"report_sha256": manifest["report"]["sha256"], "sealed_at": manifest["sealed_at"],
                      "report": str(report_target), "manifest": str(run_target / "manifest.json"),
                      "file_count_excluding_manifest": len(manifest["files"]), "copied_digests_verified": True}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
