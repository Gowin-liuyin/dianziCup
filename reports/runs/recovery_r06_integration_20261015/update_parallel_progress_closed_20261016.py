"""Preserve prior records while correcting the closed source run and current ownership."""

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
assert head == "3baeb8809d3950a091e8db114be7a28049b74b36"
assert subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=ROOT, text=True).strip() == "https://github.com/Gowin-liuyin/dianziCup.git"
state_path = ROOT / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_fields)
original = json.dumps(state["tasks"], ensure_ascii=False, sort_keys=True)
notes = {
    "R06": "更正此前running记录：e310/tool44段实际06:19:43.758521–06:47:34.216338+08，1670.457817秒，guard_snapshot_stale停止。失败signed age/profile未记录，历史根因未知，新的独立诊断中。MinIO遗留子进程07:17:33内核确认清理。未重启，不拼接旧段，六小时/P1仍未通过。",
    "R07": "默认富化scope-v2 sourceba69/material998原独立复核baa280限定Ship；taxonomy source5b/material670独立reviewcommit6d640限定Ship、394fresh+146字节未变共享回归，完整官方schema126红保留。归档后主合；prompt/selection持久指纹、默认知识分类与九维live仍待接线，不签整卡。",
    "R10": "PG六关系/默认图App已合；新Neo4j派生切片与自有runtime并行，真实PG/Neo4j7项作者初跑通过。Community5.26.32/driver6.4.0/Bolt5.8实际连接，当前同CID关闭usage report后复验；缺KILL导致tini TERM转发失败，虽exact stop已证，graceful shutdown未通过，必须保留局限。生产0025/default job注册/ACL返回与独审仍缺。",
    "R11": "规则评估source2dd/material6b已reviewed合main3ba；SBOM隐私source694/material5be独立00451限定Ship，547唯一功能末态通过，待归档主合。0021/0022 source2fe/material569作者119PG/371pure，新的独立初审已启动。正式default评估/SBOM browser/live/manual未通过。",
    "R12": "hybrid ba/d3已reviewed合mainb502；root0020 sourceed0/material8c经新89579限定Ship，独立30生产+28负例+143相关回归通过，待归档合入。四模块PG多轮context/bundle切片正在独立WT实现，0024/默认API-worker-query-grounding接线与真实多跳SLA未通过。",
    "R17": "资产工作台a25/f9经独立b82c限定Ship并合main99c，455前端/原12Edge/迟到与权限反例已审。新SBOM前端从3ba独立设计实现，现有真实后端浏览器全链not_run，不签完整工作台。",
    "R18": "独立协议/SDK提案核对从3ba启动，先冻结真实服务/八schema/两MCP transport与CLI退出语义、文件所有权；没有声称SDK/MCP已接通。root确认后转实现，R14/R15依赖缺口保留。",
}
for task_id, note in notes.items():
    item = state["recovery_tasks"][task_id]
    item.setdefault("history", []).append({"recorded_at": started, "prior_status": item["status"], "prior_implementation": item["implementation"], "event": note})
    item["status"], item["implementation"] = "in_progress", "partial"
    item["verification_scope_notes"] = {"recorded_at": started, "current": note + " 整卡验证层不提升。"}
state["updated_at"], state["updated_by_task"] = started, "root source closure correction and reviewed slice integration"
assert original == json.dumps(state["tasks"], ensure_ascii=False, sort_keys=True)
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
snapshot = f"""## 当前权威续接 · {started}

主控 codex/full-delivery-recovery@{head}，origin已重核为授权URL；最后已核远端G-B c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7。G-C仍in_progress/partial，无阶段放行/push。G-D/G-E独立准备非跨门。原60T/history/分母/金标不改，用户frontend/tsconfig.tsbuildinfo不stage。root当前仅pyproject/uv.lock有neo4j6.4.0新增待checkpoint，不是用户改动。

来源段已停止：06:19:43.758521→06:47:34.216338+08，1670.457817秒，guard_snapshot_stale，失败signed age/profile未知。现新r06_guard_snapshot_stop_root_cause_diagnosis@D:/wt/r06-guard-diag从tool44仅读、独立最小复现；固定源码用PG transaction_timestamp与host UTC差值，不是后台monotonic发布机制。禁止重启、扩大阈值或拼六小时。42 sourcejobs/34成功4blocked4partial，343 knowledge_change blocked缺handler，331doc/346revision/96459evidence是这段delta，不算时效达标。MinIO遗留子07:17:33已内核确认关闭；旧段日志/红保留。

当前9路职责（本次实际spawn后快照计数，完成后滚动调整）：root合同/生产0020–25/锁/默认接线/Git/状态；r06独立guard诊断；r11_forward_migrations_first_independent_review新冻569仅读与fresh PG负例；r12_hybrid_corpus_retrieval_implementation@D:/wt/r12-conversation-context独占4新会话/bundle文件；r10_neo4j_projection_design@D:/wt/r10-neo4j-projection独占3新投影/driver协议文件；r10_owned_neo4j_runtime_integration仅自有ops/报告；r17_sbom_workbench_frontend_integration从3ba独占资产前端指定文件，不改App/全局CSS；r18_protocol_sdk_contract_preparation只提案/索引/合同核对；recovery_frozen_evidence_archive第12批canonical复制，不改业务/Git/progress，根attrs eda4733a只读锁持有直到总收据done。禁止其他writer扩范围/递归spawn/push/accepted。

已主合：R17资产UI99c与R11规则评估3ba，均有独立限定Ship。待主合reviewed候选：R07default998(baa280)、taxonomy670(review6d640，fresh394+146复用)、R12生产8c(89579)、SBOM隐私5be(00451)。0021/22 source2fe/material569已作者冻，独立review新启动。Neo4j官方固定manifest57ec.../同CIDc0d49.../volume/data namespace自有，127.0.0.1:27687/27474，内存1536MiB/CPU1/pids128/heap512/cache512、deadline19:35:43.312788+08不延长；driver与server telemetry关闭。缺KILL令tini TERM转发失败，不把Docker停止当graceful通过，生产0025与默认注册仍未实施。WSL资源最晚2026-10-17T21:49:15+08，凭据DPAPI只内存，无日志/argv。

R07官方taxonomy完整schema126红、R20严格CPU红与历史环境失败保留；默认九维/来源6h/正式模型多跳/完整Agent/推荐重判/MCP插件/性能评测仍不冒称通过。人工双人label/裁决、FOFA授权资产scope缺失，CNNVD IAB登录未确认不读cookie，ZoomEye401。真实模型凭据已有授权；PPT后置非删除；holdout不入索引/产品/一般Agent上下文。

下一步：归档12释放attrs→root显式主合reviewed998/670/8c/5be并新索引集成回归；0021/22新审通过后再合；root完成0023富化审计指纹/知识分类与默认hybrid/graph handler，0024会话及0025派生投影；R17 SBOM和R18协议设计实现并行。新切片初审必须新非作者，整阶段另新reviewer；没有G-C通过或push。R14–24持续推进，R24-A→R23→R24-B保持。

"""
for name in ("context_handoff.md", "recovery_workstreams.md", "blockers.md"):
    path = ROOT / "progress" / name
    path.write_text(snapshot + path.read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")
ended = now()
stage_path = ROOT / "reports/stages/recovery/G-C.md"
stage = stage_path.read_text(encoding="utf-8-sig")
for prefix, value in (("本次写作开始时间：", started), ("本次写作结束时间：", ended), ("最后更新时间：", ended), ("本报告证据截止时间：", started)):
    stage = "\n".join(prefix + value if line.startswith(prefix) else line for line in stage.splitlines()) + "\n"
stage = stage.replace("## 2. 当前真实状态与修改\n", "## 2. 当前真实状态与修改\n\n" + snapshot, 1)
stage += f"\n{ended} /root修订：明确更正来源段stopped及真实窗口，保留旧历史；补主合与限定独审、新九路所有权；整阶段/原T验证与远端不提升。\n"
stage_path.write_text(stage, encoding="utf-8", newline="\n")
receipt = {"started_at": started, "ended_at": ended, "head": head, "original_T_tasks_unchanged": True, "original_T_tasks_sha256": hashlib.sha256(original.encode()).hexdigest(), "stage": "G-C in_progress/partial", "whole_cards_accepted": [], "push": "not_run", "source_run_status": "stopped/needs_changes", "source_duration_seconds": 1670.457817, "assigned_workstreams_at_dispatch": 9}
(RUN / "parallel_progress_closed_20261016_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
