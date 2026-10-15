"""保留历史并登记已冻结组件，整卡与阶段验收不随组件通过提升。"""

import copy
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[3]
run = Path(__file__).resolve().parent
receipt = run / "question_snapshot.json"
assert not receipt.exists()
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def strict_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


notes = {
    "R04": "限流/重复头/超长头批次c83e1a03f2独立限定Ship，已集成23c1878；906 unit、421相关、19既有PG、40自拟通过，另RFC850完整50年日期边界1红为非阻断保守误blocked债务，未skip。真实来源与浏览器结果仍限定早前afe/8f6分段；整卡未验收。",
    "R05": "基础3ab2357的float32全零/平方范数Must均独立关闭；grounding b151独立47探针/113核心/29安全通过，已集成1688367。root d7b6bf1已接API认证→PG当前公开证据→真实E5/PGvector/rerank→双轮生成核验→复鉴权/epoch→PG答案/历史GET；880 unit默认65.78%及124相关通过，11PG检索为显式合成模型接线，不是live。新独立pipeline reviewer审d7，另API/PG测试作者并行。完整产品问答live尚未执行；供应商累计真实4次，费用unknown。",
    "R17": "问答前端ebbdc9a已冻结249 unit/9隔离浏览器，root冷启动等待增量a0a94f1为254 unit/类型/lint/build通过，新独立UI reviewer审目标a0a94f1，原12秒被10秒超时的红例保留。尚未集成或真实页面问答验收；来源工作台afe真实桌面/移动/管理员2+1通过，动态背景和reduced-motion仍有真实证据。完整工作台未完成。",
}
links = {
    "R04": ["reports/reviews/recovery/G-B-R04-rate-limits-review-1.md", "reports/reviews/recovery/G-B-R04-rate-limits-review-1-recheck.md"],
    "R05": ["reports/reviews/recovery/G-B-R05-vector-foundation-review-1.md", "reports/reviews/recovery/G-B-R05-grounded-answer-review-1.md", "reports/runs/recovery_r05_controller_20261015/questions_unit.json", "reports/runs/recovery_r05_controller_20261015/vector_pg_active_support.json"],
    "R17": ["reports/runs/recovery_r05_controller_20261015/question_ui_timeout/unit.json"],
}
state_path = root / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8"), object_pairs_hook=strict_pairs)
original_tasks = copy.deepcopy(state["tasks"])
for task_id, note in notes.items():
    task = state["recovery_tasks"][task_id]
    task.setdefault("history", []).append({"recorded_at": started, "prior_status": task["status"], "prior_implementation": task["implementation"], "prior_verification": copy.deepcopy(task["verification"]), "prior_verification_scope_notes": copy.deepcopy(task.get("verification_scope_notes", {})), "event": "Frozen component evidence update; no whole-card acceptance"})
    assert task["status"] == "in_progress" and task["implementation"] == "partial"
    task["verification_scope_notes"] = {"current": note, "recorded_at": started, "scope": "whole-card not_run; limited component evidence only"}
    task["evidence"] = list(dict.fromkeys(task.get("evidence", []) + links[task_id]))
state["updated_at"] = started
state["updated_by_task"] = "G-B frozen question pipeline and active workstream evidence"
assert state["tasks"] == original_tasks
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
snapshot = f"""## 当前权威快照 · {started}

集成分支codex/full-delivery-recovery，HEAD {head}；远端最后已核对G-A fa5deb0d0b519869ca92d34d9ffe7d8e39b06fb4（15:41:48+08）。G-A accepted；G-B in_progress/partial、未阶段push，所有原T整卡及R最终验收范围不变。以下旧快照是历史，不覆盖本段。

{notes['R04']}

{notes['R05']}

{notes['R17']}

并行四槽：root独占共享合同/schema/锁/进度/集成/Git并准备真实运行；r05_question_api_pg_tests拥有新test_r05_question_api_pg.py/test_r05_question_routes.py及自有报告，WT D:/wt/r05-api-tests@d7；新独立r05_question_pipeline_independent_review只审d7，不改业务；新独立r05_question_frontend_independent_review审a0a94f1与自己的负例。来源限流和grounding独立review已封存退出。实现者不能accepted/push，报告/日志仅自有范围。

API/worker/beat和前端上一段afe均16:10到期关闭，目前未有新的产品服务；MinIO段2实际16:55:49 deadline结束exit0、无OOM，段3实际16:57:02启动、7200秒硬截止18:57:02，同对象/身份、存在73秒中断。首次段3 helper在启动前路径替换错误exit1已记录initial_start_failure.json，修正后才启动。Docker总截止2026-10-17T21:49:15+08。不同版本/中断不拼连续时长。

当前部署缺口：Dockerfile未安装semantic extra，compose API384MiB不足约1.25GiB模型子进程，private-only网络无供应商出网；待主控受控部署接线/独立审查，不能称默认容器已支持问答。后续运行须2GiB受控Job，不继承旧PDF512MiB。凭据/模型缓存/连接仓外；缺双人金标与FOFA授权资产范围；PPT用户后置。下一步：新PG/API负例与root修复→新独立复核→有限真实模型/PG/API/浏览器问答→新G-B阶段review和push；持续完整目标。

"""
for relative in ("progress/context_handoff.md", "progress/blockers.md", "progress/recovery_workstreams.md"):
    path = root / relative
    path.write_text(snapshot + path.read_text(encoding="utf-8"), encoding="utf-8")
stage = root / "reports/stages/recovery/G-B.md"
text = stage.read_text(encoding="utf-8")
lines = text.splitlines()
replacements = {"本次写作开始时间：": started, "最后更新时间：": started, "本报告证据截止时间：": started, "已测代码SHA：": "d7接线880 unit/124相关；3ab基础与b151核心定向；c83来源复核；a0a94f1前端254，均限定组件非整阶段", "已审代码SHA：": "c83来源限流、3ab基础、b151内核限定Ship；d7产品接线和a0a94f1问答UI新独立初审在途；整阶段未审", "提交/推送结果：": f"当前本地{head}，G-B未阶段push；G-A远端fa5实际收据见台账"}
for prefix, value in replacements.items():
    index = next(index for index, line in enumerate(lines) if line.startswith(prefix))
    lines[index] = prefix + value
text = "\n".join(lines) + "\n"
heading = text.find("\n## ")
text = text[:heading] + "\n\n" + snapshot + text[heading:]
ended = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
text = "\n".join("本次写作结束时间：" + ended if line.startswith("本次写作结束时间：") else line for line in text.splitlines()) + "\n"
text += f"\n修订记录：{ended}，主控/root以实际冻结SHA更新接线、审查、并行所有权、限流与浮点Must关闭、UI10秒负例/等待预算和资源中断；不提升整卡/阶段状态。\n"
stage.write_text(text, encoding="utf-8")
task_report = root / "reports/tasks/R05.md"
task_report.write_text(task_report.read_text(encoding="utf-8") + f"\n## 冻结接线进展 · {ended}\n\n{notes['R05']}\n\n新代码复用既有认证/权限、PG事实账本/事务、网关和GenerationClient、永久原文校验、已审本地模型；仅新增单事件检索与PG问答生命周期服务，未建平行业务数据库。R12全库混合、多轮多跳、资产/历史调查仍未完成，R05不签其最终范围。共享来源transport新批已独立Ship，root集成回归执行中。完整live/人工/产品浏览器本时点not_run。\n", encoding="utf-8")
receipt.write_text(json.dumps({"started_at": started, "ended_at": ended, "head": head, "original_t_tasks_unchanged": state["tasks"] == original_tasks, "whole_card_or_stage_status_promoted": False}, indent=2), encoding="utf-8")
print(receipt.read_text())
