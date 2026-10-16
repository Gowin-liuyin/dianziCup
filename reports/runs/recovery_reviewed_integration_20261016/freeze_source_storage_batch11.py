"""Freeze explicitly reviewed sources and preserve separate integration evidence layers."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as element_tree
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent


def timestamp():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


started = timestamp()
baseline = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
if baseline != "a576fc1f88cd82bc13e5bed9a4c7a013bb8cd74b":
    raise RuntimeError("integration baseline changed")
if subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT).strip():
    raise RuntimeError("existing staged files are not owned by this batch")
user_file = ROOT / "frontend/tsconfig.tsbuildinfo"
expected_user_hash = "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
if hashlib.sha256(user_file.read_bytes()).hexdigest() != expected_user_hash:
    raise RuntimeError("protected user file changed")
inputs = []
for name in ("source_storage_batch11_inputs.json", "completion_guard_batch11_inputs.json"):
    inputs.extend(json.loads((RUN / name).read_text(encoding="utf-8"), object_pairs_hook=unique_object)["files"])
for item in inputs:
    if hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() != item["raw_sha256"]:
        raise RuntimeError("reviewed source byte mismatch: " + item["path"])
checks = json.loads((RUN / "source_storage_batch11_checks.json").read_text(encoding="utf-8"))
if len(checks) != 4 or any(item["exit_code"] for item in checks):
    raise RuntimeError("self-checks not passed")
xml_root = element_tree.parse(RUN / "source_storage_batch11_offline.xml").getroot()
suites = xml_root.findall("testsuite")
counts = {name: sum(int(suite.attrib.get(name, 0)) for suite in suites) for name in ("tests", "failures", "errors", "skipped")}
if counts != {"tests": 339, "failures": 0, "errors": 0, "skipped": 0}:
    raise RuntimeError("unexpected unit/contract counts")

section = f"""\n## 当前集成证据与滚动并行 · {started}

本次写作开始时间：{started}；证据截止时间同写作开始。Root 基线 {baseline}，batch11 是未放行阶段的 checkpoint；G-C/G-D/G-E/G-F 均 in_progress/partial，整卡各层未因此改绿。origin 2026-10-17T00:37:39+08:00实际读取仍为授权URL；本批尚未push，最后已核远端仍G-B c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7。

复用与必要新增：来源保存链复用 SourceResponse 与既有不可变修订，来自 a3e918ac 的服务器可信 data_mode 不信任远端 metadata，mode 改变产生新修订而不覆盖旧历史；Root 默认 worker 仅注入已有 settings.data_mode，新增2个注册回归。文件存储复用标准库 os.link 做原子排他发布，保留原主异常和 foreign 文件，NTFS以外无成功承诺。Detached 完成端口沿已有 fresh PG transaction、租约/attempt/完成逻辑增加可选四参数guard，None兼容，不新增状态权威、数据库表或依赖。

独立源审查：模式 source a3e918ac268fa4a7dcddd89a849ec406faf331b8 / review dcf1701ee258b3464d2d67de4844b2b97b82799d（386离线+12真实PG）；存储 source e2f11a687dfe1c3d7b9cbde61ab6c5ba299661c7 / review cdfeff49c92dfc34da36b41f0f54b859cabe293d（233不同离线，仅NTFS）；完成端口 source 968c71b6ed5e3991edd49bedfef765b36fdbda3d / review e98f82f8dd3a40b1f617a77ab0a4457c66dfb849（158离线+27真实PG）。这些限定源结论不代签Root新组合/default/live/fan-in，审查材料在各自冻结WT/Git提交中可复取。

Root本批实际自检：工作目录D:/dianzi/backend；2026-10-17T00:17:25+08:00至00:17:37+08:00，21明确相关unit/contract文件339passed/0fail/error/skip，mypy6源、Ruff7文件和backend100 format检查均exit0。原命令/日志/XML/起止时间在 reports/runs/recovery_reviewed_integration_20261016/source_storage_batch11_checks.json 与同前缀文件。此批无PG/Redis/model/sourceHTTP；integration/security/frontend/e2e/live/manual=not_run。此前各模块真实PG不拼成此新组合通过，测试时长不称持续采集。

CBM本批2026-10-17T00:31:04+08:00至00:31:28+08:00：当前backend/src独立缓存，2803nodes/16382edges，parsepartial/unusable0；index/schema/architecture/workflow.tool/consume_job五命令exit0，source_storage_batch11_index_source_files.json保存当前WIP逐源hash，cross-check源码/rg。秘密、fixtures、holdout、报告不入索引；缓存留工作区外。工具完整并发cap没有本批采样，not_run，不能冒充资源验证通过。

问题/传播：R14 read fix1的真实复验298=294passed/4failed，其中37PG通过；4红为 compare_versions未知后仍inventory及旧Assessor已完成节点恢复时三策略停止原因错误。冻结修复者新WT只workflow/graph+直属tests，原Oracle不改。R14默认broker单独原case已执行返回，但composite因共享fixture权限错误失败，恢复/重启段未执行，仍待复核。Root UI独审82frontend/64backend/474SDK/12diagnostic通过，但真实Edge首屏超时/0业务断言/ordinary consume未运行；新诊断只入口，不以组件测试替代浏览器成功。所有失败原日志保留。

并行所有权：Root独占公共合同/配置/schema/迁移/锁/progress/App/Git。r14_unknown_boundary_root_cause_fix2仅workflow/graph、新tests；r17_browser_entry_timeout_diagnosis仅自己诊断脚本/报告；r18_public_producer_fix2_independent_recheck只审c8ab/3b冻结公开读取；r07_default_bridge_consumer_implementation只reader factory和直属tests，真实Root consumer尚未接。两旧独审只封存/复核，不修改业务，未签全卡accepted，子Agent不push。最多16宿主槽，实际滚动分工而非虚构后台。

合同差异：CR-R16_completion_fanin于2026-10-17T00:31:04+08:00补本attempt typed verified-bytes、64MiB去重/原R11较低限、精确owner/context/epoch/CAS与无外部IO finalguard；消费者source d550仍需新独审。原T卡验收、two-types、金标/阈值/分母不变。只有原page-budget指针按completion manifest解析获准，原drive retry Oracle未实跑先保留。source-mode CR b578未新增公共schema。

下一步：冻结本batch11给新的非作者默认入口/真实PG/单来源验收；通过后创建干净Product fullSHA，重绑定已审CORE/OPS，由新激活审查者检查schema0030/DB OID+COMMENT/nonce/预算，实际启动同版本受控6h。旧Product1cdb不得启动，新窗口尚未开始。父PG资源deadline 2026-10-17T21:49:15+08:00不延长。R16 fan-in、历史/撤回/negative watch、公开tasks/ask/stack/HTTP-MCP及三插件、R19人工金标、R20秘密/CPU/CI/索引恢复、R21/R22/R24仍有内部工作；不能称只剩外部。

评分证据范围：F1/E1支持可信来源模式与原文原子保存；A1/E1支持内部最终事务guard。九维/来源广度/完整Agent/准确率/P95/正式分母与6h稳定运行本批没有新结果。费用unknown，无本批产品API付费调用。用户tsbuildinfo rawSHA {expected_user_hash}未改未stage，push ledger未纳本批。

本次写作结束时间：{{ended}}；修订原因：精确集成3份已独审源，保留新组合证据限制与4红传播；修订人Root。
"""

state_path = ROOT / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
original_tasks = json.dumps(state["tasks"], ensure_ascii=False, sort_keys=True)
events = {
    "R03": "batch11精确合已独审968/e98 optional completion guard；Root339相关unit/contract通过，Root最终PG/consumer另审，不验收整卡。",
    "R06": "batch11合a3模式持久化，Root默认worker trusted data_mode注入2例通过；独审dcf的12PG不代签Root组合，新6h未启动。",
    "R14": "read fix1独立298例294pass/4fail，其中37真实PGpassed；未知工具后续读取和恢复stop_reason4红未关闭；新共同根因fix2独立WT，整卡partial/needs_changes范围保留。",
    "R16": "author d550/032 fan-in194离线，3PG仅collect；RootCR补typed content reuse，consumer新非作者待审，完整传播/history/retraction未验。",
    "R17": "Roota576独审真实Edge首屏超时0业务断言，默认尚未Ship；新入口诊断，82前端/64后端/474SDK/12诊断不替代业务e2e。",
    "R18": "3b/c8 public producer fix2新非作者复核，Root未装配；SDK限定Ship不等于六工具REST/MCP/三插件完成。",
    "R20": "batch11合e2f/cdfe排他文件发布/FD错误保留修复，Root相关unit/contract通过，仅NTFS；完整秘密/CPU/备份索引恢复/CI未验。",
}
for task_id, event in events.items():
    task = state["recovery_tasks"][task_id]
    task.setdefault("history", []).append({"recorded_at": started, "event": event, "root_baseline_sha": baseline, "whole_task_accepted": False})
    task.setdefault("notes", []).append(event)
if json.dumps(state["tasks"], ensure_ascii=False, sort_keys=True) != original_tasks:
    raise RuntimeError("original T-state changed")
state["updated_at"] = started
state["updated_by_task"] = "R00-R24-controller-integration-batch11"
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
ended = timestamp()
section = section.replace("{ended}", ended)
documents = ["progress/context_handoff.md", "progress/recovery_workstreams.md", "progress/blockers.md"]
for relative in documents:
    path = ROOT / relative
    path.write_text(section.lstrip() + "\n" + path.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
for relative in ["reports/tasks/R03.md", "reports/stages/recovery/G-C.md", "reports/stages/recovery/G-D.md", "reports/stages/recovery/G-E.md", "reports/stages/recovery/G-F.md"]:
    path = ROOT / relative
    path.write_text(path.read_text(encoding="utf-8") + section, encoding="utf-8", newline="\n")
report = ROOT / "reports/tasks/Root-source-storage-batch11.md"
report.write_text(f"# Root · 可信模式、原文发布和任务原子完成组合\n\n文档首次创建时间：{started}\n任务状态：awaiting_review\n实现状态：partial\n" + section, encoding="utf-8", newline="\n")

run_names = [
    "integrate_source_storage_batch11.py", "source_storage_batch11_inputs.json",
    "integrate_completion_guard_batch11.py", "completion_guard_batch11_inputs.json",
    "check_source_storage_batch11.py", "source_storage_batch11_checks.json",
    "source_storage_batch11_offline.json", "source_storage_batch11_offline.log", "source_storage_batch11_offline.xml",
    "source_storage_batch11_mypy.json", "source_storage_batch11_mypy.log",
    "source_storage_batch11_ruff.json", "source_storage_batch11_ruff.log",
    "source_storage_batch11_format.json", "source_storage_batch11_format.log",
    "refresh_source_storage_batch11_index.py", "source_storage_batch11_cbm_receipts.json",
    "source_storage_batch11_index_source_files.json", "source_storage_batch11_cbm_index.log",
    "source_storage_batch11_cbm_schema.log", "source_storage_batch11_cbm_architecture.log",
    "source_storage_batch11_cbm_workflow_tool.log", "source_storage_batch11_cbm_default_consumer.log",
    "append_fanin_proof_contract.py", "fanin_proof_contract_receipt.json", "freeze_source_storage_batch11.py",
]
code_paths = [item["path"] for item in inputs] + ["backend/src/ai_intel/workers/runtime.py", "backend/tests/unit/test_r06_default_worker_data_mode.py"]
paths = [*code_paths, "docs/decisions/CR-R16_completion_fanin.md", "progress/task_state.json", *documents,
    "reports/tasks/R03.md", report.relative_to(ROOT).as_posix(),
    *("reports/stages/recovery/" + stage + ".md" for stage in ("G-C", "G-D", "G-E", "G-F")),
    *((RUN / name).relative_to(ROOT).as_posix() for name in run_names), ".gitattributes"]
attribute_path = ROOT / ".gitattributes"
attributes = attribute_path.read_text(encoding="utf-8").splitlines()
for name in run_names:
    if Path(name).suffix in {".log", ".xml"}:
        relative = (RUN / name).relative_to(ROOT).as_posix()
        if any(line.split(" ", 1)[0] == relative for line in attributes):
            raise RuntimeError("unexpected existing raw attributes")
        raw = (RUN / name).read_bytes()
        if any(line.endswith((b" ", b"\t")) for line in raw.replace(b"\r\n", b"\n").splitlines()):
            raise RuntimeError("actual non-CR trailing whitespace requires explicit investigation")
        attributes.append(relative + " -text whitespace=trailing-space,space-before-tab,cr-at-eol")
attribute_path.write_text("\n".join(attributes) + "\n", encoding="utf-8", newline="\n")
commands = []
for label, command in [
    ("add", ["git", "add", "--", *paths]),
    ("boundary", [str(ROOT / "backend/.venv/Scripts/python.exe"), "-I", str(RUN / "check_staged_boundary.py")]),
    ("diff", ["git", "diff", "--cached", "--check"]),
]:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=120)
    (RUN / ("source_storage_batch11_checkpoint_" + label + ".log")).write_bytes(result.stdout + result.stderr)
    commands.append({"label": label, "command": command, "exit_code": result.returncode})
    if result.returncode:
        raise RuntimeError("freeze stopped before next step: " + label)
staged = set(subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"], cwd=ROOT).decode().split("\0")) - {""}
if staged != set(paths):
    raise RuntimeError("staged path set mismatch")
if hashlib.sha256(user_file.read_bytes()).hexdigest() != expected_user_hash:
    raise RuntimeError("protected user file changed before commit")
result = subprocess.run(["git", "commit", "-m", "checkpoint G-C/G-D: preserve trusted source mode, exclusive content and atomic job completion; default review pending"], cwd=ROOT, capture_output=True, timeout=120)
(RUN / "source_storage_batch11_checkpoint_commit.log").write_bytes(result.stdout + result.stderr)
if result.returncode:
    raise RuntimeError("checkpoint commit failed")
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
receipt = {"started_at": started, "ended_at": timestamp(), "baseline_sha": baseline, "head_sha": head, "paths": paths, "commands": commands, "counts": counts, "stage_accepted": False, "push": "not_run", "protected_user_file_sha256": expected_user_hash}
(RUN / "source_storage_batch11_checkpoint_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"head_sha": head, "files": len(paths), "stage_accepted": False, "push": "not_run"}))
