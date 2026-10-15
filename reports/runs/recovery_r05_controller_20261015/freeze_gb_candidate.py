"""冻结本阶段证据和待审状态，保留原任务及历史失败，不作验收登记。"""

import copy
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[3]
run = Path(__file__).resolve().parent
receipt = run / "gb_candidate_freeze.json"
assert not receipt.exists()
now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def strict_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


stage = root / "reports/stages/recovery/G-B.md"
text = stage.read_text(encoding="utf-8")
text = text.replace("55/48来自两个已退役venv，15/10待逐条fixture来源核验", "55命中/47文件来自两个已退役venv，其余15条精确分类记录覆盖11文件/13唯一span；此前55/48、15/10口述计数已由独立审查撤回")
text = text.replace("精确分类收口仍待完成，security保持failed", "15条已独立核对并精确合并，原36条不变；原安全单测2026-10-15T17:57:58+08:00至2026-10-15T17:58:10+08:00 exit0、1pass。全套新候选待阶段独立复跑，原1418pass/1fail保留")
text = text.replace("整合安全扫描精确分类仍未收口，新的整阶段review未发生，本报告不能过G-B门", "整合安全扫描精确分类已收口并通过原单测；新的整阶段review未发生，本报告仍不能过G-B门")
text = text.replace("下一步：关闭精确fixture分类/缓存收口的安全失败，最终源码/回归/文档冻结", "下一步：最终源码/回归/文档冻结")
text = text.replace("至15:04:34+08:00", "至2026-10-15T15:04:34+08:00")
text = text.replace("至17:36:59+08:00", "至2026-10-15T17:36:59+08:00")
text = text.replace("段3自16:57:02+08:00", "段3自2026-10-15T16:57:02+08:00")
prefixes = {
    "本次写作开始时间：": now,
    "本次写作结束时间：": now,
    "最后更新时间：": now,
    "本报告证据截止时间：": now,
    "阶段状态：": "awaiting_review",
    "实现状态：": "complete（仅R04/R05本阶段功能候选；原T整卡、R12/R17和后段部署验收不在此提升）",
    "各层验证状态：": "unit/contract/integration/frontend/e2e/live已按所列限定范围通过；security原综合1418pass/1fail已精确修复单项复验passed，新候选全套待独立复跑；manual not_run。整阶段仍awaiting_review",
}
text = "\n".join(next((prefix + value for prefix, value in prefixes.items() if line.startswith(prefix)), line) for line in text.splitlines()) + "\n"
text += f"\n修订：{now}，/root保留首次创建时间与所有红例；核对独立分类校正为15条/11文件/13 span和第三方55/47、实际原单测复验及完整缓存搬迁hash。精确manifest 51条，原36条不变，没有改扫描器/规则/ignore。阶段仅awaiting_review，未accepted、未push。\n"
stage.write_text(text, encoding="utf-8")

state_path = root / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8"), object_pairs_hook=strict_pairs)
old_tasks = copy.deepcopy(state["tasks"])
notes = {
    "R04": "两固定真实源→MinIO原文/不可变revision→PG事件/证据/任务与游标→认证API→真实桌面/390页面闭环；48ad解析、7af API、8f6分页、c83限流及来源UI专项Must已限定关闭。105事件/434证据前向0014迁移identity hash保留。整R04等待新G-B阶段审查。",
    "R05": "dc014事务接线三Must独立关闭：必需key、420s PG预约/owner/expiry CAS、同事务认证锁；32PG/24新PG/8独立进程与竞态探针。root37PG/route/contract及10隔离旧PG安全通过；综合1418pass/1fail后精确分类原安全1pass。真实修复版浏览器单问10212.6966ms，20同模型块复用，2实际供应商attempt；累计8真实调用、费用unknown，不是准确率/性能分母。整卡等待新阶段审查。",
    "R17": "a0a94f1问答前端独立限定Ship：254前端、type/lint/build、9原fixture+11新增浏览器检查；root dc014真实桌面→引用→390/reduced-motion→固定revision→GET重读→退出1pass。动态背景已接，POST90s预算不等于性能目标。完整资产/图谱/推荐/报告/Agent工作台仍partial。",
}
links = {
    "R04": ["reports/stages/recovery/G-B.md"],
    "R05": ["reports/reviews/recovery/G-B-R05-question-pipeline-review-1.md", "reports/reviews/recovery/G-B-secret-fixture-classification.md", "reports/runs/recovery_r05_controller_20261015/product_live_dc014c9/browser.json", "reports/runs/recovery_r05_controller_20261015/gb_security_exact_manifest_recheck.json"],
    "R17": ["reports/reviews/recovery/G-B-R05-question-frontend-review-1.md", "reports/runs/recovery_r05_controller_20261015/product_live_dc014c9/browser.json"],
}
for task_id, note in notes.items():
    task = state["recovery_tasks"][task_id]
    task.setdefault("history", []).append({"recorded_at": now, "prior_status": task["status"], "prior_implementation": task["implementation"], "prior_verification": copy.deepcopy(task["verification"]), "prior_verification_scope_notes": copy.deepcopy(task.get("verification_scope_notes", {})), "event": "Integrated G-B candidate submitted for new independent checkpoint review; no acceptance"})
    task["verification_scope_notes"] = {"current": note, "recorded_at": now, "scope": "G-B candidate evidence; whole card acceptance pending independent checkpoint"}
    if task_id != "R17":
        task["status"] = "awaiting_review"
        task["implementation"] = "complete"
    task["evidence"] = list(dict.fromkeys(task.get("evidence", []) + links[task_id]))
state["updated_at"] = now
state["updated_by_task"] = "G-B integrated candidate freeze, not checkpoint acceptance"
assert state["tasks"] == old_tasks
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

snapshot = f"""## 当前权威快照 · {now}

集成分支codex/full-delivery-recovery；代码HEAD {head}。G-A accepted，远端最后核对fa5deb0d0b519869ca92d34d9ffe7d8e39b06fb4，2026-10-15T15:41:48+08:00。G-B功能候选awaiting_review，未阶段push；整R04/R05仅候选complete，原T整卡状态与全部验收不变。各层整卡verification保持not_run，限定真实证据见G-B报告；不能拿未整卡登记当作无功能，也不能拿组件Ship反推accepted。

{notes['R04']}

{notes['R05']}

{notes['R17']}

所有API/Vite/worker/beat段均已结束，dc014产品段2026-10-15T17:29:17+08:00至2026-10-15T17:44:17+08:00 deadline；MinIO段3仍在，截止2026-10-15T18:57:02+08:00，Docker总截止2026-10-17T21:49:15+08:00。旧两venv原样搬至D:/dianzi-runtime-cache/01a13a70-858c-7d92-8070-0b2693ad7fc4/retired-review-venvs/20261015/，4857/6532文件hash前后相同，历史日志路径不改，映射receipt在controller。没有持续运行时长合并。

四槽当前：root独占共享schema/配置/迁移/锁/进度/集成/Git，冻结G-B并派新阶段reviewer；r06_feed_parsers独占D:/wt/r06-feeds的arxiv_atom.py/trailofbits_rss.py及新tests/run报告，7ed基线，不改公共文件；新r06_source_preparation_independent_review只审e4f docs/sample prep，独立D:/wt/r06-prep-review，不写业务；剩余槽给新G-B checkpoint reviewer。R06 source prep/纯parser可独立于R05付费问答，不能提前签G-C/live。

真实模型累计8次，fee unknown；秘密/模型缓存/连接仓外。容器semantic extra、容量/固定出网待R20部署接线，不能称默认Docker QA已通；Linux来源网络未由Windows成功替证。人工双人金标/裁决与FOFA授权资产范围未给，PPT后置；继续不受影响工作。下一步新G-B reviewer复跑/核对冻结版本→有依据登记阶段/CR/切片→stage commit与授权远端正常push并核对SHA→R06–R10。R24-A→R23→R24-B保持。

"""
for relative in ("progress/context_handoff.md", "progress/blockers.md", "progress/recovery_workstreams.md"):
    path = root / relative
    path.write_text(snapshot + path.read_text(encoding="utf-8"), encoding="utf-8")
for task_id in ("R04", "R05"):
    path = root / f"reports/tasks/{task_id}.md"
    path.write_text(path.read_text(encoding="utf-8") + f"\n## 当前候选更新 · {now}\n\n状态awaiting_review、实现complete仅本R卡阶段切片，尚未整卡accepted。{notes[task_id]}\n\n复用、必要新增、全部问题和命令cwd/起止/exit/数量/日志见reports/stages/recovery/G-B.md及其专项报告。此前本报告的needs_changes/未接通是历史时点，已由固定SHA的独立复核与真实产品证据更新；不删除原失败。正式准确率/召回率/性能、全库多跳与人工验证均未由本卡证明。\n", encoding="utf-8")

untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], cwd=root, text=True).splitlines()
selected = [path for path in untracked if path.startswith(("reports/reviews/recovery/G-B", "reports/runs/recovery_", "reports/security/gb_fixture", "reports/tasks/G-B", "reports/tasks/R04.md")) and not path.startswith(("reports/runs/recovery_r06_", "reports/runs/recovery_gb_checkpoint_"))]
selected += ["progress/task_state.json", "progress/context_handoff.md", "progress/blockers.md", "progress/recovery_workstreams.md", "reports/stages/recovery/G-B.md", "reports/tasks/R05.md", "reports/security/recovery_fixture_false_positives.json", "reports/runs/recovery_r04_minio_segment2_20261015/service.log"]
raw_dirs = sorted({"/".join(path.split("/")[:3]) for path in selected if path.startswith("reports/runs/")})
attributes = "*.log -text -diff\n*.xml -text -diff\n*.json -text\n*.jsonl -text\n*.body -text -diff\n*.diff -text -diff\n*.txt -text -diff\n*.stdout -text -diff\n*.stderr -text -diff\n.coverage* -text -diff\n"
created_attributes = []
for directory in raw_dirs:
    path = root / directory / ".gitattributes"
    if not path.exists():
        path.write_text(attributes, encoding="utf-8")
        selected.append(path.relative_to(root).as_posix())
        created_attributes.append(path.relative_to(root).as_posix())
ended = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
receipt.write_text(json.dumps({"started_at": now, "ended_at": ended, "code_head": head, "stage_status": "awaiting_review", "original_tasks_unchanged": True, "selected_paths": sorted(set(selected)), "local_raw_attributes": created_attributes, "attribute_reason": "Preserve exact raw bytes/hash and original whitespace in named evidence directories; no code/test/scanner ignores", "stage_report_sha256": hashlib.sha256(stage.read_bytes()).hexdigest()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
selected.append(receipt.relative_to(root).as_posix())
for offset in range(0, len(selected), 80):
    subprocess.run(["git", "add", "--", *selected[offset:offset + 80]], cwd=root, check=True, capture_output=True)
print(json.dumps({"started_at": now, "ended_at": ended, "selected_files": len(set(selected)), "local_raw_attributes": len(created_attributes), "stage_status": "awaiting_review", "original_tasks_unchanged": True}))
