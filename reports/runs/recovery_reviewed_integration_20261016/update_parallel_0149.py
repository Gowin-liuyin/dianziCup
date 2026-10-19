"""Record current evidence and exclusive work ownership without signing whole cards."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


root = Path(__file__).resolve().parents[3]
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
state_path = root / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
original_tasks = json.dumps(state["tasks"], sort_keys=True, ensure_ascii=False)
events = {
    "R06": "默认f3独审ac6限定Ship：339offline+7PG，新DoH真实HTTP→broker→普通worker→PG两源30revisions/211evidence/2cursors，26s，仅一页partial不是6h。保留None/fixture真实存储，但旧读取DTO错标live是已证open。激活da221新nonce33guards；独审3生命周期红（stop借用启动时间门、observer早final、重启gate FileExistsError）阻断启动，作者最小fix2。7flags false，42/450 ledger不重置，未启动新采集。",
    "R14": "1daf/43d4由0e835独审348offline+38真实PG=386distinct通过、own进程7/PG152.757s/清理0，限定共享三read与unknown incoming checkpoint恢复Ship，整卡partial。新的唯一集成人从Root972叠入workflow/graph，保留defaultdriver和QA13行；尚未Root组合验收。",
    "R16": "fix1独审0058c377：214offlinepassed；真实PG26=25passed/1failed，原20全绿，新分页fixture只选单asset change未产生next_page。旧retry_wait两红关闭，完整journal/cap已保存，窗口39s/进程5/连接2/清理0。作者新fix2仅修新fixture范围，不改原Oracle/业务；尚未Root集成或Ship。",
    "R18": "99ea/60e322由a2cc独审141offline+41PG=182distinct通过，human/source原origin不变、hypothesis拒绝，限定Ship。新Root整合只完整两producer模块+tests；默认App尚未挂。123bf来源报告分类强图耦合真实10shape probes为新增open，不能被旧Ship关闭。",
    "R20": "972合qualified PG backup及22历史证据输入；Root32offline、2PGcollect、PLAN_OK结构检查通过；Root没有重跑PG。ab048原40验证含2PG仅限定备份切片，索引rebuild_required。新native诊断先区分Root旧50ms路径与未合native0.9/pipe候选，真实全秘密/CPU/CI/恢复门仍open。",
    "R17": "a576正式bundle首屏静态独审b4b1：10真实Edge断言，4.609s/进程13/残留0；普通consumer、登录后调查业务/真实模型仍not_run。原runner入口500/Edge环境与控制错误保留，未以静态证明业务全通。",
    "R07": "新唯一集成人合bb04来源证明桥→91b工厂→c2f有界node到972独立WT；304offline为旧作者/helper层证据，默认SourceEnricher与真实receipt字节门尚未接线。本轮不放宽strongGraph/current_supported/unknown。",
}
for task_id, event in events.items():
    task = state["recovery_tasks"][task_id]
    task.setdefault("history", []).append({"recorded_at": started, "event": event, "root_baseline_sha": head, "whole_task_accepted": False})
    notes = task.setdefault("notes", [])
    if not isinstance(notes, list):
        raise ValueError("preserve unexpected notes shape")
    notes.append(event)
if json.dumps(state["tasks"], sort_keys=True, ensure_ascii=False) != original_tasks:
    raise RuntimeError("original T-card state changed")
state["updated_at"] = started
state["updated_by_task"] = "R00-R24-controller-parallel-qualified-slices"
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
protected = hashlib.sha256((root / "frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest()
if protected != "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d":
    raise RuntimeError("protected user file changed")
section = f"""## 当前权威续接与并行文件所有权 · {started}

Root分支codex/full-delivery-recovery，实际HEAD {head}；origin本轮01:41:14工具读取仍授权URL。G-C仍in_progress/partial，最后核对远端G-B c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7，无新合格阶段push。以下独立Ship只覆盖报告的切片，原T卡状态和整R卡验收不改绿。

Root持有主App/runtime/公共合同/schema/迁移/锁/progress/集成Git。唯一指定集成人：r14_qualified_slice_integration仅workflow_service/graph与直属R14tests；r18_qualified_producer_integration仅NEW public_extension_reads/routes与直属tests；r07_qualified_bridge_integration仅NEW structured_fact_proofs/source_report_reader/source_report_node与直属tests。三者独立WT从972，无共享checkout编辑。r20_native_pipe_cpu_root_cause只process_limits/直属新增tests；r06_revision_mode_read_root_cause仅只读投影模式诊断与自己报告，等Root兼容决策后才实现。R06作者独占候选CORE/OPS/必要新版observer与自己报告；独审r06_activation_first_independent_gate固定版本亲复，子审已结束不再递归。R16作者仅新PG分页fixture fix2，独审0058本轮封存，原Oracle与历史不改。

""" + "\n\n".join(events.values()) + f"""

资源：父PG25432/Redis26379/OpenSearch29200截止2026-10-17T21:49:15+08:00，不延长。A/B当前空闲；R06新激活审查已获一次A≤240s ownDB/preflight（新final冻结后才能开始，须实际报时），CBM轻窗≤60s；尚未provision或启动6h。所有PG连接上限需实采，不将superuser CONNECTION LIMIT2误作硬限制；普通own进程cap10与工具/Edge特殊cap16分开。宿主16 Agent槽，按独立包滚动使用约9，不保证长期后台。Host preflight旧匹配actor/新3监听0、private目录未创建；仅Host健康，不冒充parent服务健康。

当前仍有内部实现：SourceEnricher+真实输出预算、source mode DTO纠偏、R10默认graph消费者协调、完整九职责/模型检索、多跳问答、推荐历史和变化重判、公开tasks/ask/stack、MCP/OAuth/CLI/三插件、R19候选/人工金标、安全/CI/索引恢复/性能与正式评测、R24-A→R23→R24-B。双人核验与裁决、授权资产范围、CNNVD登录XML仍未知；PPT后置。费用unknown，不能声称只剩外部或全部完成。保护用户tsbuildinfo raw SHA {protected}；既有push ledger不顺手stage，明确文件add、secret/holdout门合格后才阶段push。

本次写作结束时间：{started}；此为真实证据索引更新，不是阶段验收或push。

"""
for relative in ("progress/context_handoff.md", "progress/recovery_workstreams.md", "progress/blockers.md"):
    path = root / relative
    path.write_text(section + path.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
ended = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
(Path(__file__).parent / "parallel_0149_receipt.json").write_text(json.dumps({"started_at": started, "ended_at": ended, "head_sha": head, "original_tasks_unchanged": True, "whole_task_accepted": False, "push": "not_run", "user_file_sha256": protected, "events": events}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"started_at": started, "ended_at": ended, "original_tasks_unchanged": True, "events": list(events)}))
