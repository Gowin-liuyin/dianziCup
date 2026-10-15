"""依据已封存的新独立阶段意见登记有限通过；原T状态及未运行层级保持。"""

import copy
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
clock = ZoneInfo("Asia/Shanghai")
started = datetime.now(clock).isoformat(timespec="seconds")
receipt = RUN / "ga_acceptance_registration.json"
assert not receipt.exists()
manifest = json.loads((ROOT / "reports/runs/recovery_ga_checkpoint_review_1_20261015/docs_final_manifest.json").read_text(encoding="utf-8"))
review = ROOT / "reports/reviews/recovery/G-A-checkpoint-review-1.md"
assert manifest["gate"] == "ship_scoped_G_A"
assert hashlib.sha256(review.read_bytes()).hexdigest() == manifest["report_sha256"]
state_path = ROOT / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
original_tasks = copy.deepcopy(state["tasks"])
for task_id in ("R01", "R02", "R03"):
    task = state["recovery_tasks"][task_id]
    assert task["status"] == "awaiting_review"
    task.setdefault("history", []).append({"recorded_at": started,
        "event": "Independent G-A scoped Ship registration; original T acceptance unchanged",
        "prior_record": {key: copy.deepcopy(value) for key, value in task.items() if key != "history"}})
    task["status"] = "accepted"
    task["review_ref"] = "reports/reviews/recovery/G-A-checkpoint-review-1.md"
    task["verification_scope_notes"] = {"current": "仅本卡已批准G-A能力切片accepted；依据新阶段reviewer固定b27代码/a836文档Ship意见。1200组合/686纯unit及原始worker/API/PG/MinIO证据已独立核验；live/manual等现有not_run层级不被登记覆盖，后段与原T整卡验收保留。",
        "recorded_at": started, "reviewed_code_sha": manifest["reviewed_code_sha"],
        "reviewed_document_sha": manifest["reviewed_document_sha"]}
assert state["tasks"] == original_tasks
state["recovery_stage"] = "G-B"
state["updated_at"] = started
state["updated_by_task"] = "G-A scoped Ship registration based on independent checkpoint; continue G-B"
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

path = ROOT / "reports/stages/recovery/G-A.md"
document = path.read_text(encoding="utf-8")
updates = {
    "本次写作开始时间": started,
    "本次写作结束时间": started + "（依据独立意见的状态登记）",
    "最后更新时间": started,
    "阶段实际开始/结束时间": "历史未单独记录开始；首个已留档时钟2026-10-14T20:44:18+08:00仅为观测时点 / 独立阶段门2026-10-15T15:29:12+08:00封存，不是连续服务时段",
    "阶段状态": "accepted（仅G-A批准能力范围，依据新非作者Ship）",
    "已审代码SHA": "b27a79d9bce769564e86034a164010b3fd176080；已审文档a8362baa7ea042075ca53125495a080d86274bae；独立最终报告第8节Ship，封存时间2026-10-15T15:29:12+08:00",
    "提交/推送结果": "本次登记写作时尚未push；实际命令/退出码/北京时间/本地与远端SHA见reports/push/recovery_push_log.jsonl，推送后追加并随下一阶段提交，不递归改本文件写自身SHA",
}
for key, value in updates.items():
    document = re.sub(r"^" + re.escape(key) + "：.*$", key + "：" + value, document, count=1, flags=re.M)
document += f"\n{started}：/root依据新独立阶段reviewer第8节Ship登记accepted；原T记录与manual/live not_run不变，后续G-B继续；实际push收据待发生后追加台账。此前awaiting_review文字保留为本报告沿革。\n"
path.write_text(document, encoding="utf-8")
notice = f"""## 独立阶段通过登记 · {started}

本卡G-A能力切片accepted/complete，依据新独立reviewer固定代码b27a79d、文档a8362ba及reports/reviews/recovery/G-A-checkpoint-review-1.md第8节Ship，独立封存2026-10-15T15:29:12+08:00。原T整卡合并验收、各层not_run、正式live/人工/云CI及后段范围保持；下面各旧状态仅历史。阶段push写作时尚未发生，实际收据见reports/push/recovery_push_log.jsonl。

"""
for relative in ("reports/tasks/R01.md", "reports/tasks/R02.md", "reports/tasks/R03.md"):
    path = ROOT / relative
    path.write_text(notice + path.read_text(encoding="utf-8"), encoding="utf-8")
handoff = notice + "当前阶段G-B；源码尚未集成的来源UI fccc包处于新独立review，semantic/资源helper在独立WT，未由G-A意见背书。root后续继续采集/模型/检索接线，不能因本阶段放行结束完整目标。\n\n"
for relative in ("progress/context_handoff.md", "progress/blockers.md", "progress/recovery_workstreams.md"):
    path = ROOT / relative
    path.write_text(handoff + path.read_text(encoding="utf-8"), encoding="utf-8")
receipt.write_text(json.dumps({"started_at": started,
    "ended_at": datetime.now(clock).isoformat(timespec="seconds"),
    "review_report_sha256": manifest["report_sha256"],
    "reviewed_code_sha": manifest["reviewed_code_sha"], "reviewed_document_sha": manifest["reviewed_document_sha"],
    "accepted_scope": ["G-A", "R01", "R02", "R03"], "original_T_states_unchanged": True,
    "verification_not_run_unchanged": True, "push_performed": False}, indent=2))
print(receipt)
