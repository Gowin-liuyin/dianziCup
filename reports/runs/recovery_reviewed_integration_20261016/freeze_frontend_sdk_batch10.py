"""Create an explicit non-stage candidate with original failures and a protected user file."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
if subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT).strip():
    raise RuntimeError("unrelated staged work present")
protected = ROOT / "frontend/tsconfig.tsbuildinfo"
expected = "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
if hashlib.sha256(protected.read_bytes()).hexdigest() != expected:
    raise RuntimeError("protected user file changed")
source = json.loads((RUN / "reviewed_frontend_sdk_batch10_inputs.json").read_text())
paths = {item["path"] for item in source["files"]}
paths.update({"frontend/src/App.tsx", "frontend/src/app/workspace-navigation.ts", "frontend/src/App.investigation.test.tsx", "docs/decisions/CR-R16_completion_fanin.md", "reports/tasks/R17.md", "reports/tasks/R18.md", "reports/stages/recovery/G-E.md", "progress/task_state.json", "progress/context_handoff.md", "progress/recovery_workstreams.md", "progress/blockers.md"})
names = [
    "integrate_reviewed_frontend_sdk_batch10.py", "reviewed_frontend_sdk_batch10_inputs.json",
    "check_frontend_sdk_batch10.py", "check_sdk_batch10_related.py", "frontend_sdk_batch10_check_receipts.json",
    "refresh_frontend_batch10_index.py", "refresh_frontend_batch10_post_index.py",
    "frontend_batch10_index_source_files.json", "frontend_batch10_cbm_receipts.json",
    "frontend_batch10_post_index_source_files.json", "frontend_batch10_post_cbm_receipts.json",
    "frontend_batch10_xml_withheld.json", "record_fanin_contract_batch10.py", "fanin_contract_batch10_receipt.json",
    "update_batch10_continuity.py", "continuity_batch10_receipt.json",
    "write_frontend_sdk_batch10_reports.py", "frontend_sdk_batch10_report_receipt.json",
    "freeze_internal_contracts_batch10.py", "internal_contracts_batch10_receipt.json", "freeze_frontend_sdk_batch10.py",
]
for label in ("frontend_batch10_unit", "frontend_batch10_typecheck", "frontend_batch10_lint", "frontend_batch10_build", "sdk_batch10_unit", "sdk_batch10_related_fix1"):
    names.extend([label + ".json", label + ".log"])
names.extend(["sdk_batch10_unit.xml", "sdk_batch10_related_fix1.xml"])
for phase in ("frontend_batch10", "frontend_batch10_post"):
    names.extend(phase + "_cbm_" + label + ".log" for label in ("index", "schema", "architecture", "workbench"))
names.extend("internal_contracts_batch10_" + label + ".log" for label in ("add", "boundary", "diff", "commit"))
paths.update((RUN / name).relative_to(ROOT).as_posix() for name in names)
for relative in paths:
    path = ROOT / relative
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("unexpected explicit input: " + relative)
attributes_path = ROOT / ".gitattributes"
attributes = attributes_path.read_text(encoding="utf-8")
for relative in sorted(paths):
    if relative.startswith(RUN.relative_to(ROOT).as_posix() + "/") and Path(relative).suffix in {".log", ".xml"}:
        rule = relative + " -text"
        if rule not in attributes.splitlines():
            attributes += rule + "\n"
attributes_path.write_text(attributes, encoding="utf-8", newline="\n")
paths.add(".gitattributes")
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
receipts = []
commands = [
    ("add", ["git", "add", "--", *sorted(paths)]),
    ("boundary", [str(ROOT / "backend/.venv/Scripts/python.exe"), "-I", str(RUN / "check_staged_boundary.py")]),
    ("diff", ["git", "diff", "--cached", "--check"]),
    ("commit", ["git", "commit", "-m", "checkpoint G-E: mount revision-bound investigations and six-tool SDK; default review pending"]),
]
try:
    for label, command in commands:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=120)
        (RUN / ("frontend_sdk_batch10_checkpoint_" + label + ".log")).write_bytes(result.stdout + result.stderr)
        receipts.append({"label": label, "command": command, "exit_code": result.returncode})
        if result.returncode:
            raise RuntimeError("candidate stopped before next step: " + label)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
finally:
    (RUN / "frontend_sdk_batch10_checkpoint_receipt.json").write_text(json.dumps({"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "head_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "paths": sorted(paths), "commands": receipts, "stage_accepted": False, "push": "not_run", "frontend_xml": "withheld pending provenance; original raw file remains outside commit", "user_file_unchanged": hashlib.sha256(protected.read_bytes()).hexdigest() == expected}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"head_sha": head, "stage_accepted": False, "push": "not_run"}))
