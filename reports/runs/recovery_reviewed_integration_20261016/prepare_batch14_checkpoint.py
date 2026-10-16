"""Freeze only verified integration inputs and truthful progress for new independent reviews."""

import copy
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


assert git("rev-parse", "HEAD").decode().strip() == "bc089809c03472582f6256b495a6f9a2a308a5d2"
assert not git("diff", "--cached", "--name-only").strip()
assert hashlib.sha256((ROOT / "frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest() == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
selected = set()
for name in ("mode_budget_batch14_inputs.json", "pool_lifecycle_batch14_inputs.json"):
    manifest = json.loads((RUN / name).read_text(), object_pairs_hook=strict_object)
    for item in manifest["files"]:
        assert hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() == item["sha256"]
        selected.add(item["path"])
    selected.add((RUN / name).relative_to(ROOT).as_posix())
for name in ("test_incoming_checkpoint_unknown.py", "test_remaining_unknown_paths.py", "test_review_unknown_read_stops.py", "test_all_tool_latches.py", "original_graph_unknown_samples.json"):
    relative = "reports/runs/r14_source_report_output_budget_20261017/" + name
    assert (ROOT / relative).read_bytes() == git("show", "7b1747cd1322957bc9f9b24b49bf28012e17fd9e:" + relative)
    selected.add(relative)
stamp = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
note = f"""\n\n## {stamp} · 主控批次14冻结，未验收阶段

Root基线bc089809，完整导入R06 ff972ebb/R14 db922460/R01 dbf99272的25冻结文件；修订mode错误、SourceEnricher消费者、UTF8累计预算、Engine释放修复已接线，新的整合PG独审待运行。Root模式/预算/释放联合783例passed/0fail/0error/0skip，配置36例passed（单列不相加），mypy204源码passed、Ruff14和format14passed。原Root遗漏冻结样本导致8 FileNotFound/误拼settings路径/配置继承fixture/样式E501红均保留。

Source实际独立912控制器03:34:02.196146至03:34:22.012818提前退出19.816672秒，formal_six_hour_pass=false；不是6h持续采集。fixed控制前置b7a1244独审通过，七门Root登记，不证明实际五actor完成。首API确定缺langchain_core：launch选旧runtime_env，与冻结产品锁不一致；worker未到ready，原收据不足区分15秒timeout与launcher exit。新独立诊断见R06-first-912-start-diagnosis.md。历史ledger42是已用/总450，不是cap42；余408，不reset。actor/MinIO退出ACK保存，不复用旧窗口冒同版本稳定。离线缺38包已安装，库存96同锁，模块smoke/完整重启仍待验证，不能据库存签ready。

并行：R17新独审d7d3068对8e4发现M01刷新竞态，779distinct既有用例/Edge11fixture通过不消除该红；作者在新WT修所有subscription caller。R19新独审8f326cd仅3文件Ship/69fixture，人工gold0。R18独立适配与assessment同事务read由唯一作者实现；Root持有App/QA身份/seletor/typedtaskbinding。R10默认worker工厂CR已经登记，后续独立作者复用Neo4j与PG/租约/graph policy；公开schema、迁移/lock仍Root独占。R20 strict1CPU红仍未关闭，产品默认30与startup诊断不同，不能下调门槛。

宿主16Agent槽，按能力依赖滚动6–10包；运行资源另行独占，普通完整进程10/60s、CBM16/60s、Edge16有界。默认shell/profile共同延迟已通过显式C:/Program Files/PowerShell/7/pwsh.exe、login=false恢复；原长延迟未洗成合规。真实Source成本unknown，本轮模型/测绘paid调用0。无新阶段放行/push，G-C仍in_progress/partial；用户tsbuildinfo/push台账保护。人工双标/授权资产/CNNVD登录仍缺，最终未验收。
"""
for relative in ("progress/context_handoff.md", "progress/blockers.md", "progress/recovery_workstreams.md", "reports/stages/recovery/G-C.md"):
    with (ROOT / relative).open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(note)
    selected.add(relative)
state_path = ROOT / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
original_tasks = copy.deepcopy(state["tasks"])
for task_id in ("R01", "R06", "R07", "R10", "R14", "R17", "R18", "R19", "R20"):
    task = state["recovery_tasks"][task_id]
    task.setdefault("history", []).append({"recorded_at": stamp, "source": "Root-batch14-integration checkpoint", "status_preserved": task["status"], "implementation_preserved": task["implementation"], "note": note.strip(), "new_whole_task_accepted": False})
state["updated_at"] = stamp
state["updated_by_task"] = "R00-R24-controller-batch14-code-freeze-and-actual-source-start-failure"
assert state["tasks"] == original_tasks and len(original_tasks) == 60
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
selected.add("progress/task_state.json")
report = ROOT / "reports/tasks/Root-batch14-integration.md"
assert not report.exists()
report.write_text(f"""# Root · 批次14修订模式、调查预算与连接释放

文档首次创建时间：{stamp}
本次写作开始/结束时间：{stamp} / {stamp}
最后更新时间与证据截止：{stamp}
工作分支：codex/full-delivery-recovery
代码基线：bc089809c03472582f6256b495a6f9a2a308a5d2
状态：awaiting_review；实现partial；不签整卡/阶段，不push。

25个冻结作者输入原字节核验，两个R07直属合成输入显式fixture，原24诊断和业务Oracle保留。复用现有readers、SourceReportReader、PG共享workflow预算/版本和Engine，必要新增是共同mode分类器、消费者注入与两finally；无新依赖/迁移或评分变更。v2混合/未知历史仍明确503，完整历史体验尚未完成。

Root783联合离线回归全通过；原红775pass+8missing sample因Root材料闭包遗漏，修复拷贝原冻结样本后原件复跑783。Graph配置36单独通过，新增18用例与老用例不简单累计；原继承fixture及拼错文件的red保留。mypy204源码、Ruff14、format14通过。普通窗口峰6–8/10、残留0；精确命令/+08起止/退出/原始日志位于同run.command.json/stdout/stderr/XML。PG/security/frontend/e2e/live/manual该整合批not_run；作者/先前独审PG不能替代本新整合源码复验。

CR-R06/CR-R14落实当前切片，CR-R10配置已进入本次源码，默认图工厂/worker尚未实现。代码索引bc旧图不得审新代码；本freeze之后刷新新独立索引并新reviewer复验mode真实PG8、预算PG12/defaultservice以及连接释放。当前来源独立912首次startup失败是真实失败，见下文；没有跨版本拼稳定时段。冻结报告SHA、已审代码SHA与后续pushSHA分别记录。
{note}
""", encoding="utf-8", newline="\n")
selected.update({"reports/tasks/Root-batch14-integration.md", "backend/src/ai_intel/infrastructure/settings.py", "backend/tests/unit/test_r10_graph_runtime_settings.py", "docs/decisions/CR-R06_revision_mode_read_projection.md", "docs/decisions/CR-R14_source_report_output_accounting.md", "docs/decisions/CR-R10_default_graph_runtime.md"})
for prefix in ("mode_budget_batch14_", "pool_lifecycle_batch14_", "graph_settings_batch14_", "integrated_batch14_"):
    selected.update(path.relative_to(ROOT).as_posix() for path in RUN.glob(prefix + "*.command.json"))
    selected.update(path.relative_to(ROOT).as_posix() for path in RUN.glob(prefix + "*.counts.json"))
for name in ("batch13_checks_helper.py", "batch13_process_metadata.py", "integrate_mode_budget_batch14.py", "integrate_pool_lifecycle_batch14.py", "check_mode_budget_batch14.py", "prepare_batch14_checkpoint.py"):
    selected.add((RUN / name).relative_to(ROOT).as_posix())
receipt_path = RUN / "batch14_checkpoint_selection.json"
receipt = {"recorded_at": stamp, "baseline_sha": "bc089809c03472582f6256b495a6f9a2a308a5d2", "selected": sorted(selected), "stage_accepted": False, "original_60_task_records_preserved": True, "push": "not_run"}
receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
selected.add(receipt_path.relative_to(ROOT).as_posix())
assert "frontend/tsconfig.tsbuildinfo" not in selected and "reports/push/recovery_push_log.jsonl" not in selected
subprocess.run(["git", "add", "--", *sorted(selected)], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
print(json.dumps({"recorded_at": stamp, "explicit_files_staged": len(selected), "stage_accepted": False, "push": "not_run"}))
