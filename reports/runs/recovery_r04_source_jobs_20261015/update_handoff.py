"""真实时钟登记当前实施与限定审查，保留旧记录，不签整卡或阶段。"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
NOW = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
HEAD = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


summary = f"""## 当前权威快照 · {NOW}

分支 codex/full-delivery-recovery，HEAD {HEAD}；G-A/G-B 均 in_progress/partial，无阶段 accepted 或 push。R00 的限定激活不扩为原 T 卡验收。旧快照仅为历史，以下以当前字段和证据为准。

来源修复6c7fd7a的三 Must 已由原非作者定向关闭，报告 reports/reviews/recovery/G-B-R04-sources-review-1-recheck.md：16原探针、131合同、22实际PG、396纯unit（raw62.73471352912855%）及11helper补测通过。root来源writer df214c6刚集成，尚无新独立审查；其作者41项混合命令实际27PG+14纯计算，不能写41PG。API4934de3初审又发现三Must：NUL过滤变503、损坏维度引用变空、stale支持claim仍current；root正在共享read service修复，不能把原24PG通过当API验收。

并行四槽：root拥有 source_jobs.py/source_routes.py、app/runtime接线、公共合同、状态与集成；r04_vendor_source封存sourcewriter证据后释放；r04_api_independent_review只读固定4934de3并封存初审；r04_knowledge_api在独立R05 worktree实施两种wire生成客户端，拥有infrastructure/models与直接测试，不读真实keys、不push。下一个新槽用于新sourcewriter reviewer，初审固定df214c6或新的明确候选；不能自审。

真实服务：旧API0b段已13:01:56停止，当前没有API/worker长期段；MinIO新段13:17:25启动，7200秒上限，截止15:17:25，日志 recovery_r04_minio_20261015；与旧段13:15:28存在间断，不能拼连续运行。Docker/PG/Redis为已隔离资源，不升级旧审查库。root本轮将建单独source_jobs测试库；所有coverage单run仓外隔离。

前端黑客暗色、低亮缓慢拓扑与reduced-motion已实现并有独立交互结果；当前截图明确fixture。真实GET→MinIO/PG→Celery→API→浏览器仍未闭环。产品模型调用0、费用unknown；DeepSeek两wire正在实现，embedding/rerank未选择/探测。双人金标和FOFA授权资产范围仍缺，PPT按用户后置；它们不阻断当前采集和模型接口。秘密保持仓外DPAPI/环境，不进日志、索引、前端或提交。

下一步：修API三Must并冻结供原reviewer定向复验；sourcewriter新初审；root完成分页任务负例/PG原子性与真实队列采集段；R05客户端冻结后新独立审查，再由主控有限live调用。G-A还需综合集成候选与新的阶段reviewer，所有阶段push尚未发生。

"""
for relative in ("progress/context_handoff.md", "progress/blockers.md", "progress/recovery_workstreams.md"):
    path = ROOT / relative
    path.write_text(summary + path.read_text(encoding="utf-8"), encoding="utf-8")
path = ROOT / "progress/task_state.json"
state = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
state.update(updated_at=NOW, updated_by_task="R04 source writer integration; API review defects; R05 client preparation")
for task_id, note in {
    "R03": "cursor08c2ff0/network2522b3a限定Must已关闭，最终独立报告已封存；全阶段未审。",
    "R04": "来源6c7三Must定向关闭，df214writer待新初审；API493初审3Must正在修；source_jobs/app/runtime当前未提交接线不得算通过。",
    "R05": "受控JSON POST162c0b9已自检，生成客户端独立实现中；真实模型/embedding/rerank/live均未运行，调用0。",
}.items():
    item = state["recovery_tasks"][task_id]
    item.setdefault("history", []).append({"recorded_at": NOW, "prior_status": item["status"], "prior_implementation": item["implementation"], "event": "frozen evidence update; whole acceptance unchanged"})
    if task_id != "R03":
        item.update(status="in_progress", implementation="partial")
    item.setdefault("verification_scope_notes", {})["current_snapshot"] = note
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

stage = ROOT / "reports/stages/recovery/G-A.md"
content = stage.read_text(encoding="utf-8")
content = content.replace("## 当前权威快照", summary + "## 历史快照", 1)
content = "\n".join(
    f"{line.split('：')[0]}：{NOW}（当前快照修订）"
    if any(line.startswith(label + "：") for label in ("本次写作开始时间", "本次写作结束时间", "最后更新时间", "本报告证据截止时间")) else line
    for line in content.splitlines()
) + "\n"
stage.write_text(content, encoding="utf-8")

stage_b = ROOT / "reports/stages/recovery/G-B.md"
if stage_b.exists():
    raise FileExistsError("G-B first creation already recorded; update deliberately")
stage_b.write_text(f"""# G-B · 真实来源、证据页面与模型回答

文档首次创建时间：{NOW}
本次写作开始时间：{NOW}
本次写作结束时间：{NOW}（本次脚本生成记录，非代码编写时长）
最后更新时间：{NOW}
阶段实际开始/结束时间：历史未单独记录，首个来源GET观测为2026-10-15T11:53:40+08:00，并非阶段开始时间 / 尚未结束
本报告证据截止时间：{NOW}
主控/实现Agent：/root、r04_vendor_source、r04_knowledge_api、hacker_frontend，精确包与所有权见progress/recovery_workstreams.md
独立审查Agent与报告：parsing/frontend/sources专项报告见下方；r04_api_independent_review初审中；整阶段新review尚未发生
阶段状态：in_progress
实现状态：partial
各层验证状态：unit/contract/integration/security/frontend/e2e/live/manual整阶段均not_run；专项结果不能替代整阶段
工作分支：codex/full-delivery-recovery
已测代码SHA：各专项固定版见报告；当前{HEAD}含新writer，完整集成尚未测
已审代码SHA：解析48ad、UI7f9、来源修复6c7fd7a限定；API4934de3初审needs_changes；整阶段未审
提交/推送结果：仅本地小批提交，阶段push尚未发生

## 1. 本阶段要解决的用户问题与验收范围

R04/R05，原T09/T10/T12/T17/T18/T20/T30/T31/T40/T41/T43的切片；D2/F1/F2/F3/A1/R1。用户登录后能查看真实NVD/厂商公告、历史原文与定位证据，再得到真实模型支持的引用回答。原卡所有映射切片共同完成才能独立验收；本阶段不能替代推荐、正式多跳、完整工作台或持续运行。

## 2. 当前真实状态与修改

已实现真实PDF/严格JSON解析、NVD实际wrapper/CVSS与厂商公告归一化、PG来源元数据与原文引用、两源页面写服务、认证的事件列表/详情/证据读取、黑客风页面与低亮动态背景。复用现有PG仓储/版本/证据和网关，新增代码负责真实API字段、原始成员切片与事务装配，无平行数据库或通用CRUD框架。生成客户端由新并行包复用有界POST；真实回答、向量、rerank仍未证明。

## 3. 并行执行与独立审查

{summary}
## 4. 问题台账

| 问题 | 触发、预期/实际、影响 | 根因、修复、状态与责任 |
|---|---|---|
| RB-001 | 真实NVD字段与旧fixture不一致，实际CVSS丢失；影响R04/R07 | wrapper/cvssData层级；0e622修正，6c7严格时间/UTF8边界；原非作者定向关闭限定问题 |
| RB-002 | 原响应回收COUNT后并发提交FK，可删除已引用原文 | GC先读后删竞态；6c7先PG DELETE/savepoint，真实23503/23514复验通过；完整恢复仍R20 |
| RB-003 | Linux原unit396通过但静态subprocess.CREATE_NO_WINDOW不成立 | 4934使用有官方依据的Windows常量，Linux396/raw62.60494%通过；此改尚需独立覆盖 |
| RB-004 | API q/product/risk_type NUL返回503，损坏维度引用HTTP200空，过期支持claim维度current | 4934初审真实PG复现；root共享过滤/投影修复中，未签通过；精确输入/行号/日志待初审报告封存 |
| RB-005 | 新source POST ISO字符串被strict datetime拒绝，实际422未达认证 | root首次29例27通过/2失败；显式ISO字符串解析正在复跑；另修新测试problem字段错误，不改合同 |

发现/关闭的独立秒级时间以原命令收据为准；历史未记录的不补造。代码修复SHA、复验与关闭在冻结后补齐，未解决项不得当关闭。

## 5. 实际验证

- 来源修复6c7独立16原探针、131合同、22PG、396unit(raw2606/4154)、11helper与静态通过，报告G-B-R04-sources-review-1-recheck.md；测试重复不可累计成独立总数。
- API4934独立原24PG通过，独立8补测3通过/5失败，三Must未关闭；原始证据recovery_r04_api_review_1_20261015，不用作者通过抵消缺陷。
- 来源writer作者最终41混合=27实际PG+14纯计算，446unit raw2810/4479；代码df214，独立新review待派。
- 解析和UI专项见G-B-R04-parsing-review-1.md、G-B-R04-frontend-review-1-recheck.md；截图明确fixture，旧真实auth段对应0b后端。
- 真来源匿名GET：NVD与vLLM实际200留档，仅诊断/原样本；不是worker采集、连续运行、问答live或正式指标。
- 本阶段完整浏览器真实数据、真实模型/embedding/rerank、故障恢复、性能和人工结果not_run。每条真实命令的cwd/起止/退出码/数量/数据版本见runs收据；未运行的不算passed。

## 6. 合同与计划差异

CR-R04-R04_source_persistence.md与CR-R04-R04_source_jobs.md落实已授权事务/来源切片；CR-R04-R05_model_post.md落实真实模型有界请求。无需调整评分/金标/分母。观察轮次不等于上游快照，未知NVD时区原值保留且不造watermark；withdrawal传播留R16，未删验收。

## 7. 评分和场景证据

F1/F2/D2/R1仅当前来源/证据准备切片；U01登录已有专项，真实情报用户闭环尚未证明。F3/A1需真实模型与检索回答，当前未达，不自评满分。U02–U14仍按原映射保留。

## 8. 阶段结论和下一步

部分可继续开发，G-A/G-B均未过门。先修API三Must、新sourcewriter审查并完成真实worker/MinIO/PG/浏览器段；生成客户端冻结→新review→有限live，再接真实embedding/rerank与回答。缺少人工金标/资产授权只传播到相应后段验收，不能据此停止独立实施。

## 9. 文档修订记录

{NOW}：/root首次创建，登记实际组件、失败、未知与并行所有权；阶段未结束，未编造历史写作时间或持续运行时长。
""", encoding="utf-8")
print(json.dumps({"written_at": NOW, "head": HEAD, "stage_accepted": False}))
