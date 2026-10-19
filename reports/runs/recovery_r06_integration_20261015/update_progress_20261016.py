"""Record the current integrated tree without promoting component checks to whole cards."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
remote = subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=ROOT, text=True).strip()
assert remote == "https://github.com/Gowin-liuyin/dianziCup.git"
path = ROOT / "progress/task_state.json"
state = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_fields)
original_tasks = json.dumps(state["tasks"], sort_keys=True, ensure_ascii=False)
notes = {
    "R06": "失败原文独立收据 b781 已限定审查并集成；九源真实新持续段未启动。增量观察器独立初审三项 Must 正修，整卡未验收。",
    "R07": "core、公开字段、四维模型接口已限定审查并集成；root 发布服务尚未审/接 worker。新增真实 PG 来源子集遗漏复现正在修复；单维模型调用接口独立实现中。",
    "R08": "Hunter/Quake connector 已限定审查集成，四次真实聚合 search 成功；0授权资产扫描，统计不等于受影响资产；PG/worker/API/UI 暴露统计未接。",
    "R09": "证据知识卡准备代码已冻结；共享预派发超时 Must 新修复已独立 Ship，R09组合版本和原reviewer复核尚未完成；无真实资料模型/产品接线验收。",
    "R11": "版本范围准备切片修复已独立限定 Ship，尚未合主控；资产清单 parser 两项 Must 正修复。无实际资产PG/API/四态自查整链验收。",
    "R17": "事件详情UI限定切片修复已独立 Ship并集成；对应真实后端浏览器复验未执行，其他完整工作台未完成。",
    "R20": "进程启动限额修复已独立限定 Ship并集成；严格总CPU一秒边界/旧全unit四失败未关闭；整阶段安全、恢复与CI未验收。",
}
for task, note in notes.items():
    item = state["recovery_tasks"][task]
    item.setdefault("history", []).append({"recorded_at": started, "prior_status": item["status"], "prior_implementation": item["implementation"], "event": note})
    item["status"], item["implementation"] = "in_progress", "partial"
    item["verification_scope_notes"] = {"recorded_at": started, "current": note + " 各切片通过记录不替代整R卡的八层验证。"}
state["updated_at"], state["updated_by_task"] = started, "R06–R11 parallel frozen review and integration"
assert json.dumps(state["tasks"], sort_keys=True, ensure_ascii=False) == original_tasks
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
snapshot = f"""## 当前权威续接与文件所有权 · {started}

主控 codex/full-delivery-recovery HEAD {head}，origin 仍为授权地址。最后已核远端为 G-B/c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7；G-C in_progress/partial，未阶段放行或 push。本段新增 reviewed merge 包括公开字段 facf、R20 startup 535、R17 detail 647、失败收据 b781、模型字段 ef247；只有 .gitattributes 两侧精确材料规则冲突由主控合并，最终 cc1。集成receipt在 recovery_r06_integration_20261015，当前 cc1 组合回归尚未运行。

当前活跃6：root；r06_incremental_observation_collector_fix；r11_manifest_snapshot_parsing_implementation；recovery_frozen_evidence_archive；r09_shared_timeout_combination_preparation；r07_single_model_dimension_implementation。宿主16含root，实际目标6–10；禁止一级Agent再spawn。root独占公共schema/迁移/锁/runtime/集成Git/progress。观察器仅自有reports run/测试；清单parser仅assets内部候选与直接测试；归档者仅新增canonical reports、不改Git/业务/progress；R09组合D:/wt/r09-combo-fix固定ed+47；单维模型D:/wt/r07-single-field@cc1+47仅model_fields与专属tests。所有初审用新独立Agent和冻结版本；不会让作者自签。

root D:/wt/r07-publication@23f5186 有未提交来源roster保护/3新增PG测试。实际漏洞：2个current PG来源只交1个文档时仍可保存FAILED模型维度；已红色复现，修后定向绿，待新代码冻结、77PG/202unit/static/CBM及全新初审。共享GenerationClient predispatch修复47c47bc/材料df0fa、独立review gen-tmo-r1 限定Ship，未合main；R09原Must不能被旧SHA绿色背书。版本范围71e724/材料8f5/原reviewer复核限定Ship，未合main。parser tool_permissions语义换序和UTC校验两Must修中；observer超行delta/opaque token落盘/metadata连续性三Must修中。原红日志保留、CSV方言未判Must，不能为了涂绿修改原探针。

受控新runtime 00:32:57启动PG25432/Redis26379/OpenSearch29200，deadline2026-10-17T21:49:15+08；当前API/worker/frontend/MinIO/collector未宣称运行。旧1927段19:45:24–22:49:51共11067秒已结束，不得拼成6h；旧1156真实集成1187秒、199doc/216rev/2146evidence/234MinIO对象保留。新连续段须observer修复复核且root重启自有MinIO/默认beat后才能记录。

Hunter/Quake实际4次搜索00:58:59–00:59:12：Ollama266463/819574，vLLM0/2；provider统计retrieved时间已记、源观察时间unknown，费用unknown；0扫描/资产正文/PG暴露发布。FOFA为用户第三方relay，不是官方订阅，资产授权范围缺失；ZoomEye401。真实模型已授权，新的R07/R09live尚未执行；人工双人核验/裁决与金标未提供，PPT用户后置，CNNVD内置登录未确认。holdout不进产品/索引，秘密只DPAPI→进程env。

下一步：root发布冻批→新review并同时接job；归档共享Gen/版本复核→安全合入；R09组合→原reviewer定向复核；parser/observer修复→原reviewer复核；实际全链与G-C R06–R10仍必须完成，随后R11–R24持续推进。原T60项历史/验收分母未改。

"""
for name in ("context_handoff.md", "recovery_workstreams.md", "blockers.md"):
    target = ROOT / "progress" / name
    target.write_text(snapshot + target.read_text(encoding="utf-8-sig"), encoding="utf-8")
stage_path = ROOT / "reports/stages/recovery/G-C.md"
stage = stage_path.read_text(encoding="utf-8-sig")
ended = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
for prefix, value in (("本次写作开始时间：", started), ("本次写作结束时间：", ended), ("最后更新时间：", ended), ("本报告证据截止时间：", started)):
    stage = "\n".join(prefix + value if line.startswith(prefix) else line for line in stage.splitlines()) + "\n"
stage = stage.replace("## 2. 当前真实状态与修改\n", "## 2. 当前真实状态与修改\n\n" + snapshot, 1)
stage += f"\n{ended} /root修订：记录cc1已集成切片、六路所有权、新Must与资源边界；不改变历史首次创建时间或阶段门结论。\n"
stage_path.write_text(stage, encoding="utf-8")
receipt = {"started_at": started, "ended_at": ended, "head": head, "origin": remote, "original_T_tasks_unchanged": True, "whole_cards_accepted": [], "stage": "G-C in_progress/partial"}
(Path(__file__).parent / "progress_20261016_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
