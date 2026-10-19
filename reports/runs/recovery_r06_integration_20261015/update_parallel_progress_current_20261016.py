"""Record current scoped parallel work without promoting aggregate acceptance."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


started = now()
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert head == "acfe244e93662119b9d4b86033f8903bd4b43ec6"
state_path = ROOT / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_fields)
original = json.dumps(state["tasks"], ensure_ascii=False, sort_keys=True)
notes = {
    "R06": "固定产品e310/tool44来源实际06:19:43.758521+08启动，截止12:19:43.758521+08；06:46状态42总sourcejob/34成功4blocked4partial，0model/provider。旧段不拼6h；严格CPU门仍红。pwsh7 status成功，误用Windows PowerShell5 AsPlainText失败留存。",
    "R07": "默认入口1f/测试兼容8a/materiale61新初审47e needs_changes：幂等缺用户/事件路由scope两个PG/HTTP红；新专用scope-v2 fix作者green待冻结原reviewer复验。taxonomy7a/material4c独立复验中，官方schema126红不抹；default接线与selection/prompt持久审计仍待整合。",
    "R10": "PG六关系/默认图App已主合；新独立Neo4j派生投影准备WT从acfe，仅读合同/资源并提具体方案，未部署/接通，不称live通过。",
    "R11": "纯SBOM/条件已reviewed合mainacfe，侧表0532待整体审。PGd56/ad独立初审f92 needs_changes：commit/read store=None两原文损坏红，原作者修共同loader；SBOM089/c036独立隐私Must包含external URI/ref/encoded purl，正在仅公共安全投影fix，原canonical/hash不变。0021/22/default评估/OpenVEX未实施。",
    "R12": "ba/d3修复经独立fdd限定Ship，64/31全部绿但0020/defaultAPI/worker未接，正式QA/SLA未证。原作者新独立WT仅多轮多跳设计提案，root冻结后才实现公共接线。",
    "R17": "资产UI M01跨租户DTO拒绝后仍残留私有DOM，原独立f5 needs_changes；fixa25/materialf9，455前端/12Edge/新增2连动作者绿，原reviewer新WT复验；真实PG浏览器联测not_run。",
}
for task_id, note in notes.items():
    item = state["recovery_tasks"][task_id]
    item.setdefault("history", []).append({"recorded_at": started, "prior_status": item["status"], "prior_implementation": item["implementation"], "event": note})
    item["status"], item["implementation"] = "in_progress", "partial"
    item["verification_scope_notes"] = {"recorded_at": started, "current": note + " 仅切片，整卡八层不提升。"}
state["updated_at"], state["updated_by_task"] = started, "root parallel repair and integration continuity"
assert original == json.dumps(state["tasks"], ensure_ascii=False, sort_keys=True)
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
snapshot = f"""## 当前权威续接 · {started}

主控 codex/full-delivery-recovery@{head}；origin原授权URL。主合已审纯SBOM f6/条件386，依赖48/forward0017–19/PGgraph/default图此前已合。G-C仍in_progress/partial，无阶段push；最后已核远端G-B c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7。保护用户frontend/tsconfig.tsbuildinfo。原60T/history/金标/阈值不改。G-D/G-E首次文档06:39:55+08，只独立准备不意味着跨门。

来源服务真正运行：D:/wt/r06-live-e310-20261016产品e310，D:/dianzi-runtime-cache/r06-live-e310-run-20261016工具44。实际窗口06:19:43.758521–12:19:43.758521+08，450total/prestop410/35100HTTPS保守上界/21600s/0model-provider；CPU1200sec与每process512MiB/总2GiB等原上限不变。06:46状态42jobs(34成功4blocked4partial)，8源normalized，arxiv仅failed且generation未进；未知发布时间与初采过6h实数保留，费用/wireunknown，不能称P1达标。控制入口D:/dianzi-runtime-cache/r06-live-e310-operations-20261016/startup_handoff.json；status用pwsh7 -NoProfile -File .../launch.ps1 -Mode status，Windows PowerShell5的AsPlainText不支持故失败，不改服务。private env只内存。PID supervisor47464/launcher36008/worker6412/beat48352/API10532/observer47076以kernel创建时间复核，不按旧PID误杀。WSL截止2026-10-17T21:49:15+08。

本轮分派10路职责（并非声明持续同时running）：root公共合同/0020–23/Git/集成/状态；R07scopefix D:/wt/r07-idempotency-scope 唯一job_service writer；R07taxonomy原独立reviewer D:/wt/r07-input-review1 仅复核4c；R11PG作者D:/wt/r11-pg-assessments 唯一rule/assessment内部5文件；R11SBOM作者D:/wt/r11-sbom-inventory 唯一assets库存/DTO安全投影writer与原独立reviewer新冻复核；R17原reviewer D:/wt/r17-assets-review1-fix1 仅读f9；archive第十批canonical原bytes，不碰attrs/业务；R12作者D:/wt/r12-conversation-design仅读旧问答+提设计；新r10_neo4j_projection_design D:/wt/r10-neo4j-design仅读图+提设计。root0030公共schema等不授权其他writer；新实现首审必须新非作者，后修原reviewer可复核；无子Agentpush/accepted/progress/递归spawn。

阻断与根因：R07default e61初审47e两个真实幂等409红，scope-v2作者修仍awaitingreview；taxonomy7a/4c官方schema126红保留、review独立资源重跑；PGd56/ad初审f92两原文损坏仍current红，共同loader修；SBOM089/c036同根因unsafeURI/ref/encodedpurl泄漏，需要只读安全投影及alias/历史反例，原raw/hash不变；资产UI1acf/6db初审f5 DOM残留M01，a25/f9原reviewer复核；R12ba/d3/fdd限定Ship后root0020/defaultworker/API接线仍缺。旧CPU严格<1s红、全unit2208/6red不删，不因来源守卫准备Ship称R20通过。

第九归档493new/0drift已封；第十归档先R12fix72(fdd/a66)、后R07default90、R17assets80、R11PG80原红报告，未封WIP不copy。主控本轮不修改attrs直到archive释放。来源正在写的private日志不混入冻结包，actual扫描与原hash/脱敏hash分别保留，GitLF和rawbytes分开，unknown expected null。

外部仍双人独立label/裁决未知、FOFA授权资产scope未知、CNNVD IAB登录未确认不取cookie、ZoomEye401；Hunter/Quake服务聚合非受影响资产数。PPT按用户后置非删范围。正式label/live/gold/盲测/3→5产品/性能/cleanrepro/WordPDF演示仍未完成。holdout不入索引/产品/一般Agent上下文。

下一动作：archive优先R12fix完成→root守卫主合d3→独立WT 0020生产前向迁移/真实indexerworker装配；四Must修复冻结→原reviewer逐负例复验→才可主合；root冻结多轮/Neo4j设计后分工真实实现；source有限status与终段记录并行，不sleep等待。R14–R24未闭合继续按能力前置推进，R24-A→R23→R24-B不变。

"""
for name in ("context_handoff.md", "recovery_workstreams.md", "blockers.md"):
    target = ROOT / "progress" / name
    target.write_text(snapshot + target.read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")
ended = now()
stage_path = ROOT / "reports/stages/recovery/G-C.md"
stage = stage_path.read_text(encoding="utf-8-sig")
for prefix, value in (("本次写作开始时间：", started), ("本次写作结束时间：", ended), ("最后更新时间：", ended), ("本报告证据截止时间：", started)):
    stage = "\n".join(prefix + value if line.startswith(prefix) else line for line in stage.splitlines()) + "\n"
stage = stage.replace("## 2. 当前真实状态与修改\n", "## 2. 当前真实状态与修改\n\n" + snapshot, 1)
stage += f"\n{ended} /root修订：acfe已审纯切片主合、source真实启动与有限状态、四Must修复/独立复核和两新设计准备所有权；原T与整门不提升。\n"
stage_path.write_text(stage, encoding="utf-8", newline="\n")
receipt = {"started_at": started, "ended_at": ended, "head": head, "original_T_tasks_unchanged": True, "original_T_tasks_sha256": hashlib.sha256(original.encode()).hexdigest(), "whole_cards_accepted": [], "stage": "G-C in_progress/partial", "push": "not_run", "assigned_workstreams": 10}
(RUN / "parallel_progress_current_20261016_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
