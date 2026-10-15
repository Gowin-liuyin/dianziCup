"""以真实时钟保留历史，登记限定范围的独立结论而不验收整卡。"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
NOW = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
HEAD = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


path = ROOT / "progress/task_state.json"
state = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
state["updated_at"] = NOW
state["updated_by_task"] = "R01/R03 limited rechecks; R04 source and UI preparation"
updates = {
    "R01": ("in_progress", "a7c0 TLS两Must已由新独立reviewer限定关闭；7TLS/6补充、native失败隐私和默认prepare+Linux恢复1通过。云CI/整阶段未审。Vitest4新集成7f9/0b已独立复验并有scope授权核对。"),
    "R03": ("awaiting_review", "08c2ff0 cursor和2522b3a network已冻结；两个原独立reviewer定向复跑通过消息已收到，最终报告封存中。未拿dirty root396替代固定版独立283/379，也未签整R03/G-A。"),
    "R04": ("in_progress", "48ad PDF/JSON解析与7f9前端独立限定通过；Linux根33补测通过。0e622ce NVD/schema13新批待新review。实际NVD和vLLM各一次匿名GET，尚未PG→API→浏览器live闭环；模型调用0。"),
    "R17": ("in_progress", "黑客暗色/低亮动态拓扑和reduced-motion已有独立浏览器证据；7f9列表/详情/证据115unit、fixture6、负例5、HTTP8、实auth3限定通过。真实情报/完整工作台未通过；原生hidden暂停仍manual未证明。"),
}
for task_id, (status, note) in updates.items():
    record = state["recovery_tasks"][task_id]
    record.setdefault("history", []).append({
        "recorded_at": NOW, "prior_status": record["status"],
        "prior_implementation": record["implementation"],
        "prior_verification": record["verification"].copy(),
        "event": "Reconcile frozen limited evidence; no whole-card acceptance",
    })
    record.update(status=status, implementation="partial")
    record.setdefault("verification_scope_notes", {})["current_snapshot"] = note
    if task_id == "R01":
        record["verification_scope_notes"]["security"] = "两TLS Must限定关闭，整阶段security尚未集成审查；不使用旧needs_changes作当前结论。"
    if task_id == "R04":
        record["evidence"] = list(dict.fromkeys(record["evidence"] + [
            "reports/reviews/recovery/G-B-R04-parsing-review-1.md",
            "reports/reviews/recovery/G-B-R04-frontend-review-1-recheck.md",
            "reports/tasks/R04-NVD-source-schema.md",
        ]))
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

summary = f"""## 当前权威快照 · {NOW}

分支codex/full-delivery-recovery，HEAD {HEAD}，origin授权URL已核对；G-A仍in_progress/partial，无阶段push。旧历史保持，以下旧等待或旧状态不覆盖本快照。R00仅既有限定accepted；原T全部映射切片要求不变。

R01 TLS a7两Must独立关闭，云CI未运行；CR-R10升级既有授权覆盖，7f9/0b新集成UI与依赖已独立通过限定复验。R03 cursor08c2ff0及network2522b3a原Must修复固定，原独立reviewer实际负例/PG/纯unit回归通过，最终报告封存中；整阶段须新的综合review。R04 PDF/JSON48ad、UI7f9专项有限通过，root Linux33补测通过。NVD真实映射和0013来源历史schema已冻结0e622ce；新review尚未开始，API/worker/页面真实链路仍需实施。

并行四槽：root公共合同/迁移/来源服务/集成；r04_vendor_source只独立vendor_advisories.py/直接测试/真实留档/report；r03_executor_independent_review固定08c2ff0只审查；r03_network_independent_review固定2522b3a只审查。cursor测试专库已释放0012；root新r04_sources专库公共schema仍0013或由fixture迁移，以实际查询为准，不动旧固定审查库。API旧0b段已请求受控停止；MinIO原2小时边界约13:15，到期不计继续运行。

用户UI参考已吸收为暗色青绿、密集可读、证据抽屉与低亮动态拓扑；已真实浏览器验证，展示样本明确fixture，不冒充实时情报。NVD/vLLM实际匿名GET仅来源诊断，未计持续监测。产品模型调用0、费用unknown；DeepSeek/OpenAI/Anthropic兼容尚未接线；embedding/rerank未探测。秘密仓外DPAPI，不能进文件/前端/日志；双人独立金标和FOFA授权资产范围仍缺，PPT后置。

下一步：完成两review封存和当前证据归档，接source原始响应/成员修订→PG/事件→真实只读API→浏览器；新非作者审查NVD/schema/source读取，并行模型受控POST准备。G-A须全阶段集成与新review，不能拿组件通过代替阶段过门。历史记录从此处往下保留。

"""
for relative in ("progress/context_handoff.md", "progress/recovery_workstreams.md", "progress/blockers.md"):
    target = ROOT / relative
    target.write_text(summary + target.read_text(encoding="utf-8"), encoding="utf-8")

stage = ROOT / "reports/stages/recovery/G-A.md"
content = stage.read_text(encoding="utf-8")
for label in ("本次写作开始时间", "本次写作结束时间", "最后更新时间", "本报告证据截止时间"):
    lines = content.splitlines()
    content = "\n".join(f"{label}：{NOW}（本次快照修订）" if line.startswith(label + "：") else line for line in lines) + "\n"
content = content.replace("## 1. 本阶段", summary + "## 1. 本阶段", 1)
stage.write_text(content, encoding="utf-8")

cr = ROOT / "docs/decisions/CR-R10_vitest_security_upgrade.md"
content = cr.read_text(encoding="utf-8").replace(
    "状态：awaiting_review；现有用户授权覆盖普通兼容安全修复，正式技术生效待新的集成独立核对。",
    "状态：accepted（仅本固定依赖安全修复，按新集成独立意见登记生效；非R01/阶段验收）。",
    1,
)
content += f"\n## {NOW} · 当前生效登记\n\n主控依据非作者scope-check与G-B-R04-frontend-review-1-recheck.md登记：既有批次授权覆盖；固定0b983/7f9集成npm ci、115unit、lint/typecheck/build/audit0及浏览器/HTTP专项由独立reviewer复跑。Vitest4.1.11本固定修复生效，旧授权等待判断仅保留历史，不再阻断。此登记不签整R01/G-A或云CI通过。\n"
cr.write_text(content, encoding="utf-8")
print(json.dumps({"recorded_at": NOW, "code_head": HEAD, "whole_stage_accepted": False}))
