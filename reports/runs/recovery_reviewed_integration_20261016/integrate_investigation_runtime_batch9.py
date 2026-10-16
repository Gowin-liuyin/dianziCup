"""Import the full reviewed durable workflow and recovery closure, preserving the root app."""

import hashlib
import json
import subprocess
import difflib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
AUTHOR = Path("D:/wt/r14-terminal-outbox-fix1")
SOURCE = "e56ab6e0778352e746f48f1e5b753e09fc1b6a33"
QA_AUTHOR = Path("D:/wt/r14-qa-citation-real-trial")
QA_SOURCE = "c6b9442401ea748d4d2c8ccc04b8e53793d23791"


def git(directory, *arguments):
    return subprocess.check_output(["git", *arguments], cwd=directory)


def clock():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


started = clock()
paths = [
    "backend/src/ai_intel/api/investigation_routes.py",
    "backend/src/ai_intel/investigation/checkpoint_runtime.py",
    "backend/src/ai_intel/investigation/graph.py",
    "backend/src/ai_intel/investigation/graph_contracts.py",
    "backend/src/ai_intel/investigation/runtime.py",
    "backend/src/ai_intel/investigation/workflow_service.py",
    "backend/src/ai_intel/workers/investigation.py",
    "backend/src/ai_intel/workers/jobs.py",
    "backend/src/ai_intel/workers/runtime.py",
    "backend/src/ai_intel/infrastructure/outbox.py",
    "backend/tests/contract/test_r14_langgraph_workflow_contract.py",
    "backend/tests/integration/test_r14_default_runtime_pg.py",
    "backend/tests/integration/test_r14_langgraph_workflow_fix1_pg.py",
    "backend/tests/integration/test_r14_langgraph_workflow_pg.py",
    "backend/tests/integration/test_r14_preclaim_recovery_pg.py",
    "backend/tests/integration/test_r14_terminal_outbox_pg.py",
    "backend/tests/unit/test_r14_default_runtime.py",
    "backend/tests/unit/test_r14_langgraph_workflow.py",
    "backend/tests/unit/test_r14_langgraph_workflow_fix1.py",
    "backend/tests/unit/test_r14_preclaim_recovery.py",
    "backend/tests/unit/test_r14_terminal_outbox_selection.py",
    "backend/tests/contract/test_r14_qa_citation_prompt_wire_fix1.py",
    "backend/tests/unit/test_r14_qa_citation_prompt_fix1.py",
]
protected = ROOT / "frontend/tsconfig.tsbuildinfo"
protected_hash = hashlib.sha256(protected.read_bytes()).hexdigest()
if protected_hash != "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d":
    raise RuntimeError("protected user cache changed")
if git(ROOT, "diff", "--cached", "--name-only").strip():
    raise RuntimeError("preexisting staged changes")
pending = []
for relative in paths:
    if git(ROOT, "status", "--porcelain=v1", "--", relative).strip():
        raise RuntimeError("protect existing changes: " + relative)
    directory, source = (QA_AUTHOR, QA_SOURCE) if "qa_citation_prompt" in relative else (AUTHOR, SOURCE)
    raw = git(directory, "show", source + ":" + relative)
    target = ROOT / relative
    record = {"path": relative, "source_sha": source, "git_blob_oid": git(directory, "rev-parse", source + ":" + relative).decode().strip(), "raw_sha256": hashlib.sha256(raw).hexdigest(), "before_raw_sha256": hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None}
    pending.append((target, raw, record))
records = []
for target, raw, record in pending:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    if git(ROOT, "hash-object", "--path", record["path"], str(target)).decode().strip() != record["git_blob_oid"]:
        raise RuntimeError("imported blob mismatch")
    records.append(record)
workflow_path = "backend/src/ai_intel/investigation/workflow_service.py"
before_qa = git(AUTHOR, "show", "b8b75bf8bd7730f7be85e7f45a0502c41f17c0fe:" + workflow_path)
after_qa = git(QA_AUTHOR, "show", QA_SOURCE + ":" + workflow_path)
qa_patch = "".join(difflib.unified_diff(before_qa.decode().splitlines(keepends=True), after_qa.decode().splitlines(keepends=True), fromfile="a/" + workflow_path, tofile="b/" + workflow_path)).encode()
patch_path = RUN / "qa_prompt_batch9_exact_reviewed_delta.patch"
patch_path.write_bytes(qa_patch)
for arguments in (["git", "apply", "--check", str(patch_path)], ["git", "apply", str(patch_path)]):
    result = subprocess.run(arguments, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    (RUN / ("qa_prompt_batch9_check.log" if "--check" in arguments else "qa_prompt_batch9_apply.log")).write_bytes(result.stdout)
    if result.returncode:
        raise RuntimeError("QA reviewed delta failed to integrate; preserve recovery source")
if hashlib.sha256(protected.read_bytes()).hexdigest() != protected_hash:
    raise RuntimeError("protected user cache changed during import")
receipt = {"started_at": started, "ended_at": clock(), "baseline_sha": git(ROOT, "rev-parse", "HEAD").decode().strip(), "records": records, "reviewed_recovery_material": "77b6a6170d479dce326cd8c0f8c1014114b2e322", "qa_review_material": "8fa76962df1f458274ad0d923ba2d2a38a74d714", "qa_delta_sha256": hashlib.sha256(qa_patch).hexdigest(), "merged_workflow_sha256": hashlib.sha256((ROOT / workflow_path).read_bytes()).hexdigest(), "qa_delta_preserves_ff7_recovery_source": True, "preserved_shared_current_sources": ["api/app.py", "infrastructure/settings.py", "ingestion/source_documents.py", "assessment/assessment_service.py", "recommendations/", "investigation/read_adapters.py", "investigation/tool_gateway.py", "investigation/tool_contracts.py", "investigation/capabilities.py"], "default_mount": "not_run", "main_dependency_sync": "not_run", "root_validation": "not_run", "stage_gate": "not_accepted", "push": "not_run"}
(RUN / "investigation_runtime_batch9_integration.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"exact_imported_paths": len(records), "root_default_app_preserved": True, "current_source_proof_preserved": True}))
