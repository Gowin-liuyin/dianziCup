"""Record frozen delivery and current file ownership without promoting whole-card gates."""

import hashlib
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
assert head == "136fbaef337036d95229aa4976c1ba49b2e6b04c"
origin = subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=ROOT, text=True).strip()
assert origin == "https://github.com/Gowin-liuyin/dianziCup.git"
path = ROOT / "progress/task_state.json"
state = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_fields)
original_tasks = json.dumps(state["tasks"], sort_keys=True, ensure_ascii=False)
notes = {
    "R06": "批量写入a89/bde已新独立限定Ship：原资源caps下两次execute 1.330/1.514秒，各20文档11827块证据完整核验，0HTTP。待合入。旧8a真实段131秒失败/六小时not_run，服务已全部关闭，禁止拼接。",
    "R07": "单维模型已集成136；发布dc04/材料9e经原独立reviewer234/95PG/203/17通过限定Ship待合。root新工作流合同/0017冻结281，40contract/20PG通过，真实执行Agent已派，API/worker接线仍未完成。",
    "R08": "PG/cache/servicefb1初审320通过但剩余0.5秒写1秒TTL为Must；4a/a763修复41定向通过，新干净WT原独立reviewer复核中。生产0019/RedisIO/暴露发布/live接线not_run。",
    "R09": "知识卡b5已合入136；独立限定通过不等于资料PG/API/检索与真实知识卡模型全部接通。",
    "R10": "1.1初复核仍4稳定负例：否定/未知强边与隐藏租户claim锁。1.2源码11d/最终仅测试08b已冻结，原独立reviewer新WT复核中；默认API/Neo4j/live仍未验收。",
    "R11": "parser37已合136；资产6f/bc独立206+8PG限定Ship，原局部覆盖23.57%<60红保留；生产0018/App/SBOM/条件四态/异步导入/analyst兼容未完成。",
    "R17": "图指针d653/654经原独立reviewer405unit/18Edge/3probe限定Ship，实际重叠边chooser正确。新独立WT实施默认App路由及严格1.2识别，后端真实浏览器联测尚not_run。",
    "R20": "早bootstrap/父handle监督abc/4eb已封存，严格<1秒实测1.03125仍红；新非作者审查有界≤12primary。不能以一次原4行为通过或coverage exit1关闭原硬CPU门。",
}
for task_id, note in notes.items():
    item = state["recovery_tasks"][task_id]
    item.setdefault("history", []).append({"recorded_at": started, "prior_status": item["status"], "prior_implementation": item["implementation"], "event": note})
    item["status"], item["implementation"] = "in_progress", "partial"
    item["verification_scope_notes"] = {"recorded_at": started, "current": note + " 仅切片结论，整卡八层验证不提升。"}
state["updated_at"], state["updated_by_task"] = started, "frozen slice integration and parallel execution"
assert json.dumps(state["tasks"], sort_keys=True, ensure_ascii=False) == original_tasks
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
snapshot = f"""## 当前权威续接与文件所有权 · {started}

主控分支codex/full-delivery-recovery@{head}，origin已核授权URL。已合R09b5、R11parser37、R07single b05；最后远端核对仍G-B/c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7，G-C in_progress/partial，无阶段push。原60张T/history/阈值/金标不改；用户frontend/tsconfig.tsbuildinfo修改保护。

当前8路（含root），宿主16上限、用户期望6–10：root独占合同/schema/0017–0019迁移、API/统一job路由/worker运行注册、集成Git/progress；r07_durable_enrichment_job_execution_implementation独占D:/wt/r07-enrichment-execution@281的内部job_service/handlers与直属新测试；r17_graph_default_workbench_integration独占D:/wt/r17-graph-app的App/hash/图元数据/详情导航及直属前端测试；r10_pg_evidence_graph_read_implementation仅D:/wt/r10-graph-fix2作者测试与封存；r10_pg_evidence_graph_independent_review在新D:/wt/r10-graph-recheck2只复核08b；r08_aggregate_persistence_first_independent_review在新D:/wt/r08-persistence-recheck1只复核a763；r20_early_cpu_bootstrap_first_independent_review在新D:/wt/r20-early-review1只审4eb、≤12primary；recovery_frozen_evidence_archive只canonical manifest列出的报告/原bytes，不碰业务或attrs。一级Agent不得递归spawn、push、改progress或accepted。

root工作流WT D:/wt/r07-enrichment-jobs@281371b072a696d972aa3c38519b8646393c98e2，0017与请求/server policy模型已冻结，40contract/20真实PG及静态通过。该WT已合经审pub9e/single，原生执行服务由Agent接，root并行API与运行装配；root代码必须交其它新reviewer。发布dc04/9e原reviewer已限定Ship，批量证据a89/bde新独立原caps两次1.330/1.514秒限定Ship，等待第六批归档结束后root合入，不能先假定main已具备。

R08 TTL边界4a/a763已修待复核；R10新1.2共享field_sources极性/新可见claim围栏11d、08b仅补8PG测试，旧1.1四red/原33分母保存；图UI指针654已限定Ship但默认App及真实后端联测另批。R11资产bc已独立206+8PG限定Ship，0018生产迁移由root。R20早启动4eb仍严格CPU红，新独立审查不降低阈值、不以局部coverage红冒充全绿。

当前API/worker/frontend/collector/MinIO自有服务全部关闭；PG25432/Redis26379/OpenSearch29200上次有真实存活记录，需下次实测；WSL截止2026-10-17T21:49:15+08。真实131秒段、11067秒旧段、1187秒旧段不能拼成同版本六小时。受控新段必须产品批量修复已审合入、watchdog与DoH有限预算重新独立核对后另run启动。事实/任务PG权威，缓存/图只投影。

资源缺口仍双人独立标注/裁决awaiting_human_label、FOFA授权资产范围未知、CNNVD用户IAB登录未确认、ZoomEye401；Hunter/Quake四次真实聚合仅服务总量，observed/fee unknown。不读取秘密/holdout到报告或代码索引；PPT按用户后置。原G-A/B限定历史结论不升级，后续R12–R24仍须继续。

下一步：第六批归档完成→主控合pub9e/bulkbde→共享调用方回归/新索引→新有界真实持续采集；并行九维持久执行/API、R08/R10复核、图默认App、0018/0019生产迁移与R20独立安全审查。每个新实现批次冻SHA后新初审，阶段跨越按新阶段reviewer门槛，不因切片Ship或时间点自行通过。

"""
for name in ("context_handoff.md", "recovery_workstreams.md", "blockers.md"):
    target = ROOT / "progress" / name
    target.write_text(snapshot + target.read_text(encoding="utf-8-sig"), encoding="utf-8")
ended = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
stage_path = ROOT / "reports/stages/recovery/G-C.md"
stage = stage_path.read_text(encoding="utf-8-sig")
for prefix, value in (("本次写作开始时间：", started), ("本次写作结束时间：", ended), ("最后更新时间：", ended), ("本报告证据截止时间：", started)):
    stage = "\n".join(prefix + value if line.startswith(prefix) else line for line in stage.splitlines()) + "\n"
stage = stage.replace("## 2. 当前真实状态与修改\n", "## 2. 当前真实状态与修改\n\n" + snapshot, 1)
stage += f"\n{ended} /root修订：按136/281和新冻结材料更新八路所有权及限制，首创时间保留；未登记整卡/阶段accepted。\n"
stage_path.write_text(stage, encoding="utf-8")
receipt = {"started_at": started, "ended_at": ended, "head": head, "origin": origin, "original_T_tasks_unchanged": True, "original_T_tasks_sha256": hashlib.sha256(original_tasks.encode()).hexdigest(), "whole_cards_accepted": [], "stage": "G-C in_progress/partial", "active_at_snapshot": 8}
(Path(__file__).parent / "parallel_progress_0455_20261016_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
