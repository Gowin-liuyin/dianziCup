"""将已取得的有限证据与未接线范围同步到唯一进度索引，保留历史。"""

import copy
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[3]
now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
receipt = Path(__file__).resolve().parent / "snapshot_reconciliation.json"
assert not receipt.exists()
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
notes = {
    "R04": "当前来源分页e6/c3与空package/API Must已独立关闭；8f6真实after游标5页新增40，15:27观测95事件/414证据且厂商partial。afe工作台15:56桌面/移动原文证据2pass，15:59管理员真实提交/PG partial状态1pass。403/429提前重试语义修复仍在独立WT；整卡未验收。",
    "R05": "31c生成metadata/nested/defer Must均独立关闭；两wire共4次真实调用，首轮2次因CRLF精确引用失败，single-line-v2两次通过，费用unknown。1e77语义锁Must独立关闭并集成fd01ea3；root102回归、6真PG/0014保历史/mypy75通过；新retrieval草稿10真PG通过但未冻结/未审。模型/PG/问答/API/UI完整链尚未接通，整卡未验收。",
    "R17": "afe来源工作台已独立限定Ship，root178前端通过；真实浏览器桌面/390宽度证据2pass，管理员来源一页提交→PG partial1pass。暗色青绿/低亮拓扑/减少动画/指针焦点已验证。首轮admin selector错误已保留，按role改测试后复验通过；完整问答/资产/图谱/推荐等工作台仍未完成。",
}
links = {
    "R04": ["reports/reviews/recovery/G-B-R04-pipeline-review-1-recheck.md", "reports/runs/recovery_r04_source_jobs_20261015/real_browser_segment6.json", "reports/runs/recovery_r04_source_jobs_20261015/real_browser_segment6_recheck.json"],
    "R05": ["reports/reviews/recovery/G-B-R05-generation-review-1-recheck.md", "reports/reviews/recovery/G-B-R05-semantic-review-1.md", "reports/tasks/R05-semantic-runtime.md", "reports/tasks/R05-pgvector-runtime.md", "reports/runs/recovery_r05_controller_20261015/embedding_regression.json", "reports/runs/recovery_r05_controller_20261015/vector_pg_isolated.json"],
    "R17": ["reports/reviews/recovery/G-B-R17-source-jobs-review-1.md", "reports/runs/recovery_r04_source_jobs_20261015/real_browser_segment6_recheck.json"],
}
path = root / "progress/task_state.json"
state = json.loads(path.read_text(encoding="utf-8"))
original_tasks = copy.deepcopy(state["tasks"])
for task_id in notes:
    task = state["recovery_tasks"][task_id]
    task.setdefault("history", []).append({"recorded_at": now, "prior_status": task["status"],
        "prior_implementation": task["implementation"], "prior_verification": copy.deepcopy(task["verification"]),
        "prior_verification_scope_notes": copy.deepcopy(task.get("verification_scope_notes", {})),
        "event": "Closed prior component defects; preserve new work/limitations and do not infer whole-card acceptance"})
    task["status"] = "in_progress"
    task["implementation"] = "partial"
    task["verification"] = {key: "not_run" for key in task["verification"]}
    task["verification_scope_notes"] = {"current": notes[task_id], "recorded_at": now,
        "scope": "whole-card verification not_run; component results only in cited frozen evidence"}
    task["evidence"] = list(dict.fromkeys(task.get("evidence", []) + links[task_id]))
    task["review_ref"] = links[task_id][0]
state["updated_at"] = now
state["updated_by_task"] = "G-B scoped evidence reconciliation; whole-card and stage acceptance pending"
assert state["tasks"] == original_tasks
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
snapshot = f"""## 当前权威快照 · {now}

集成分支codex/full-delivery-recovery，HEAD {head}；远端最后核实为G-A fa5deb0d0b519869ca92d34d9ffe7d8e39b06fb4，2026-10-15T15:41:48+08:00成功推送并ls-remote核对，见reports/push/recovery_push_log.jsonl。G-A范围已独立accepted；当前G-B in_progress/partial，未阶段push；原T整卡状态与最终范围不变。

{notes['R04']}

{notes['R05']}

{notes['R17']}

真实受控Windows段6固定afe490：API/worker/beat 15:55:43至16:10:43，前端15:55:45至16:10:46，均到期结束；不同代码/中断绝不拼连续运行。MinIO段2 14:55:48至16:55:48硬截止；Docker总截止2026-10-17T21:49:15+08。模型缓存/凭据/连接只在仓外，holdout不索引；双人金标/裁决与FOFA授权范围仍缺，PPT按用户后置。

并行：root独占公共schema/迁移0014/依赖锁/集成/进度/推送及retrieval/API接线；r05_grounded_answer_core拥有answering/contracts.py、grounding.py、直接测试/自有报告，禁止改API/PG；r04_source_rate_limits拥有source_jobs._http_failure/直接测试/自有报告（旧单个错误断言授权纠正）；新的r05_vector_foundation_review只审冻结fd01ea3并复跑，不改业务。总4槽位，子Agent不得自行扩大文件所有权/再spawn/签accepted/push。

下一步：完成单事件真实向量检索→严格引用生成/核验→PG用户答案→API→问答页面；新小批独立review后真实全链验证；限流修复新review。G-B通过后才安排新的整阶段review/push。下面旧段落仅历史，不覆盖本快照。

"""
for name in ("progress/context_handoff.md", "progress/blockers.md", "progress/recovery_workstreams.md"):
    target = root / name
    target.write_text(snapshot + target.read_text(encoding="utf-8"), encoding="utf-8")
stage = root / "reports/stages/recovery/G-B.md"
text = stage.read_text(encoding="utf-8")
replacements = {
    "本次写作开始时间：": now, "本次写作结束时间：": now + "（本次证据整理时点）",
    "最后更新时间：": now, "本报告证据截止时间：": now,
    "已测代码SHA：": "afe490前端178及真实浏览器2+1；31c供应商探测；fd01ea3基础102/6PG，retrieval working diff10PG，均限定范围，非整阶段",
    "已审代码SHA：": "7af API/8f6来源/31c生成/d391时间/fccc来源UI/1e77语义限定意见；fd01ea3新基础初审在途，整阶段未审",
    "提交/推送结果：": "G-A已推远端fa5，当前G-B本地fd01ea3，G-B尚未阶段push，见实际台账",
}
lines = text.splitlines()
for prefix, value in replacements.items():
    index = next(index for index, line in enumerate(lines) if line.startswith(prefix))
    lines[index] = prefix + value
text = "\n".join(lines) + "\n"
heading = text.find("\n## ")
text = text[:heading] + "\n\n" + snapshot + text[heading:]
text += f"\n修订记录：{now}，主控/root补G-A实际推送、旧Must关闭、95/414分段观测、真实浏览器和4次供应商探测、语义/PG进展；保留所有旧失败及未接线范围。\n"
stage.write_text(text, encoding="utf-8")
task_report = root / "reports/tasks/R05.md"
assert not task_report.exists()
task_report.write_text(f"""# R05 · 真实模型与首条引用回答

首次创建时间：{now}
最后更新时间：{now}
主控/root；状态in_progress，implementation partial，各层整卡验证not_run。

{notes['R05']}

复用已审网关/GenerationClient/权限和PG唯一事实账本；新增官方pgvector0.5.1映射、ONNX Runtime/tokenizers/numpy显式semantic extra，因真实384维存储和本地双语模型推理必要。下载模型为固定官方ONNX/分词器约975MB，缓存仓外；没有pickle、remote code、hash语义替身。

当前代码fd01ea3；semantic作者77add60→bfea9fe→1e77c0d及新独立review，详细时刻/命令/退出/计数见R05-semantic-runtime.md和review；PG资源独立准备6e5a8df的10SQL通过/共享重启1not_run，root新增真实迁移6通过。102回归命令embedding_regression.json、mypy75 static.json，6PG vector_pg_isolated.json；先前fixture scope和缺运行ID导致两轮6setup errors均保留，不计业务通过。

源PG→索引→问答完整产品链与浏览器仍not_run；10PG检索草稿只是fixture plumbing，不是语义准确率。生成初轮CRLF被拒与single-line-v2后两次成功分别留档，4实际付费请求费用unknown，不是正式问答分母。当前原文/唯一证据删除、权限、历史及模型失败的完整产品验收待接线后独立复跑。未更改金标、阈值、分母或R12最终范围。

下一步按交接快照实施API/问答页面并创建新初审，不因当前组件Ship签整R05。
""", encoding="utf-8")
receipt.write_text(json.dumps({"recorded_at": now, "head": head, "original_T_tasks_unchanged": True,
    "tasks_reconciled": list(notes), "no_new_accepted": True, "whole_verification_not_run": True}, indent=2), encoding="utf-8")
print(json.dumps({"recorded_at": now, "head": head, "original_T_tasks_unchanged": True}))
