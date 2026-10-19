"""Persist current frozen review pipeline and independent stage preparations."""

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


started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert head == "0532c4f58611e068fc7d5b03da984bc57dbad9f2"
state_path = ROOT / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_fields)
original = json.dumps(state["tasks"], ensure_ascii=False, sort_keys=True)
notes = {
    "R06": "新部署tool44c941两个停止Must已原独立reviewer复验关闭，31/6neg/真实ACK/嵌套wholeJob过；root批准450total/prestop410/35100HTTPS/21600s/0model-provider，新clean部署WT仓外，启动核验进行中，未取得6h。e310固定产品与已审组合，不拼旧段。",
    "R07": "root code1f0522/material1b894默认API/worker/图资产读入口已冻结，35真实PG+133选定unitcontract、metadata20、此前194targeted通过，全src128静态过；新非作者defaultdurable reviewer审整个281/595/b183/1f，尚未合main。taxonomy/selection7dae→9c修复中，独立URI/YAML typedkey重复及omitted-context掩坏fixed边界Must开放。",
    "R08": "主5f已经合已审0017–19前向DDL，聚合持久缓存先前已e310；R08 available→富化事实发布、默认Redis/外部实时重读仍待真实接线。",
    "R10": "已审graph1.2 ff5现main93529，已审defaultgraphApp164现main114409，主5f组合候选；root1f默认backendgraphfactory新独立审查中；Neo4j投影/live未验收。",
    "R11": "pureSBOMf6+48依赖、pure条件ddf/386新独立有限Ship均待main合，第九归档core304优先完。root sidecar Table seam0532静态/DDLassert冻结awaitingreview，生产0022not_run。新SBOM库存capacity0892候选自检337pure/28PG+46旧PG，待新review。T28 PG Agent31与354related绿，public epoch projection/fullscope map、规则family仅1published/显式retire策略末轮补证，待冻结；0021仍root。",
    "R12": "旧hybrid四合法writer窗口Must原红封存；ba1548 fix/materiald3f553，原64+31真实PGOS/5线程对照作者绿，原reviewer新WT定向复核中，不以旧绿背新SHA；0020/worker/多跳API未完成。",
    "R17": "资产UI code1acf491/material6db161，447/12Edge作者绿，已新非作者assetsreviewer；只JSONCSV目录/当前历史/原bytes导入，SBOM/条件/观察/export未接，live后端not_run。",
    "R20": "所有原严格CPU<1秒红及条件全unit2208/6red保留。source新守卫修复审查过不关闭CPU门，root无新daemon全局权限变动。",
}
for task_id, note in notes.items():
    item = state["recovery_tasks"][task_id]
    item.setdefault("history", []).append({"recorded_at": started, "prior_status": item["status"], "prior_implementation": item["implementation"], "event": note})
    item["status"], item["implementation"] = "in_progress", "partial"
    item["verification_scope_notes"] = {"recorded_at": started, "current": note + " 仅切片，整卡八层不提升。"}
state["updated_at"], state["updated_by_task"] = started, "root default entry freeze and independent review pipeline"
assert original == json.dumps(state["tasks"], ensure_ascii=False, sort_keys=True)
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
snapshot = f"""## 当前权威续接 · {started}

主控 codex/full-delivery-recovery@{head}，origin原授权URL。当前main已有R10 graph1.2/source字段共享极性、R17 default图App、forward0017–19（最终合5f32b90）与root48依赖。0532只SBOM sidecar metadata/CR seam，无生产0022/独立验收。未pushG-C，最后远端仍G-B c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7；保护用户frontend/tsconfig.tsbuildinfo，不stage它。原60T及金标/门槛/history不改。

root D:/wt/r07-enrichment-jobs code1f0522e3f3fb9547ea55136efa64fc589466c992 /材料1b894daaa4523f37600c8ff8f9990c5df534a3fa（144raw manifest7d710ba8...，全blob0diff）。2810017、内部595、b183默认API/worker及1f默认图/资产factory整体新初审r07_default_durable_entry_first_independent_review@D:/wt/r07-default-entry-review1。35真实PG/133选定pure、metadata20通过，之前194targeted和root初红全保留。真实Celery进程/e2e/live/manual未跑，R08 available未连接，prompt/selection指纹/持久coverage还须后续0017扩展前向切片。不要主合未审1b。

活跃10路（本次list_agents实际snapshot含root，宿主16上限）：root共享合同/migrations0020–23/锁/Git/progress/API集成；r06_owned_six_hour_live_runtime_integration在仓外D:/dianzi-runtime-cache/r06-live-e310-run-20261016 detached tool44准备新受控来源；r07_taxonomy_and_bounded_evidence_inputs_implementation@D:/wt/r07-input-capabilities修typedURI/YAMLkey/context混坏值Must，r07_taxonomy_selection_first_independent_review@D:/wt/r07-input-review1只审冻版本；r11_pg_rules_assessment_implementation@D:/wt/r11-pg-assessments独占5内部PG文件/6表提案，root统一0021；r11_sbom_inventory_capacity_integration@D:/wt/r11-sbom-inventory唯一backend assets parser/inventory/routes/contracts/sbom_inventory writer，root表0532已cherry，新capacity自检等新review；r12_hybrid_retrieval_first_independent_review新Fix1 WT审d3/ba，原作者已完成；r17_assets_workbench_first_independent_review@D:/wt/r17-assets-review1审6db/1acf，原UI作者完成；r07_default_durable_entry_first_independent_review审root1b；recovery_frozen_evidence_archive只canonical原bytes，第九批rootattrs实际4e4dd89b锁直到done。所有实现只awaiting_review，独立reviewer不写业务，无subAgent自行push/progress/accepted。

原作者完成和独立Ship分开：T27 pure ddfbf/3865经new f1e reviewer136+25probe+288reg独立Ship，全2208/6CPU红不删；pureSBOM658/f6经newreviewer308+43probe限定Ship、旧10k缺口后续0892修；graph1.2/forwardDDL/default图已reviewed main合，无整阶段通过。第九优先归档304raw（SBOM211sealedgz+5元文件、条件ZIP原bytes88）；R12初Must83及R06新103继续，旧4189保护无漂移，不读cache/secret/holdout。材料SHA/bodyhash/raw-GitLF与sourceSHA区分。

真实持续采集：root已具名批准source450total含旧11、prestop410/solo最大418、5page/max3attempt/35100conservativeHTTPS/21600s，不扩20%/1200CPU/512MiB每process2GiB总、8MiB组件log16MiBobserver。0model/付费provider/RESTsubmit；费用与actualwire unknown，fetch receipt不冒wire。tool44两个停止Must原独立31/6neg/kernelACK/wholeJob复核闭，root依据e310组合有限Ship批准启动前实际PID/端口/PGRedisOS/磁盘/旧owned队列归属，当前实际start尚未报告。旧11067/1187/131秒不能拼6h；WSLdeadline2026-10-17T21:49:15+08。新livegate部署副本不改原44或旧manifest，实际源/MinIO/API等有日志/PID/stop/deadline才称运行。

独立重要Must：R12 finalepoch/finalcandidate合法publish4红，作者ba修窄父行→fresh→scopeepoch锁→事务内构建，原reviewer复验中；R07 taxonomy malformedURI原生异常、SafeLoader true/True typedduplicate、omittedcontext掩fixed99坏值仍开放，原作者修；所有原红保留，不能旧green给新SHA背书。

外部人工：双人label裁决未知/awaiting_human_label、FOFA授权资产范围未知、CNNVD IAB用户登录未确认不读cookies，ZoomEye401。PPT后置不取消；Hunter/Quake只是服务聚合非受影响资产数、费用unknown。完整R13–24、R10Neo4j、R11实体评估/OpenVEX默认API、R12多轮多跳、R14真实九角色、R15/16推荐重判、R18MCP插件、formal eval/repro/doc仍须持续实施，不能用447tests/24旧accepted当百分比。

下一动作：新live实际ready回报并连续观测；第九归档done后显式main合已审pureSBOM/T27→source/PG调用链回归；root1b与6db、9c后修、新0892/PG评估各新审流水线；R12Fix1独立过后root0020迁移/搜索工厂及多轮服务分工。后续独立工作继续，不等6h无界sleep，不改主远端或发布可见性。R24-A→R23→R24-B顺序保持。

"""
for name in ("context_handoff.md", "recovery_workstreams.md", "blockers.md"):
    target = ROOT / "progress" / name
    target.write_text(snapshot + target.read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")
ended = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
stage_path = ROOT / "reports/stages/recovery/G-C.md"
stage = stage_path.read_text(encoding="utf-8-sig")
for prefix, value in (("本次写作开始时间：", started), ("本次写作结束时间：", ended), ("最后更新时间：", ended), ("本报告证据截止时间：", started)):
    stage = "\n".join(prefix + value if line.startswith(prefix) else line for line in stage.splitlines()) + "\n"
stage = stage.replace("## 2. 当前真实状态与修改\n", "## 2. 当前真实状态与修改\n\n" + snapshot, 1)
stage += f"\n{ended} /root修订：主集成5f/0532、root1b冻结新初审、source有限预算授权和实际尚未start、10路所有权/Must/独立Ship限定。firstcreated/原T/整门不提升。\n"
stage_path.write_text(stage, encoding="utf-8", newline="\n")
receipt = {"started_at": started, "ended_at": ended, "head": head, "original_T_tasks_unchanged": True, "original_T_tasks_sha256": hashlib.sha256(original.encode()).hexdigest(), "whole_cards_accepted": [], "stage": "G-C in_progress/partial", "push": "not_run", "active_agents_at_actual_list_snapshot": 10}
(RUN / "parallel_progress_0620_20261016_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
