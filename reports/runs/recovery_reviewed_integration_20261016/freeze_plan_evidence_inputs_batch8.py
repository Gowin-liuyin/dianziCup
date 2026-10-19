"""Freeze already collected plan evidence as exact raw blobs for isolated worktree replay."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path, PurePosixPath
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
SOURCE = Path("D:/wt/r19-annotation-recovery/reports/runs/recovery_r19_annotation_crash_20261016/missing_plan_inputs.json")
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
missing = json.loads(SOURCE.read_text(encoding="utf-8-sig"))
if missing["missing_count"] != 22 or len(set(missing["paths"])) != 22:
    raise RuntimeError("unexpected plan input closure")
records = []
for relative in missing["paths"]:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or path.parts[0] != "reports" or path.suffix not in {".md", ".json"}:
        raise RuntimeError("unapproved evidence boundary")
    target = ROOT / relative
    raw = target.read_bytes()
    if target.is_symlink() or len(raw) > 2 * 1024 * 1024:
        raise RuntimeError("evidence path/size boundary")
    oid = subprocess.check_output(["git", "hash-object", "-w", "--no-filters", str(target)], cwd=ROOT, text=True).strip()
    records.append({"path": relative, "raw_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "immutable_raw_git_blob": oid, "provenance": "existing controller canonical collected evidence; original reports retained"})
receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "baseline_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "files": records, "closure_count": len(records), "secret_values_read": False, "holdout_answers_read": False, "tests": "not_run; only immutable evidence input recovery", "not_a_stage_acceptance": True}
(RUN / "plan_evidence_input_closure_batch8.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"closure_count": len(records), "receipt": "reports/runs/recovery_reviewed_integration_20261016/plan_evidence_input_closure_batch8.json"}))
