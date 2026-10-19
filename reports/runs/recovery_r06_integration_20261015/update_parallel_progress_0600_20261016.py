"""Register current reviewed slices and ownership without promoting aggregate acceptance."""

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
assert head == "48b56033cf5daf3ce8cfaa710c0acbda7cc2356e"
origin = subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=ROOT, text=True).strip()
assert origin == "https://github.com/Gowin-liuyin/dianziCup.git"
path = ROOT / "progress/task_state.json"
state = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_fields)
original = json.dumps(state["tasks"], sort_keys=True, ensure_ascii=False)
notes = {
    "R06": "e310已合发布/bulk/聚合/资产/图指针五切片；新独立e310组合验证限定可作下次受控来源基线。新6h部署守卫bae准备29绿，但新review真实后代OpenProcess error5时遗留3活进程Must，正在修复，禁止启动。历史11067/1187/131秒独立版本段不拼接，6h尚未取得。",
    "R07": "root WT 0c3a已合内部执行595，API/统一job路由/server policy/worker工厂WIP，6PG/API、133相关unit通过；注册worker全流程新增测试运行中，未冻结/独立审查，不进main。分类输入Agent正在真实CWE4.19/固定ATLAS legacy5.6.0分析，旧org404保留，新org信任规则接线另CR。",
    "R08": "PG/cache TTL切片a763已经e310集成；0019前向DDL独立100PG/78pure/26兼容负例限定Ship但尚未主集成，Redis/真实暴露发布default App尚未连接。",
    "R09": "知识卡b5已经集成，资料model/PG/API/检索全链路尚未整卡验收，真实CWE/ATLAS下载不是知识卡live验收。",
    "R10": "PG只读graph 1.2 fix2 08b/ff5获独立388与原9负例复核限定Ship，canonical最终报告及scope CR已封存；默认API/Neo4j投影/全live仍未集成验收。",
    "R11": "资产bc已e310。0018/19独立前向DDL Ship待主集成；SBOM658/f6a纯308通过，新非作者独立审查中，root48b唯一purl/YAML/stub依赖checkpoint不算阶段。T27 pure最终ddfbf/136直属绿、全unit2208pass6既有CPU失败，旧红保留；新review等最终材料。T28新PG服务Agent先冻结0021提案，不自行发布布尔支持或人工金标。",
    "R12": "hybrid f316/a43d初版独立64fixture+22PG/OS绿；新review使用KnowledgeRepository.publish合法并发更新/撤回确证4窗口返回旧epoch且partial=false Must，作者根因修中。0020/worker/API/multi跳未完成，不得旧绿给修后SHA背书。",
    "R17": "图默认App baa9/164新独立425/6Edge+2鼠标负例限定Ship，待主合及后端真实联测；新资产工作台唯一所有权App/hash与features/assets，读写角色/真实JSONCSV API已冻结，不能伪装条件自查接口就绪。",
    "R20": "早bootstrap4eb新独立有限Ship，仅准备安全改进；独立原CPU4有3fail1pass、新body1.03125仍严格红，96 pure局部cov12.91<60保留。R06非CPU受控来源可独立继续，但当前stop-tree新Must尚未关闭。",
}
for task_id, note in notes.items():
    item = state["recovery_tasks"][task_id]
    item.setdefault("history", []).append({"recorded_at": started, "prior_status": item["status"], "prior_implementation": item["implementation"], "event": note})
    item["status"], item["implementation"] = "in_progress", "partial"
    item["verification_scope_notes"] = {"recorded_at": started, "current": note + " 整卡八层验证不提升。"}
state["updated_at"], state["updated_by_task"] = started, "parallel implementation and frozen independent reviews"
assert original == json.dumps(state["tasks"], sort_keys=True, ensure_ascii=False)
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
snapshot = f"""## 当前权威续接与所有权 · {started}

主控 codex/full-delivery-recovery@{head}；origin授权URL已复核。e310为五个已审服务组合，独立回归限定可作下次来源基线。48b只依赖checkpoint，无阶段通过或push；最后核对远端仍G-B c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7。G-C in_progress/partial，保护用户frontend/tsconfig.tsbuildinfo，原60T/历史/金标/门槛不变。

主控唯一负责共享合同、API/default factory、job路由/worker、schema/0017–0021迁移、锁文件、progress、集成Git和push。root D:/wt/r07-enrichment-jobs@0c3a4816d5c94b76d3f5aa11d30f277334b05970 有API/worker WIP，6真实PG与133unit过，新增注册consume_job PG运行中；需自行检查冻结后新非作者review，尚未main接通。

并行所有权：r07_taxonomy_and_bounded_evidence_inputs_implementation@D:/wt/r07-input-capabilities只新selection/taxonomy+model_fields输入构造；r17_asset_inventory_workbench_implementation@D:/wt/r17-assets-workbench唯一App/hash/新assets UI；r11_pg_rules_assessment_implementation@D:/wt/r11-pg-assessments新增PG规则/研判内部模块与0021提案，不改pure AST；r11_condition_rules_first_independent_review@D:/wt/r11-condition-review1新初审pure final ddfbf等待材料；r11_sbom_first_independent_review@D:/wt/r11-sbom-review1新初审f6a+root48依赖；r12_hybrid_retrieval_first_independent_review@D:/wt/r12-hybrid-review1审a43d/合法writer4窗口Must，r12_hybrid_corpus_retrieval_implementation@D:/wt/r12-hybrid-retrieval只原模块修复；r06_six_hour_restart_guard_first_independent_review@D:/wt/r06-live-restart-review1审新停止器，r06_owned_six_hour_live_runtime_integration@D:/wt/r06-live-restart-prep-20261016修OpenProcess错误Must/封存，productWT D:/wt/r06-live-e310-20261016固定e310；recovery_frozen_evidence_archive只canonical报告/manifest限定原bytes，第八批处理中，不改attrs。所有一级Agent不递归spawn/no push/no progress/accepted；每个新初审为未参与实现的新Agent。

新增Must：检索hybrid.final epoch/candidate读取后合法KnowledgeRepository.publish推进epoch，新claim或withdraw仍返回旧epoch且partial=false；停止器OpenProcess(error5)跳过已验证活后代导致3进程残留。原作者最小修复、原独立reviewer复核后再集成/启动，不把单元绿涂成live。

已完成审查待集成：R10 ff5服务1.2；R17默认图App164；R11/R08生产0018/19 99fec及review b8fe。第八批归档先三组（graphApp/migrations/e310）再R20，6已列工具缓存policy_excluded而不改原858 manifest；review报告的raw/GitLF区分。root在archive完成前不修改main attrs。

PG25432、Redis26379、OpenSearch29200受控WSL预算至2026-10-17T21:49:15+08，实际E5/rerank+PG/OS22只tiny合成索引真实组件证明，不是P3/金标。API/worker/frontend/MinIO/collector未运行。6h新守卫总450含旧11、预停410/solo最大发418、conservative35100 HTTPS需最终具名预算及新独立guard Ship才启动；当前新Must阻断。旧3段分别保存不拼接。

外部/人工保留：双人独立标注裁决awaiting_human_label；FOFA授权资产范围未知；CNNVD用户IAB登录未确认，不读取session/cookies；ZoomEye401；Hunter/Quake真实聚合只是产品服务总量，费用/观测时间unknown。PPT后置不取消，holdout不进入编码上下文/索引/产品。后续R13–24仍需继续，不以切片Ship/局部覆盖/时间点声明整门通过。

下一步：归档完成后主合已审图/App/0018/19；root完成API/worker自检→新review；T27/28与资产UI并行；R12/停止器修复复核；真正启动新固定版本连续采集，再实际模型九维/默认浏览器业务联测。R24-A→R23→R24-B顺序不变。

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
stage += f"\n{ended} /root修订：登记e310/48b、独立发现的两个实际Must及当前文件所有权；firstcreated保留，原T与阶段不提升。\n"
stage_path.write_text(stage, encoding="utf-8", newline="\n")
receipt = {"started_at": started, "ended_at": ended, "head": head, "origin": origin, "original_T_tasks_unchanged": True, "original_T_tasks_sha256": hashlib.sha256(original.encode()).hexdigest(), "whole_cards_accepted": [], "stage": "G-C in_progress/partial", "push": "not_run"}
(RUN / "parallel_progress_0600_20261016_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
