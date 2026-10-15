"""保留旧记录，仅登记有证据的局部验证与当前并行分工。"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
NOW = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
HEAD = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def strict_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """重复键不能由JSON读取静默覆盖。"""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


state_path = ROOT / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8"), object_pairs_hook=strict_pairs)
state["updated_at"] = NOW
state["updated_by_task"] = "R01/R02 evidence reconciliation and parallel hacker frontend"
for task_id in ("R01", "R02"):
    record = state["recovery_tasks"][task_id]
    record.setdefault("history", []).append(
        {"recorded_at": NOW, "event": "verified partial implementation, no stage acceptance",
         "prior_status": record["status"], "prior_implementation": record["implementation"],
         "prior_verification": record["verification"].copy()}
    )
    record["implementation"] = "partial"
    record["verification_scope_notes"] = {
        "version_rule": "passed only for the cited frozen subset; not whole-card or stage acceptance",
        "remaining": "R02 dimension PG service/MinIO and R03 executor/cursor still incomplete; no model/source/official metrics",
    }
r01 = state["recovery_tasks"]["R01"]
r01["status"] = "needs_changes"
r01["verification"].update(unit="passed", contract="passed", integration="passed",
                           security="failed", frontend="passed", e2e="not_run")
r01["evidence"] = [
    "reports/reviews/recovery/G-A-R01-behavior-review-1-final-recheck.md",
    "reports/reviews/recovery/G-A-R01-runtime-review-1-cache-recheck.md",
    "reports/reviews/recovery/G-A-R01-search-TLS-review-1.md",
    "reports/tasks/R01-runtime-recovery.md",
]
r01["review_ref"] = "reports/reviews/recovery/G-A-R01-search-TLS-review-1.md"
r01["verification_scope_notes"].update(
    security="TLS showlocals password output and CI fixture Musts open; CR-R10 proposed major upgrade awaits authorization",
    frontend="42 component tests on 9334c35 and historical 3 browser cases on b504; new hacker UI and new PG-default browser not yet verified",
    integration="cache cold restart and 7 search TLS independently passed on their frozen worktrees; not integrated current HEAD",
)
r02 = state["recovery_tasks"]["R02"]
r02["status"] = "in_progress"
r02["verification"].update(unit="passed", contract="passed", integration="passed")
r02["evidence"] = [
    "reports/tasks/R02.md",
    "docs/decisions/CR-R04-R02_implementation_contract.md",
    "reports/runs/recovery_r01_controller_20261014/r02_default_auth_resume.command.json",
    "reports/runs/recovery_r01_controller_20261014/r02_default_auth_resume.xml",
]
r02["verification_scope_notes"].update(
    integration="87 automatic tests, 72.72% coverage: current auth plus default PG factory and 0009 forward schema; knowledge candidate b005021 independently unreviewed and not integrated",
    security="auth failure-log credential rotated/redacted, privacy source166 integrated; no fresh nonauthor acceptance yet",
)
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

snapshot = f"""\n## 当前快照 · {NOW}\n\n分支codex/full-delivery-recovery，HEAD {HEAD}，origin为授权GitHub地址；未有合格阶段push，G-A未过门。root唯一负责合同/迁移/锁/集成/progress/Git。R00及三个切片保持独立accepted；R01 needs_changes/partial，R02 in_progress/partial，不接受整T。\n\n当前四槽：root；r02_knowledge_resume（既有知识WT，代码b005021冻结，50 PG组合/102 unit/207 contract-security作者自检，原始JUnit为准）；hacker_frontend（独立recovery-hacker-ui WT，用户指定先调研后设计再实现黑客风，端口25300）；r01_tls_fix（独立recovery-tls-fix WT，专属CI/TLS fixture/报告脱敏唯一写者）。新批次仍需新非作者review；TLS初审者只做新冻结补丁定向复核，整阶段另新reviewer。\n\n主机中断：02:47后到09:51无连续工作证据；旧WSL supervisor/daemon消失，停止时间unknown。09:59:13–14从同data-root恢复，supervisor18/daemon25、boot a57bd35b，期限仍2026-10-17T21:49:15+08:00。14原容器恢复健康，17容器/28images/12volumes保留；10:03 TLS healthy与10:06核心新观察已实测。不能拼作同一版本持续采集。Windows28000 API停止，root正在准备新独立运行段供UI真浏览器；管理权已交回root。\n\nroot默认PG认证/空库与旧库升级/0009前向迁移87通过、coverage72.72%；0009第一次引用不存在jobs表导致2失败/12error，已改为实际job_runs。首轮同名log/XML被复跑覆盖，这是证据保留失误；次数/时刻/根因如实记录，wrapper现禁止复用label，不伪称首轮完整原始文件仍在。知识PG维度状态service和MinIO未接通，R03租约/持久游标/真实出口仍未实现。\n\n秘密仍在仓外DPAPI/测试root600，不进消息/源码；生成、供应商凭据用户已经提供，但model/供应商live尚未执行。embedding/reranker能力未验证。FOFA授权资产范围、双人独立人工标注未取得；PPT用户明确后置。CR-R10仍proposed，不能将无回复当major批准。用户UI参考E:/wechatData/.../ui-design.md只参考，不采纳其7工具/9来源/库替换等新合同。\n\n以下内容是历史交接/分工/阻塞记录；当前状态以本节及task_state对应证据范围为准，旧绿灯不为新SHA背书。\n"""
for relative in ("progress/context_handoff.md", "progress/recovery_workstreams.md", "progress/blockers.md"):
    path = ROOT / relative
    old = path.read_text(encoding="utf-8")
    heading, _, body = old.partition("\n")
    path.write_text(heading + "\n" + snapshot + body, encoding="utf-8")

stage_path = ROOT / "reports/stages/recovery/G-A.md"
stage = stage_path.read_text(encoding="utf-8")
stage = stage.replace("本次写作开始时间：2026-10-15T02:38:15+08:00", f"本次写作开始时间：{NOW}")
stage = stage.replace("本次写作结束时间：本轮写作中", f"本次写作结束时间：{NOW}（本次快照修订）")
stage = stage.replace("最后更新时间：2026-10-15T02:38:15+08:00", f"最后更新时间：{NOW}")
stage = stage.replace("本报告证据截止时间：2026-10-15T02:38:15+08:00", f"本报告证据截止时间：{NOW}")
stage += f"\n## {NOW} · 快照修订与问题补充\n\n" + snapshot
stage += "\n上次02:38写作结束时刻未记录，不能把主机中断间隔称为写作时长。本次修订同步独立TLS needs_changes、恢复证据和用户黑客风并行要求。新问题RA-019：TLS失败日志全/片段密码泄漏；RA-020：CI缺专用TLS资源，两项由r01_tls_fix修复、原独立reviewer定向复核。RA-021：0009外键初版错引用jobs，经实际PG失败定位到job_runs并修复，87复跑通过，独立复核待排。RA-022：主控首轮同名复跑覆盖失败log/XML，完整原件无法补回，保留工具可见计数/时刻并新增禁止覆盖保护，后续label唯一。\n"
stage_path.write_text(stage, encoding="utf-8")

task_path = ROOT / "reports/tasks/R02.md"
task = task_path.read_text(encoding="utf-8")
task += f"\n## {NOW} · 当前集成与验证\n\n默认应用PGstate装配及审计SQL失败503待新独立审查。root代码基底{HEAD}，0009维度结果表/映射已实现并真实空schema和0006旧数据迁移通过，PG维度service尚未实现，不声称T19完成。10:17:06–10:17:31共87通过、0failure/error/skip，coverage72.72%，日志r02_default_auth_resume；前次10:15:39–58因错引用jobs的FK，73passed/2failed/12errors。复跑覆盖同名首轮文件，原件缺失事实已登记，新增wrapper拒绝已有label。R01/TLS与资源恢复仍不等于整R02或G-A接受。首次创建时间保持；02:33写作结束历史未记录，本次快照写作开始/结束{NOW}。\n"
task_path.write_text(task, encoding="utf-8")
print(json.dumps({"recorded_at": NOW, "head": HEAD, "updated": 6,
                  "accepted_added": 0}, ensure_ascii=False))
