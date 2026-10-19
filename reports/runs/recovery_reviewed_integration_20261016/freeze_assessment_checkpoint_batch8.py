"""Stage an explicit tested checkpoint, and commit only after both boundary checks succeed."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
PYTHON = ROOT / "backend/.venv/Scripts/python.exe"


def clock():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def execute(label, arguments):
    started = clock()
    result = subprocess.run(arguments, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    (RUN / (label + ".log")).write_bytes(result.stdout)
    (RUN / (label + ".json")).write_text(json.dumps({"started_at": started, "ended_at": clock(), "command": arguments, "cwd": str(ROOT), "exit_code": result.returncode}, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"label": label, "exit_code": result.returncode}), flush=True)
    return result.returncode


if subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT).strip():
    raise RuntimeError("preexisting staged changes require explicit inspection")
for name in ("assessment_batch8_check_receipts.json", "assessment_frontend_batch8_receipts.json"):
    receipts = json.loads((RUN / name).read_text(encoding="utf-8"))
    for item in receipts:
        if item["label"] == "assessment_frontend_batch8_typecheck" and item["exit_code"] == 2:
            fixed = json.loads((RUN / "assessment_frontend_batch8_typecheck_fix1.json").read_text(encoding="utf-8"))
            if fixed["exit_code"] == 0 and not fixed["timed_out"] and fixed["original_typecheck_error_preserved"]:
                continue
        if item["exit_code"] != 0 or item["timed_out"]:
            raise RuntimeError("candidate validation failed")
paths = []
for name, key in (
    ("read_r16_batch7_integration.json", "source_files"),
    ("assessment_package_batch8_integration.json", "records"),
    ("assessment_frontend_batch8_integration.json", "records"),
):
    record = json.loads((RUN / name).read_text(encoding="utf-8"))
    paths.extend(item["path"] for item in record[key])
paths.extend([
    ".gitattributes", "backend/src/ai_intel/api/app.py", "backend/src/ai_intel/infrastructure/settings.py",
    "backend/tests/unit/test_r16_cursor_settings.py", "backend/tests/contract/test_r11_default_assessment_mount.py",
    "frontend/src/App.tsx", "frontend/src/App.assessment.test.tsx", "frontend/src/app/workspace-navigation.ts",
    "frontend/src/features/preparation/capability-workspace.tsx",
    "docs/decisions/CR-R11_assessment_http_projection.md", "docs/decisions/CR-R16_persisted_cursor_configuration.md",
    "docs/decisions/CR-R18_public_read_identity_bindings.md", "docs/decisions/CR-R06_reprepared_nine_script_binding.md",
    "progress/task_state.json", "progress/context_handoff.md", "progress/blockers.md", "progress/recovery_workstreams.md",
    "reports/stages/recovery/G-C.md", "reports/stages/recovery/G-D.md", "reports/stages/recovery/G-E.md",
    "reports/stages/recovery/G-F.md", "reports/stages/recovery/G-G.md",
    "reports/reviews/recovery/G-C-R19-preparation-review-1-recheck.md",
])
run_files = [
    "integrate_read_r16_batch7.py", "read_r16_batch7_integration.json", "check_read_r16_batch7.py",
    "read_batch7_offline.json", "read_batch7_offline.log", "read_batch7_offline.xml",
    "r16_batch7_offline.json", "r16_batch7_offline.log", "r16_batch7_offline.xml",
    "integrate_assessment_package_batch8.py", "assessment_package_batch8_integration.json",
    "integrate_assessment_frontend_batch8.py", "assessment_frontend_batch8_integration.json",
    "check_assessment_default_batch8.py", "assessment_batch8_check_receipts.json",
    "assessment_batch8_offline.json", "assessment_batch8_offline.log", "assessment_batch8_offline.xml",
    "assessment_batch8_ruff.json", "assessment_batch8_ruff.log", "assessment_batch8_format.json", "assessment_batch8_format.log",
    "assessment_batch8_mypy.json", "assessment_batch8_mypy.log",
    "check_frontend_assessment_batch8.py", "assessment_frontend_batch8_receipts.json",
    "assessment_frontend_batch8_unit.json", "assessment_frontend_batch8_unit.log", "assessment_frontend_batch8_unit.xml",
    "assessment_frontend_batch8_typecheck.json", "assessment_frontend_batch8_typecheck.log",
    "assessment_frontend_batch8_typecheck_fix1.json", "assessment_frontend_batch8_typecheck_fix1.log",
    "assessment_frontend_batch8_lint.json", "assessment_frontend_batch8_lint.log",
    "assessment_frontend_batch8_build.json", "assessment_frontend_batch8_build.log",
    "update_continuity_batch8.py", "continuity_batch8_receipt.json", "write_batch8_contract_notes.py",
]
paths.extend("reports/runs/recovery_reviewed_integration_20261016/" + name for name in run_files)
paths = list(dict.fromkeys(paths))
if any(not (ROOT / path).is_file() for path in paths) or "frontend/tsconfig.tsbuildinfo" in paths:
    raise RuntimeError("incomplete explicit stage inventory")
if execute("assessment_checkpoint_stage", ["git", "add", "--", *paths]) != 0:
    raise SystemExit(1)
if execute("assessment_checkpoint_diff_check", ["git", "diff", "--cached", "--check"]) != 0:
    raise SystemExit(1)
if execute("assessment_checkpoint_secret_check", [str(PYTHON), "-I", str(RUN / "check_staged_boundary.py")]) != 0:
    raise SystemExit(1)
if execute("assessment_checkpoint_commit", ["git", "commit", "-m", "checkpoint R11/R17 default assessment workbench and reviewed R16 inputs; G-C pending"]) != 0:
    raise SystemExit(1)
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
(RUN / "assessment_checkpoint_commit_receipt.json").write_text(json.dumps({"recorded_at": clock(), "sha": head, "explicit_paths": paths, "stage_gate": "not_accepted", "push": "not_run", "root_own_code_review": "awaiting_review"}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"checkpoint_sha": head, "files": len(paths), "push": "not_run", "stage_gate": "not_accepted"}))
