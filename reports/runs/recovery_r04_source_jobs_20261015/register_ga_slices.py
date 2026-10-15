"""补齐独立阶段意见对应的13能力切片；不提升任何原T整卡状态。"""

import copy
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
receipt = RUN / "ga_slice_registration.json"
assert not receipt.exists()
at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
state_path = ROOT / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
manifest = json.loads((ROOT / "contracts/task_manifest.json").read_text(encoding="utf-8"))
original_statuses = {key: value["status"] for key, value in state["tasks"].items()}
changed = []
for package_id in ("R01", "R02", "R03"):
    assert state["recovery_tasks"][package_id]["status"] == "accepted"
    for slice_id in manifest["recovery"]["work_packages"][package_id]["output_slices"]:
        task_id = manifest["recovery"]["capability_slices"][slice_id]["original_task"]
        entry = state["tasks"][task_id]["slice_acceptance"][slice_id]
        entry.setdefault("history", []).append({"recorded_at": at,
            "prior_record": {key: copy.deepcopy(value) for key, value in entry.items() if key != "history"},
            "reason": "G-A scoped Ship applies to this package output, not the whole original task"})
        entry.update(status="accepted", review_ref="reports/reviews/recovery/G-A-checkpoint-review-1.md",
            evidence=["reports/stages/recovery/G-A.md",
                      "reports/reviews/recovery/G-A-checkpoint-review-1.md",
                      state["recovery_tasks"][package_id]["report"]])
        changed.append(slice_id)
assert {key: value["status"] for key, value in state["tasks"].items()} == original_statuses
state["updated_at"] = at
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
result = subprocess.run(["D:/dianzi/backend/.venv/Scripts/python.exe", "scripts/verify_plan.py"],
    cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
(RUN / "ga_slice_registration_plan.log").write_text(result.stdout + result.stderr, encoding="utf-8")
receipt.write_text(json.dumps({"recorded_at": at,
    "initial_registration_verifier": "19 STATE_RECOVERY_OUTPUT_SLICE/REQUIRED_SLICE errors; only package statuses registered, no raw stdout file captured",
    "correction": "register exactly approved R01-R03 output slices using independent scoped Ship evidence",
    "accepted_slices": changed, "original_T_whole_card_statuses_unchanged": True,
    "verification_not_run_unchanged": True, "verifier_exit_code": result.returncode}, indent=2))
print(json.dumps({"accepted_slices_count": len(changed), "verifier_exit_code": result.returncode}))
raise SystemExit(result.returncode)
