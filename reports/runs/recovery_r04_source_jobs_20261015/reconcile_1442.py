"""以实际已取得证据更新进度；完整保留旧状态与历史快照。"""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
CLOCK = ZoneInfo("Asia/Shanghai")
started = datetime.now(CLOCK).isoformat(timespec="seconds")
receipt_path = RUN / "reconciliation_1442.json"
if receipt_path.exists():
    raise FileExistsError(receipt_path)
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
snapshot = f"""## 当前权威快照 · {started}

集成分支codex/full-delivery-recovery，HEAD {head}；2026-10-15T14:38:43+08:00重新核对origin为授权地址。G-A/G-B仍in_progress/partial，无阶段accepted或阶段push。旧段落均为历史，不覆盖本快照；原T卡完整切片与验收条件不变。

真实来源链已在Windows受控运行段证明：7184后端于14:18:16启动，NVD实际45事件/3页完成；厂商10条已入库，来源合计55事件，证据334条为14:22附近观测。GitHub数字page实际重复同10条，达到页上限的partial不算全采完。14:24:49–52两页原始响应哈希一致，Link明确after游标；厂商分页Must未关闭，作者在独立WT修复，旧backfill游标/原始响应不删除，下一轮从未用live流验收。NVD源时间无时区保持未知，不能拿观察时间补源发布时间。

API三Must已由独立reviewer固定7af91b3定向关闭：43真实PG/探针、505纯unit(raw3075/5026)；来源空package两负例固定7184也已独立关闭。pipeline新发现翻页Must，整体仍needs_changes。真实浏览器7184链41项交互通过，含实际PG列表/详情/固定修订证据、刷新、移动端、分页和错误恢复；NVD外网页内容仍blocked_external_content，GitHub外网页200/内容可核验。来源监控页仍待接线，完整R17未完成。

UI已实现暗色青绿黑客工作台与低亮动态拓扑。真实浏览器验证transform变化、减少动画后停止、pointer-events:none及焦点可用。新Must为SavedTime直接显示UTC/微秒；root d391f89统一北京时间秒级+08:00且保留原datetime，120前端unit/类型/lint通过，独立定向复验待槽位。首次root测试子命令exit0，打印输出GBK异常使外层exit1，原始日志保留并修报告脚本；不能算业务测试失败或抹去外层失败。

生成接口436455d已接两种DeepSeek wire及原生OpenAI/Anthropic接口，尚未产品接线。新独立review固定该SHA：574unit(raw3442/5356=64.26437640029873%)、共享HTTP/安全112、真实本机socket3通过，但新增probe确证两Must：prompt/schema版本可将synthetic credential写metadata；TypedDict/dataclass显式extra=ignore可吞字段。作者只修generation和直接测试，初审报告G-B-R05-generation-review-1.md保留失败，产品模型调用仍0、费用unknown，embedding/rerank未选/未探测。

当前四槽滚动：root统一合同/状态/集成及UI时间；r04_vendor_source独立source_jobs/source_documents及直接测试；r04_knowledge_api独立generation及直接测试；新独立r05 reviewer初审完成后释放，下一槽短时给原liveUI reviewer定向复验，再给pipeline reviewer复验。各自不得扩文件权属、不push、不accepted。公共schema/锁无本轮变更。

真实运行分段：Linux95段13:59:50–14:04:54因WSL出网失败两源0事实/0游标；Windows95段14:08:14–14:17:26证明NVD45，厂商空package失败；Windows7184段14:18:16开始、14:48:16硬截止，API28000/worker/beat，RedisDB14、独立PG0013。WindowsSolo由独立PG期限看守及JobObject内存限制，不能冒称Linux生产hard-limit验证。前端7184服务25300自14:19:19开始、14:49:19截止。MinIO新段13:17:25至15:17:25截止，中断与版本不得拼连续运行；Docker总资源17日21:49:15截止。所有启动/停止以raw收据为准，快照不是新的运行时长证据。

双人独立标注/裁决与FOFA授权资产范围仍缺；PPT按用户后置。不阻断当前接口/来源/工作台实施。凭据只在仓外DPAPI与子进程环境；不进入前端/索引/报告。下一步：翻页与生成Must修复→原独立reviewer复验；UI时间真实浏览器复验；新版本真实来源流；生成限定通过后有限模型live，再接embedding/rerank与引用回答。G-A仍需新的整阶段审查，未具备阶段push条件。
"""

state_path = ROOT / "progress/task_state.json"
def unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key: " + key)
        value[key] = item
    return value
state = json.loads(state_path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs)
notes = {
    "R03": "cursor08c2ff0/network2522b3a限定Must独立关闭；共享HTTP TimeoutError07新增回归独立112/本机socket3通过；真实Windows任务链受控分段已运行，Linux出网仍阻塞；整阶段待新review。",
    "R04": "来源55事件有限实链及41浏览器交互通过；API7af三Must/空package7184两负例独立关闭；GitHub数字page重复必须改Link.after。root d391时间显示修复120前端检查通过但独立待复验；整卡needs_changes。",
    "R05": "436两wire生成已集成，独立574unit/112HTTP/3本机socket通过但4新probe失败确证metadata secret与nested extra两Must；作者修复中，产品调用0/费用unknown，embedding/rerank/回答未接线。",
    "R17": "7184真实事件链41交互及动态背景/减少动画已实测；时间UTC显示Must root d391修复等待独立复验。来源监控与后续业务页面仍待接线，非完整工作台。",
}
for task_id, note in notes.items():
    task = state["recovery_tasks"][task_id]
    task.setdefault("history", []).append({"recorded_at": started,
        "prior_status": task["status"], "prior_implementation": task["implementation"],
        "prior_verification": task["verification"],
        "prior_verification_scope_notes": task.get("verification_scope_notes"),
        "event": "Evidence reconciliation; independent defects retained; no whole-card acceptance"})
    task["verification_scope_notes"] = {"current": note, "current_snapshot": note, "recorded_at": started}
    if task_id in {"R04", "R05"}:
        task["status"] = "needs_changes"
    if task_id == "R04":
        task["verification"].update(integration="failed", frontend="failed", live="failed")
        task["review_ref"] = "reports/reviews/recovery/G-B-R04-pipeline-review-1.md"
    elif task_id == "R05":
        task["verification"].update(unit="failed", contract="failed", security="failed")
        task["review_ref"] = "reports/reviews/recovery/G-B-R05-generation-review-1.md"
    task["implementation"] = "partial"
state["updated_at"] = started
state["updated_by_task"] = "R04 live pipeline and browser evidence; independent Must reconciliation; R05 generation review"
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

for relative in ["progress/context_handoff.md", "progress/blockers.md", "progress/recovery_workstreams.md"]:
    path = ROOT / relative
    history = path.read_text(encoding="utf-8").replace("## 当前权威快照 ·", "## 历史快照 ·")
    path.write_text(snapshot + "\n" + history, encoding="utf-8")

for name in ["G-A", "G-B"]:
    path = ROOT / f"reports/stages/recovery/{name}.md"
    document = path.read_text(encoding="utf-8").replace("## 当前权威快照 ·", "## 历史快照 ·")
    replacements = {
        "本次写作开始时间": started,
        "本次写作结束时间": started + "（脚本整理时点，非代码/测试/持续采集时长）",
        "最后更新时间": started,
        "本报告证据截止时间": started,
        "独立审查Agent与报告": "专项报告及固定版本见当前快照；整阶段新审查尚未发生",
        "已测代码SHA": "后端436455d含574纯unit；真实来源/浏览器7184；UI时间d391f89自检120通过，均限定范围，整阶段未测",
        "已审代码SHA": "API7af限定Must关闭；来源pipeline7184仍翻页Must；生成436仍两Must；UI7184仍时间Must，d391待复验；整阶段未审",
        "提交/推送结果": "小批本地提交；无阶段push，暂无远端验收SHA",
    }
    for key, value in replacements.items():
        document = re.sub(r"^" + re.escape(key) + r"：.*$", key + "：" + value, document, count=1, flags=re.M)
    position = document.find("\n## ")
    document = document[:position] + "\n\n" + snapshot + "\n" + document[position:]
    document += f"\n{started}：/root修订当前权威字段，保留历史；补真实链路、重复分页、生成两Must、UI时间修复及受控服务边界，阶段仍未过门。\n"
    path.write_text(document, encoding="utf-8")

task_report = ROOT / "reports/tasks/R04.md"
if not task_report.exists():
    task_report.write_text(f"""# R04 · 第一条真实情报链路

文档首次创建/本次写作开始/结束/证据截止：{started}（本次脚本整理时点）
状态：needs_changes；实现partial；独立结论见G-B-R04-pipeline-review-1.md及G-B-R04-live-ui-review-1.md。

## 范围与实际行为

R04映射T09/T10/T12/T17/T40/T41切片，F1/F2/D2/R1；不代表整T卡完成。真实NVD/厂商→共享网关→MinIO原始响应及成员→PG原文/证据/事件→Celery任务状态→认证API→浏览器链路已有限证明。复用PG仓储、共享HTTP/解析/认证与既有前端；必要新增是source writer/page job/只读投影及实际接口兼容，无新通用CRUD或内存真相。

## 版本、文件与独立审查

writer df214；装配95ba；API纠正7af；空package7184；UI北京时间d391。主要文件ingestion/source_documents.py、source_jobs.py、api/source_routes.py、knowledge查询/投影路由、workers/runtime.py、frontend事件工作区。独立sources6c7三Must、API7af三Must已限定关闭；pipeline7184翻页Must与liveUI7184时间Must未关闭。root修UI必须交非作者复验。

## 实际测试与日志

工作目录D:/dianzi/backend，root run_checks.py receipts逐条记录起止/命令/退出/测试量：jobs_fixed_2=514通过，api_related_fixed=41实际PG通过，model_integrated_unit=574纯unit通过/raw3442/5356。这些是不同范围重复检查，不相加成不重复总量。独立API43PG/探针及pipeline own PG/MinIO复现见各review原始run。前端d391自检120通过/type/lint通过；外层打印GBK异常exit1保留，子测试exit0证据完整。root新draft真实e2e spec尚未运行，不把它计通过。

真实Windows7184源段14:18:16开始，截至14:22:20观测NVD45完成3页，vendor10条但重复数字分页；55事件/334证据是该时点值。独立真实浏览器41检查通过，具体分辨率/输入/API状态见recovery_r04_live_ui_review_1_20261015。源页面NVD内容blocked_external_content；GitHub网页实200/内容核验，fixture中的stale/failed不能冒充真实来源stale/failed。

## 问题与边界

空package使整页失败：7184可存原样未知package，PG两负例独立关闭。数字page参数被上游忽略导致同10条重复：两页哈希相同、Link为after，pipeline Must未关闭；下一版本用固定域路径重构after，不跟任意Link URL，不重置旧历史。UTC微秒显示：d391统一+08秒及null未知，120自检通过但独立待复验。Linux公共DNS/出网失败，0事实/游标，转已授权Windows受控段；Linux生产worker live仍未证明。原始错误与修复日志完整保留。

## 结论与下一步

六类卡验收未全部闭合；unit/contract/integration/security/frontend/e2e/live/manual分层状态与范围见progress唯一状态、G-B与原始收据。当前不能整卡accepted。继续翻页与UI独立复验、固定新版本实际来源流、补回放/修订链证据；NVD真实源时间未知不得猜。正式持续监测/时效、九维富化、撤回重判、完整恢复留原后段验收，不删减。
""", encoding="utf-8")

receipt_path.write_text(json.dumps({"started_at": started,
    "ended_at": datetime.now(CLOCK).isoformat(timespec="seconds"), "head": head,
    "files": ["progress/task_state.json", "progress/context_handoff.md", "progress/blockers.md",
              "progress/recovery_workstreams.md", "reports/stages/recovery/G-A.md",
              "reports/stages/recovery/G-B.md", "reports/tasks/R04.md"],
    "stage_accepted": False, "push_performed": False}, indent=2), encoding="utf-8")
print(receipt_path)
