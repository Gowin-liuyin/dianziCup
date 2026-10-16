"""Freeze explicit reviewed inputs and root wiring as a non-stage checkpoint."""

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
PYTHON = ROOT / "backend/.venv/Scripts/python.exe"


def clock():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def command(label, arguments):
    started = clock()
    result = subprocess.run(arguments, cwd=ROOT, capture_output=True, timeout=120)
    (RUN / (label + ".log")).write_bytes(result.stdout + result.stderr)
    receipt = {"started_at": started, "ended_at": clock(), "command": arguments, "cwd": str(ROOT), "exit_code": result.returncode}
    receipts.append(receipt)
    print(json.dumps({"label": label, "exit_code": result.returncode}), flush=True)
    if result.returncode:
        raise RuntimeError("checkpoint blocked: " + label)
    return result.stdout


started = clock()
receipts = []
if subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT).strip():
    raise RuntimeError("existing staged files; refusing to include unknown work")
protected_hash = hashlib.sha256((ROOT / "frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest()
if protected_hash != "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d":
    raise RuntimeError("protected user file hash changed")
source = json.loads((RUN / "investigation_runtime_batch9_integration.json").read_text())
paths = {entry["path"] for entry in source["records"]}
paths.update({
    "backend/src/ai_intel/api/app.py",
    "backend/tests/contract/test_r14_default_investigation_mount.py",
    "backend/tests/unit/test_r16_default_worker_registration.py",
    "reports/runs/recovery_r14_qa_citation_prompt_fix1_20261016/old_trial_probe_result.json",
    "docs/decisions/CR-R18_public_read_identity_bindings.md",
    "reports/tasks/R14.md",
    "progress/task_state.json", "progress/context_handoff.md",
    "progress/recovery_workstreams.md", "progress/blockers.md",
    "reports/stages/recovery/G-D.md", "reports/stages/recovery/G-E.md", "reports/stages/recovery/G-F.md",
})
names = [
    "integrate_investigation_runtime_batch9.py", "investigation_runtime_batch9_integration.json",
    "check_investigation_runtime_batch9.py", "investigation_batch9_check_receipts.json",
    "investigation_batch9_offline.json", "investigation_batch9_offline.log", "investigation_batch9_offline.xml",
    "investigation_batch9_mypy.json", "investigation_batch9_mypy.log",
    "qa_prompt_batch9_exact_reviewed_delta.patch", "qa_prompt_batch9_check.log", "qa_prompt_batch9_apply.log",
    "restore_qa_prompt_input_batch9.py", "qa_prompt_input_closure_batch9.json",
    "investigation_batch9_inputfix_worker.xml", "main_langgraph_semantic_sync.json", "main_langgraph_semantic_sync.log",
    "refresh_investigation_batch9_index.py", "investigation_batch9_index_source_files.json",
    "investigation_batch9_cbm_receipts.json", "investigation_batch9_cbm_index.log",
    "investigation_batch9_cbm_schema.log", "investigation_batch9_cbm_architecture.log",
    "investigation_batch9_cbm_workflow_tool.log", "investigation_batch9_cbm_default_consumer.log",
    "update_parallel_continuity_batch9.py", "parallel_continuity_batch9.json",
    "write_investigation_batch9_report.py", "investigation_batch9_report_receipt.json",
    "freeze_investigation_checkpoint_batch9.py",
]
paths.update((RUN / name).relative_to(ROOT).as_posix() for name in names)
try:
    for relative in paths:
        path = ROOT / relative
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("unexpected checkpoint input: " + relative)
    command("investigation_batch9_explicit_add", ["git", "add", "--", *sorted(paths)])
    staged = set(subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"], cwd=ROOT).decode().split("\0")) - {""}
    if not staged <= paths or "frontend/tsconfig.tsbuildinfo" in staged:
        raise RuntimeError("unexpected staged ownership")
    command("investigation_batch9_staged_boundary", [str(PYTHON), "-I", str(RUN / "check_staged_boundary.py")])
    command("investigation_batch9_staged_diff_check", ["git", "diff", "--cached", "--check"])
    command("investigation_batch9_checkpoint_commit", ["git", "commit", "-m", "checkpoint G-D: mount durable investigations and recovery dispatch; partial validation"])
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    outcome = "committed checkpoint; awaiting independent default integration review; no stage acceptance or push"
except Exception as error:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    outcome = "blocked before checkpoint completion: " + type(error).__name__
    raise
finally:
    receipt = {"started_at": started, "ended_at": clock(), "result": outcome, "head_sha": head, "explicit_paths": sorted(paths), "commands": receipts, "protected_user_file_sha256": protected_hash, "push": "not_run", "stage_accepted": False}
    (RUN / "investigation_batch9_checkpoint_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"head_sha": head, "result": outcome}), flush=True)
