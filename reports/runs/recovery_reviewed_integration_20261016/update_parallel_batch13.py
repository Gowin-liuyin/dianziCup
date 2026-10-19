"""Record real regressions and exclusive work ownership without changing historical acceptance."""

import copy
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
stamp = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


path = ROOT / "progress/task_state.json"
state = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
original_tasks = copy.deepcopy(state["tasks"])
notes = {
    "R01": "当前Root仍含自建Engine释放回归，迁移env/current_migration_revision旧f3真实target3→1→0；新作者912d8b38 8微型/真实PG2通过，新非作者独立8+PG2+42703异常probe通过正冻结报告，Root未合修复。原G-A历史验收保留但不能给当前回归签绿。新PG辅助顺序/日志故障隔离修复另跟进；历史head/SQL6red及作者峰12违规保留。",
    "R06": "修订mode24诊断6pass18fail，Root当前版本仍可能fixture/None标live，verification.unit纠正failed。fixed CR已bc冻结，独立作者实施。控制fix3 7719作者63pass；非作者63+原2负例复核通过，待报告freeze。Product f3连接回归使启动阻断，新912生命周期独审准备接绑定；七门false/同版本6h尚未启动，旧窗口不拼。CNNVD实际新官方tab仍登录页，下载0，blocked_login。",
    "R07": "40冻结文件批次13已Root bc089809完整整合(本卡8)，全部input SHA核对；来源报告reader/caller模式两阶段围栏由R06唯一作者修，SourceEnricher/实际UTF8预算R14作者实现。649 distinct Root离线不是九维全部live通过，强图/QA原支持规则不放宽。",
    "R10": "r10_default_graph_consumer_closure独立972 WT实现图policy，27offline已pass，仅collect PG，真实GraphProjectionStore复用，不覆盖hybrid。Root待正式CR/defaultruntime接线+新独审/Neo4j真实环境；knowledge_change继续partial，不借R16全局签完成。",
    "R14": "Root bc已导入未知/读取共享原件；SourceEnricher真实typed报告及UTF8完成预算新作者独立bc WT，approved CR保留immutable output_bytes reservation，completed实际从JSON派生且所有reserve/recovery一致，新version绑定。PG/live/default完整协作仍未验，不能把现offline等同真Agent全链。",
    "R16": "Root完整ccbdf7eb 11文件已bc整合；Root定点fanin105pass/0skip，原新非作者历史214+2offline/PG26限定通过作为前证不替Root新consumer。两真实asset fixture误范围已修原assert不变。整history/watch/retraction默认live仍partial。",
    "R17": "新default产品独审在bc固定WT准备真实API+浏览器A≤240s；独立实现r17_workbench_visual_and_states仅frontend，以bc及实际ui-design.md d0f10f63为base，小修加载/分页返回/证据提示/真实调查入口/退订旧selection/登录状态，不伪装typedtask可用。旧staticEdge10不是完整业务e2e；用户tsbuildinfo不改。",
    "R18": "四GET已Root默认App挂载bc，107offline含5oldshared重复；新产品非作者DefaultApp实际HTTP/SDK/Auth/浏览器准备，不替换路由业务。typedtask503/ask-stack发布/HTTPMCP/OAuth/三类插件仍未闭；R06独占public read modeclassifier，不共享多writer。",
    "R19": "r19_qualified_annotation_integration从972仅6298完整prepare3文件，writer26/labels25已pass；旧FD独审094只M01不扩签、原资源cap4违规仍红。新CLI大组60s超时exit124，需完整分批复跑原15Oracle，不把12dots计通过。双人工/裁决未取得，gold0/awaiting_human_label。",
    "R20": "新的终态race source a6eadd5f/materiala1e9，focused15/related83重叠不得累加，Native0；fresh独审已派。原normal CPU1.03125仍failed，near held终态1.0不能称预算内误杀，限制不改。全秘密/实际索引恢复/CI/备份全链仍缺，旧有限原始日志/资源违规保留。",
}
for task_id, note in notes.items():
    record = state["recovery_tasks"][task_id]
    event = {"recorded_at": stamp, "event": "batch13_checkpoint_and_parallel_owned_work", "note": note}
    if task_id in {"R01", "R06"}:
        event.update(prior_status=record["status"], prior_implementation=record["implementation"], prior_verification=copy.deepcopy(record["verification"]))
        record["status"] = "needs_changes"
        record["implementation"] = "partial"
        record["verification"]["integration" if task_id == "R01" else "unit"] = "failed"
    record.setdefault("history", []).append(event)
    old_notes = record.get("verification_scope_notes")
    if isinstance(old_notes, dict):
        old_notes["batch13_" + stamp] = note
    else:
        record["verification_scope_notes"] = (str(old_notes or "") + "\n" + stamp + " /root: " + note).strip()
assert state["tasks"] == original_tasks
state["updated_at"] = stamp
state["updated_by_task"] = "R00-R24-controller-batch13-regressions-and-exclusive-parallel-work"
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
table = """
| 工作包 | 独立Agent/基线 | 唯一文件所有权 | 当前证据/结束条件 |
|---|---|---|---|
| R01资源释放实现/复核 | r01_migration_engine_disposal_fix / r01_engine_disposal_first_independent_review，f3→912 | 作者仅env.py、current_migration_revision与新test；reviewer报告 | 作者新PG2，非作者PG2+异常probe已实际通过，等待限定报告；测试辅助修复独立 |
| R06采集启动控制/独审 | r06_same_version_activation_binding_implementation / r06_activation_first_independent_gate，7719固定 | 启动CORE/OPS候选控制及直属test，独审只报告 | 63+原2负例亲跑；Product f3池偏差未闭前七门false/采集0 |
| R06历史模式 | r06_revision_mode_read_root_cause，bc | revision_mode新函数、两reader/两router、R18 classifier、R07 reader围栏+直属fixture | 24原负例、模式历史PG/defaultconsumer严格，不能重写历史 |
| R14来源报告/预算 | r14_source_report_budget_implementation，bc | workflow_service/runtime/graph必要预算调用、直属tests | 新version/immutable reservation/实际UTF8，PG与新独审必需 |
| R10图默认消费者 | r10_default_graph_consumer_closure，972 | 图policy新模块、graph_projection必要内部函数、直属tests | 独立27offline；共享runtime/settings/CR归Root |
| R19标注整合 | r19_qualified_annotation_integration，972 | annotation既有已审3files+直属tests/空白双人证据包 | 26+25offline；原CLI超时保留，人工gold未取得 |
| R17工作台收尾 | r17_workbench_visual_and_states_implementation，bc | frontend/src与直属tests/static asset | 实际参考已读，缺口小修；不碰tsbuildinfo/lock/后端 |
| 默认产品初审 | batch13_default_product_first_independent_review，bc固定 | own报告/探针 | 默认App真实API/SDK、Auth、单Edge≤240s/A；不改业务 |
| R20终态race初审 | r20_terminal_race_first_independent_review，a6eadd固定 | own报告/探针 | 新初审非作者，Native0；CPU原红不能扩签 |
| 当前索引增量定位 | root_batch13_index_refresh，bc | 仅own索引收据/报告 | ≤60s/16，shared worker/config callers；不索引秘密 |
"""
common = f"\n\n## {stamp} · 主控批次13与新并行流水线\n\nRoot固定checkpoint bc089809c03472582f6256b495a6f9a2a308a5d2；不是阶段验收，push尚未发生。442+107-5重叠+105=649 distinct offline，mypy193、Ruff13通过；新PG/e2e/live未运行。原源与状态历史保留，R01/R06新回归不得继续绿。费用unknown；本轮产品paid模型/来源调用0。宿主16slots，滚动约10工作角色；独立WT/唯一写者，不由作者签accepted。\n"
for name in ("progress/context_handoff.md", "progress/blockers.md", "progress/recovery_workstreams.md"):
    with (ROOT / name).open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(common)
        stream.write(table if name.endswith("recovery_workstreams.md") else "\n".join(f"- {key}: {note}" for key, note in notes.items()) + "\n")
with (ROOT / "docs/decisions/CR-R14_source_report_output_accounting.md").open("a", encoding="utf-8", newline="\n") as stream:
    stream.write(f"\n{stamp}，Root：补充不可变表兼容，output_bytes列继续表示原预留；新规则对完成output_json按统一冻结UTF8 JSON派生实际预算，reserved保留原预留，reserve/complete/recovery共用算法且锁workflow/有界操作行。历史不改，无迁移；不能对外把预留列称实际。独审核该落实后验收。\n")
with (ROOT / "docs/decisions/CR-R06_revision_mode_read_projection.md").open("a", encoding="utf-8", newline="\n") as stream:
    stream.write(f"\n{stamp}，Root：模式集合容量复用R18既有2000输入上限，limit2001只检测超限并明确503，不丢历史/改游标/伪空。仅两个直属合成fixture输入改显式fixture（或明确trusted合成live），原业务Oracle与24诊断不改，不计live；所有可见实际修订必须核模式。\n")
print(json.dumps({"recorded_at": stamp, "original_60_tasks_preserved": len(original_tasks), "new_whole_task_accepted": False, "push": "not_run"}))
