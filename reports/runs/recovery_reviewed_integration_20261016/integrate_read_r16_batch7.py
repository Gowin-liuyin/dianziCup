"""显式整合独审通过的读取能力和完整重判切片，保留共享入口。"""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
BASELINE = "1315194a8ee421b7f1131a901221f31f4cacb536"


def git(directory, *arguments):
    return subprocess.check_output(["git", *arguments], cwd=directory)


def clock():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def strict_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


started = clock()
assert git(ROOT, "rev-parse", "HEAD").decode().strip() == BASELINE
assert not git(ROOT, "diff", "--cached", "--name-only").strip()
protected = ROOT / "frontend/tsconfig.tsbuildinfo"
protected_hash = hashlib.sha256(protected.read_bytes()).hexdigest()
assert protected_hash == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
r16_directory = Path("D:/wt/r16-runtime-cursor-fix1")
r16_source = "ca47f30fe31a662e55dd886adb2c56c626ca0950"
r16_inventory_path = "reports/runs/recovery_r16_root_input_closure_20261016/dependency_inventory.json"
r16_inventory_bytes = git(r16_directory, "show", "77707eb59c788b6bce2908a47722b942d78683ef:" + r16_inventory_path)
r16_inventory = json.loads(r16_inventory_bytes, object_pairs_hook=strict_pairs)
assert r16_inventory["root_input"] == BASELINE
assert r16_inventory["source_input"] == r16_source
r16_files = [
    "backend/src/ai_intel/revalidation/candidate_contracts.py",
    "backend/src/ai_intel/revalidation/candidates.py",
    "backend/src/ai_intel/revalidation/execution_contracts.py",
    "backend/src/ai_intel/revalidation/persistence_models.py",
    "backend/src/ai_intel/revalidation/runtime_policy.py",
    "backend/src/ai_intel/revalidation/service.py",
    "backend/tests/unit/test_r16_revalidation_runtime.py",
    "backend/tests/integration/test_r16_revalidation_runtime_pg.py",
    "backend/tests/integration/test_r16_current_scope_paging_pg.py",
]
read_files = [
    "backend/src/ai_intel/investigation/capabilities.py",
    "backend/src/ai_intel/investigation/tool_contracts.py",
    "backend/src/ai_intel/investigation/tool_gateway.py",
    "backend/src/ai_intel/investigation/read_adapters.py",
    "backend/tests/integration/test_r14_read_adapters_pg.py",
    "backend/tests/unit/test_r14_read_adapters.py",
]
shared_checks = []
for record in r16_inventory["records"]:
    relative = record["path"]
    if relative in r16_files:
        continue
    assert record["root_exists"], "shared required input missing: " + relative
    actual = git(ROOT, "rev-parse", BASELINE + ":" + relative).decode().strip()
    assert actual == record["root_git_blob_oid"], "root frozen input changed: " + relative
    if relative != "backend/src/ai_intel/api/app.py":
        assert record["root_relation"] == "same_git_bytes", "shared semantic conflict: " + relative
    shared_checks.append({"path": relative, "root_git_blob_oid": actual, "preserved": True})

read_directory = Path("C:/Users/yinha/.codex/worktrees/r14-shared-read-adapters/dianzi")
read_source = "42756702d5b0d61643f78bbc712af76f0e296cb7"
read_base = "cb868896c944a45f5fc39fc3f0072743e291e7e6"
packages = [(r16_directory, r16_source, r16_files, "R16"), (read_directory, read_source, read_files, "R14")]
pending = []
for directory, source, files, label in packages:
    for relative in files:
        assert not git(ROOT, "status", "--porcelain=v1", "--", relative).strip(), "protect existing changes: " + relative
        target = ROOT / relative
        raw = git(directory, "show", source + ":" + relative)
        oid = git(directory, "rev-parse", source + ":" + relative).decode().strip()
        before_sha256 = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
        if label == "R14" and target.exists():
            previous_oid = git(ROOT, "rev-parse", read_base + ":" + relative).decode().strip()
            assert git(ROOT, "rev-parse", BASELINE + ":" + relative).decode().strip() == previous_oid
        pending.append((target, raw, {"path": relative, "task": label, "source_sha": source, "git_blob_oid": oid, "canonical_sha256": hashlib.sha256(raw).hexdigest(), "before_working_sha256": before_sha256}))

entries = []
for target, raw, entry in pending:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    assert git(ROOT, "hash-object", "--path", entry["path"], str(target)).decode().strip() == entry["git_blob_oid"]
    entries.append(entry)
assert hashlib.sha256(protected.read_bytes()).hexdigest() == protected_hash
receipt = {"started_at": started, "ended_at": clock(), "root_baseline": BASELINE, "source_files": entries, "r16_frozen_input_inventory_sha256": hashlib.sha256(r16_inventory_bytes).hexdigest(), "r16_shared_inputs_preserved": shared_checks, "protected_buildinfo_sha256": protected_hash, "review_refs": {"R16": "D:/wt/r16-runtime-review1-fix1/reports/reviews/recovery/G-E-R16-runtime-review-1-fix1.md", "R14": "D:/wt/r14-read-adapters-review1/reports/reviews/recovery/G-D-R14-read-adapters-review-1.md"}, "tests": "not_run", "default_entry_wired": False, "stage_gate": "not_accepted; no push"}
(RUN / "read_r16_batch7_integration.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"integrated_paths": len(entries), "r16_shared_inputs_preserved": len(shared_checks), "protected_user_file_unchanged": True, "default_wired": False, "tests": "not_run"}))
