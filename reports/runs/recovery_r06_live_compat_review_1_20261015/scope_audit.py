"""Freeze this review's code, contract inputs and author evidence identities."""

import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
BASE = "1a52e17ffe327fb8a0c1d4f97372948a699910e3"
CODE = "e900cd6b95dde7c6fe8d11d8c15122eb48a4acdc"
MATERIAL = "837fd22e655e6f2fb39eaf828e6ad91a78914ba4"


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, encoding="utf-8", check=True)
    return result.stdout.strip()


paths = git("diff", "--name-only", BASE, CODE).splitlines()
assert paths == ["backend/src/ai_intel/ingestion/catalog_pages.py", "backend/src/ai_intel/ingestion/sources/avid_records.py",
                 "backend/src/ai_intel/ingestion/sources/github_releases.py", "backend/tests/unit/test_r06_live_source_compatibility.py"]
assert git("rev-parse", "HEAD") == MATERIAL
assert not git("diff", "--name-only", CODE, "HEAD", "--", "backend/src", "backend/tests")
assert not git("diff", "--name-only", "--", "backend/src", "backend/tests", "progress", "contracts")
source_identity = []
for relative in paths:
    file = ROOT / relative
    blob = git("hash-object", relative)
    expected = git("rev-parse", CODE + ":" + relative)
    assert blob == expected
    source_identity.append({"path": relative, "git_blob": blob, "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "size_bytes": file.stat().st_size})
contracts = ["AGENTS.md", "docs/plan/00_execution_map.md", "docs/plan/03_data_contracts.md", "docs/plan/05_api_and_tool_contracts.md",
             "docs/plan/06_testing_and_evaluation.md", "docs/plan/11_full_delivery_recovery_20261014.md", "docs/plan/12_recovery_task_cards_20261014.md",
             "docs/tasks/T12_vendor_blog_connectors.md", "docs/tasks/T14_academic_connector.md", "docs/tasks/T16_incremental_monitoring.md",
             "docs/plan/04_workflows_and_algorithms.md", "docs/plan/07_sources_and_resources.md", "docs/plan/09_operations_delivery.md",
             "progress/task_state.json", "progress/context_handoff.md", "contracts/task_manifest.json",
             "reports/tasks/R06-live-compat-fix.md", "reports/runs/recovery_r06_live_compat_fix_20261015/fix_manifest.json"]
receipt = {"at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"), "base_sha": BASE, "code_sha": CODE, "material_sha": MATERIAL,
           "branch": git("branch", "--show-current"), "worktree": str(ROOT), "product_unchanged": True, "source_identity": source_identity,
           "inputs": [{"path": p, "sha256": hashlib.sha256((ROOT / p).read_bytes()).hexdigest()} for p in contracts],
           "skill": {"path": "C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md",
                     "sha256": hashlib.sha256(Path("C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md").read_bytes()).hexdigest()},
           "status": git("status", "--short")}
(RUN / "scope_audit.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(json.dumps({"at": receipt["at"], "product_unchanged": True, "changed_product_paths": len(paths), "contract_inputs": len(contracts)}))
