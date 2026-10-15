"""Confirm the directed document corrections without executing product code."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, r"D:\dianzi\reports\runs\recovery_r00_review_1_20261014")
import run_commands as runner

ROOT = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r00-recheck-clean\dianzi")
OUT = Path(r"D:\dianzi\reports\runs\recovery_r00_activation_check_20261014")
runner.OUTPUT = OUT
BASE = "69ecf16be7d95e839b18a4a40f03b3f9d86707f4"
SHA = "f0b154ee0e10100bc9a9d293ebeded13926d0a42"


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


runner.run("header_head", ["git", "rev-parse", "HEAD", "HEAD^{tree}"], ROOT)
runner.run("header_status", ["git", "status", "--short"], ROOT)
runner.run("header_diff_check", ["git", "diff", "--check", BASE, SHA], ROOT)
runner.run("header_baseline", ["python", "scripts/verify_plan.py", "--baseline", "contracts/baselines/plan_baseline_recovery_r00.json"], ROOT)
changed = git("diff", "--name-only", BASE, SHA).decode().splitlines()
cr_checks = []
for number in range(1, 10):
    relative = f"docs/decisions/CR-R{number:02d}.md"
    lines = (ROOT / relative).read_text(encoding="utf-8").splitlines()
    cr_checks.append({"path": relative, "status_accepted": "状态：accepted" in lines[2], "first_created_preserved": "2026-10-14T20:52:23+08:00" in lines[3],
                      "updated_at_corrected": "2026-10-14T22:31:09+08:00" in lines[3],
                      "reviewer_and_ref": "/root/r00_independent_review" in lines[6] and "G-A-R00-review-1-recheck.md" in lines[6],
                      "reviewed_sha": "15d0272bd2a9e25d19397d8147e9c3cbe6016f9b" in lines[6]})
state = json.loads((ROOT / "progress/task_state.json").read_text(encoding="utf-8"))
original_task_bodies = []
for path in (ROOT / "docs/tasks").glob("T*.md"):
    relative = path.relative_to(ROOT).as_posix()
    old = git("show", "15d0272bd2a9e25d19397d8147e9c3cbe6016f9b:" + relative).decode("utf-8").replace("\r\n", "\n").split("## 恢复合并验收附录", 1)[0]
    new = path.read_text(encoding="utf-8").split("## 恢复合并验收附录", 1)[0]
    original_task_bodies.append({"path": relative, "original_body_unchanged": old == new})
record = {"candidate": SHA, "tree": git("rev-parse", "HEAD^{tree}").decode().strip(), "changed_files": changed,
          "cr_header_checks": cr_checks, "state_execution_order_source": state["execution_order_source"],
          "accepted_original_tasks": [key for key, entry in state["tasks"].items() if entry["status"] == "accepted"],
          "accepted_recovery_tasks": [key for key, entry in state["recovery_tasks"].items() if entry["status"] == "accepted"],
          "r01_status": state["recovery_tasks"]["R01"]["status"],
          "resource_note_explicit": "尚未并入本R00冻结树" in (ROOT / "progress/context_handoff.md").read_text(encoding="utf-8"),
          "original_task_bodies": original_task_bodies,
          "unchanged_manifest_and_baseline": all(git("show", BASE + ":" + path) == git("show", SHA + ":" + path) for path in ("contracts/task_manifest.json", "contracts/baselines/plan_baseline_recovery_r00.json")),
          "historical_plan_note": "Plan 11's unstarted-development sentence describes drafting-time history; current authority/state and R01 progress take precedence, and no further approval is needed."}
(OUT / "header_recheck_inventory.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"candidate": SHA, "changed_files": changed, "all_nine_cr_headers_corrected": all(all(entry[key] for key in ("status_accepted", "first_created_preserved", "updated_at_corrected", "reviewer_and_ref", "reviewed_sha")) for entry in cr_checks),
                  "accepted_original_tasks": record["accepted_original_tasks"], "accepted_recovery_tasks": record["accepted_recovery_tasks"],
                  "original_task_body_count": len(original_task_bodies), "all_original_task_bodies_unchanged": all(entry["original_body_unchanged"] for entry in original_task_bodies),
                  "resource_note_explicit": record["resource_note_explicit"], "unchanged_manifest_and_baseline": record["unchanged_manifest_and_baseline"]}, indent=2))
