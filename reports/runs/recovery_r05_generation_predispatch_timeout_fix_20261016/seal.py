"""固定本轮输入与材料的原始字节哈希，不改变验证状态或产品源码。"""

import hashlib
import importlib.metadata
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
CODE_SHA = "47c47bc2b5d537166ee47a01c2ab14c035466e3d"
REPORT = RUN / "report.md"
stamp = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != CODE_SHA:
    raise RuntimeError("seal requires the frozen code commit")
manifest_path = RUN / "artifact_manifest.json"
if manifest_path.exists():
    raise FileExistsError("manifest already sealed")
input_files = [
    ROOT / "AGENTS.md", ROOT / "docs/plan/00_execution_map.md",
    ROOT / "docs/plan/03_data_contracts.md", ROOT / "docs/plan/05_api_and_tool_contracts.md",
    ROOT / "docs/plan/12_recovery_task_cards_20261014.md",
    ROOT / "docs/tasks/T18_model_clients.md", ROOT / "docs/tasks/T31_grounded_qa_baseline.md",
    ROOT / "progress/task_state.json", ROOT / "backend/uv.lock",
    ROOT / "backend/src/ai_intel/infrastructure/models/clients.py",
    ROOT / "backend/src/ai_intel/infrastructure/models/semantic.py",
    ROOT / "backend/src/ai_intel/answering/grounding.py",
    ROOT / "backend/src/ai_intel/answering/service.py",
    ROOT / "backend/src/ai_intel/infrastructure/settings.py", ROOT / "config/models/providers.yaml",
    Path("C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail/SKILL.md"),
    Path("C:/Users/yinha/.codex/worktrees/r09-knowledge-cards/dianzi/backend/src/ai_intel/enrichment/card_extraction.py"),
    Path("D:/wt/r07-model-fields-two-root-causes-fix/backend/src/ai_intel/enrichment/model_fields.py"),
]


def byte_record(path: Path) -> dict[str, str | int]:
    contents = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(contents).hexdigest(), "bytes": len(contents)}


source_tree = subprocess.check_output(["git", "ls-tree", "-r", CODE_SHA, "--", "backend/src"], cwd=ROOT)
changed = subprocess.check_output(["git", "diff", "--name-only", "595a13197a2c1bba6ad79957f8fde3750ba2a6c6", CODE_SHA], cwd=ROOT, text=True).splitlines()
expected = ["backend/src/ai_intel/infrastructure/models/generation.py", "backend/tests/unit/test_r05_generation_predispatch_timeout.py"]
if changed != expected:
    raise RuntimeError("product scope does not match the authorized two files")
inputs = {"recorded_at": stamp, "code_sha": CODE_SHA, "source_tree_binding_sha256": hashlib.sha256(source_tree).hexdigest(), "source_index_path": "/mnt/d/wt/gen-timeout/backend/src", "cbm_cache_path": "/tmp/dianzi-cbm-r05-predispatch-timeout-fix-20261016", "read_inputs": [byte_record(path) for path in input_files], "changed_product_files": changed, "python_version": sys.version, "installed_distributions": len(list(importlib.metadata.distributions())), "unexecuted_scopes": ["integration", "frontend", "e2e", "live", "manual"], "scope_status": "awaiting_review"}
for path in ["C:/Users/yinha/.codex/worktrees/r09-knowledge-cards/dianzi", "D:/wt/r07-model-fields-two-root-causes-fix"]:
    inputs.setdefault("read_only_sibling_commits", {})[path] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
(RUN / "scope_inputs.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
REPORT.write_text(REPORT.read_text(encoding="utf-8").replace("2026-10-16T02:15:00+08:00", stamp), encoding="utf-8")
attribute = "reports/runs/recovery_r05_generation_predispatch_timeout_fix_20261016/** -text\n"
with (ROOT / ".gitattributes").open("a", encoding="utf-8", newline="") as stream:
    stream.write(attribute)
results = []
for path in sorted(RUN.glob("*.json")):
    record = json.loads(path.read_text(encoding="utf-8"))
    if "command" in record:
        results.append({"record": path.name, "label": record["label"], "exit_code": record["exit_code"], "source_sha": record["source_sha"], "pytest": record.get("pytest")})
artifacts = sorted([path for path in RUN.rglob("*") if path.is_file()], key=str)
manifest = {"schema_version": 1, "recorded_at": stamp, "base_sha": "595a13197a2c1bba6ad79957f8fde3750ba2a6c6", "code_sha": CODE_SHA, "status": "awaiting_review", "verification": {"unit": "passed", "contract": "passed", "security": "passed", "integration": "not_run", "frontend": "not_run", "e2e": "not_run", "live": "not_run", "manual": "not_run"}, "commands": results, "artifacts": [{**byte_record(path), "path": path.relative_to(ROOT).as_posix()} for path in artifacts], "manifest_self_excluded": True, "fee": "unknown", "real_provider_calls": 0, "notes": ["All provider keys are synthetic fixtures; no live capability claimed.", "R07/R09 sibling caller code was read only and is not part of the candidate source tree.", "No author acceptance, push, database or browser operations."]}
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
for entry in manifest["artifacts"]:
    if hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest() != entry["sha256"]:
        raise RuntimeError("sealed artifact changed")
print(json.dumps({"manifest": str(manifest_path), "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(), "artifacts": len(artifacts), "recorded_at": stamp}, ensure_ascii=False))
