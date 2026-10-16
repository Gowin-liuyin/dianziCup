"""Append actual integration and review evidence while preserving all task acceptance layers."""

import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent


def clock():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def strict_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8", newline="\n")


started = clock()
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
protected = ROOT / "frontend/tsconfig.tsbuildinfo"
if hashlib.sha256(protected.read_bytes()).hexdigest() != "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d":
    raise RuntimeError("protected user cache changed")
state_path = ROOT / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8-sig"), object_pairs_hook=strict_pairs)
original_tasks = json.dumps(state["tasks"], sort_keys=True, ensure_ascii=False)
original_layers = {key: dict(value["verification"]) for key, value in state["recovery_tasks"].items()}
notes = {
    "R06": "CORE b110 + OPS d1a/d5ded冻结，167/66作者离线；原非作者jointfix2运行中，3原生配额已耗本轮0新native。Product1cdb有已确认preclaim缺陷，不能启动新6h后拿它给修复版本背书；Root待新合格Product/0030兼容合同与资源身份复核，activation七false、OID/marker空、旧ledger42不重置。",
    "R07": "bb04/1cc由原非作者0bbc独立246离线+39真实PG通过，M01 active关联撤回/M02主assertion路径关闭；峰值2、连接0、39测试schema保留。仅内部bridge有限Ship，默认consumer/完整九维未通过，Root尚未源集成此桥。",
    "R11": "48ad/772 standalone HTTP经非作者77bb limitedShip，102离线/19PG最终绿，首次15setup errors保留。Root已精确6文件合入、默认/v1及/api/v1挂载同contentstore，batch8离线126与Ruff/format/mypy4source通过；默认真实API/PG/browser仍待冻结新审查，不算整R11。",
    "R14": "read三工具427有限独审已Root6文件集成，138离线复跑；真实模型trial46c经新review793有限证据Ship：Planner/QA/Critic三调用4141总token/cache512/costunknown，五claims一citation支持，partial/adapter_gaps，完整workflow12.578s不是HTTP P3。QA c6 prompt独审Ship、shared ff7+e56 fix2原非作者70离线68PG/broker绿（材料最后封存）；default九职责及其它工具未完成。",
    "R16": "ca47完整6src+3tests精确Root输入闭包合入，75离线复跑；Root新增可选持久cursorSecretStr，14配置例通过（包含batch8）。仓外CurrentUser DPAPI 20:38:14.5941439实际生成/往返成功，只有配置字段、未装默认worker/API；fan-in/negative/recommendation watches/history/withdrawal仍待实现。",
    "R17": "3076/2f55 Unicode修复经原非作者cc4d有限Ship：64模块/712总回归/17Edge fixture；原101→100红及原probe字节保留。Root已精确11source+原PG DTO样例raw9cc合入（Gitcanonical9d68仅CRLF差异被明确记录，样例精确-text保护），默认#assessments接当前auth代次与事件证据跳转，Root713回归通过；真实默认API/browser待新独审。",
    "R18": "1460/e989安装5文件由新reviewe68有限Ship，363去重、两干净venv实际安装/CLI/type/canary；Root已合5源码，Root本次build未跑。原349完整SDK扩展四工具client/MCP与唯一typedmodels两Agent隔离并行，六工具显式optin兼容旧两工具，默认产品最终主控启六；producer/三插件仍缺。",
    "R19": "新隔离R19 annotation crash recovery作者已真实Windows中断复现直接write_new截断，获准同目录完整fsync+排他hardlink最小修复（不改schema/金标/分母/holdout）。只有合成测试，原96精确入口而非虚凑历史109；≤8自有中断/120s，不证明掉电目录持久性；待独审，人标0保持。",
    "R20": "32新provenance分类已新独审limited批准，Root161注册增量/锁ZIP7精确staged例外尚未实现，ea失败却commit历史保留、未push。loader诊断9c043实际6/6 refs10values20forms仅13历史paths+ZIP15members0exact；首partial5/6保留，fresh reviewer仅读脱敏/合成复验中。Root全仓20:45比较只有7values且3loaders失败不是完整秘密门，CPU近阈误杀/pipe EOF/handle归属仍needs_changes。",
    "R24": "R24早期候选骨架已独立179有限Ship，只prep非正式R24-A；G-F/G-G现创建真实时间材料骨架，正式R22→R24-A→R23→R24-B原顺序与human门不变。",
}
for task_id, note in notes.items():
    item = state["recovery_tasks"][task_id]
    previous = item.get("verification_scope_notes", "")
    if isinstance(previous, str):
        item["verification_scope_notes"] = previous + "\n" + started + " /root: " + note
    elif isinstance(previous, dict):
        previous.setdefault("controller_updates", []).append({"recorded_at": started, "note": note})
    elif isinstance(previous, list):
        previous.append({"recorded_at": started, "note": note})
    else:
        raise TypeError("unexpected verification_scope_notes representation")
state["updated_at"] = started
state["updated_by_task"] = "R00-R24-controller-batch8-integration"
if json.dumps(state["tasks"], sort_keys=True, ensure_ascii=False) != original_tasks:
    raise RuntimeError("original task state changed")
if any(item["verification"] != original_layers[key] for key, item in state["recovery_tasks"].items()):
    raise RuntimeError("acceptance layer changed")
write(state_path, json.dumps(state, ensure_ascii=False, indent=2))
body = f"""## 当前权威续接与文件所有权 · {started}

主控codex/full-delivery-recovery@{head}；origin授权URL最后实际核对19:37，最后已核远端G-B c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7；G-C仍in_progress/partial，无阶段通过或push，后段仅获授权独立准备。原60T/历史/整卡层级不升绿，用户tsbuildinfo SHA3c587e不改不stage。

当前9类工作责任：Root默认App/config/公共合同/schema/迁移/locks/progress/Git/push；R06原reviewer固定b110+d1a jointfix2；R14原reviewerff7+e56修复封包；R07原reviewerbb04两Must已独立39PG关闭；R17原reviewer307 Unicode已独立17Edge关闭；R20新loader reviewer只读脱敏材料/合成；R19新annotation恢复作者独占prepare.py+新tests；R18新四工具作者独占client.py/mcp_adapter.py+新tests；R18唯一typed集成人独占models.py/__init__.py+新tests。全部独立WT，不扩所有权/自push/accepted；每新批新非作者，原非作者只同批定向复核。Root15 read/R16+11 assessment/package+12front含sample已精确合入，尚Root冻结新审查。

实际新Root离线read138/R16 75、默认Assessment126（包括14配置与23旧推荐）和前端713。原shared主仓全量3492红历史未重新跑，局部绿不能whole背书。两Must source桥246/39PG、投递恢复70/68PG、UI712/17fixture各独立scope，计数不简单相加作产品质量。真实模型trial3calls4141tokens/12.578workflow、partial/adapter_gaps、费用unknown；不是fresh-source/default HTTP P3。

PG最多A/B两个heavy，每槽NullPool≤2conn/一个pytest/marked自有测试DB，不改全局PG/kill外人。R07槽B21:02:17.521912释放0conn，39schemas保留；R14槽A21:07:58.532427释放0schema/conn、Redis26493关闭且21:09:49worker0。父PG/Redis/OS deadline2026-10-17T21:49:15+08不扩；旧Neo4j19:35截止已停，新R066h未启动。known-bug旧Product1cdb需先升级与合同审查，不能拼旧版本观察窗。

ea失败却commit秘密边界历史仍未push；registry精确25+ZIP7锁hash例外待Root实现，不扫目录放宽。loader9c043真实6refs仅固定13paths/15members0matches仍不等于ZIP私有资产/holdout上下文安全，freshreview优化assert风险正在复现。CPU硬界原两个Must仍未闭合。独立功能代码尚多，不能称只剩人工或目标blocked/complete。

下一：Root已审模块精确源归档与默认API/工作台冻结→新非作者真实PG/API/Edge；R14完整driver/preclaim/outbox/QA/read工具默认接线，R16持久key默认worker+fan-in/历史/旧新空撤回；R06新Product资源身份门后真实单版本6h；R18六producer/tools/三插件；标注/性能/恢复CI/正式评测/材料/干净复现。人工双核/裁决、FOFA授权资产范围、CNNVD登录下载仍未知；PPT后置不取消。R24-A→R23→R24-B保持。

"""
for relative in ("progress/context_handoff.md", "progress/recovery_workstreams.md"):
    path = ROOT / relative
    write(path, body + path.read_text(encoding="utf-8-sig"))
blockers = ROOT / "progress/blockers.md"
write(blockers, blockers.read_text(encoding="utf-8-sig") + "\n\n" + body)
stage_notes = {
    "G-C": "R07bb04桥两Must独立关闭；R06b110+d1a jointfix2未封，旧Product1cdb有已确认preclaim缺陷，启动最终源窗口必须先冻结合格新Product及0030兼容资源合同。registry/CPU硬界与整集成验收仍阻断，未push。",
    "G-D": "默认资产判断Root126离线/类型绿但真实默认PG/API仍not_run；R14ff7+e56原非作者70+68绿材料封包，3真model4141tokens/partial仅证据包Ship。read3tools/QA/bridge有各自limited结论，整九职责与default消费者尚未闭环。",
    "G-E": "Unicode原probe修复后独立17Edge/712回归，Root影响研判默认导航+authscope接线713绿；真实defaultAPI/PG/browser待新审。R16完整6source合入+cursor配置未factory，安装5package limitedShip，SDK扩四tool与typedmodel并行；完整history/watch/fan-in/三插件待实现。",
}
for stage, note in stage_notes.items():
    path = ROOT / f"reports/stages/recovery/{stage}.md"
    text = path.read_text(encoding="utf-8-sig")
    for label in ("本次写作开始时间", "本次写作结束时间", "最后更新时间", "本报告证据截止时间"):
        text = re.sub(r"(?m)^" + label + r"：.*$", label + "：" + started, text, count=1)
    write(path, text + f"\n\n## 本次集成修订 · {started}\n\n{note}\n\n主控{head}与batch8 raw receipts；代码/文档/pushSHA分别，不把写作时间当持续采集窗。既有首次创建时间保留。\n")
for stage, name, scope in (
    ("G-F", "安全、标注与评测准备", "R19/R20/R21；T46/T45/T47/T48/T49/T50/T51；P1/P2/P3/A1/E1/X1，工具准备不代表正式gold冻结或性能已测。"),
    ("G-G", "正式评测与交付准备", "R22→R24-A→R23→R24-B；T52–T59；13要求/U14。仅候选材料骨架可提前，正式G-G前置未满足。"),
):
    path = ROOT / f"reports/stages/recovery/{stage}.md"
    if path.exists():
        raise RuntimeError("stage first creation already exists")
    write(path, f"""# {stage} · {name}

文档首次创建时间：{started}
本次写作开始时间：{started}
本次写作结束时间：{started}
最后更新时间：{started}
阶段实际开始/结束时间：提前独立准备；正式阶段尚未开始 / 尚未结束
本报告证据截止时间：{started}
主控/实现Agent：/root及本报告第3节指定作者
独立审查Agent与报告：仅组件限定意见；正式阶段新reviewer尚未委派
阶段状态：in_progress
实现状态：partial
各层验证状态：unit/contract/integration/security/frontend/e2e/live/manual整阶段均not_run，组件范围另列
工作分支：codex/full-delivery-recovery
已测代码SHA：组件限定SHA见第5节；阶段候选未冻结
已审代码SHA：组件限定SHA见第3节；整阶段未审
提交/推送结果：尚未发生阶段push；见reports/push/recovery_push_log.jsonl

## 1. 本阶段要解决的用户问题与验收范围

{scope} 原分母、盲测隔离、双人独立标签、完整耗时与未知状态保留。授权允许安全独立准备，不代表阶段门放行。

## 2. 当前真实状态与修改

G-F标注工具已有1个真实dev候选/0人工gold，直接最终路径写入中断截断已作者复现，原子发布修复在隔离WT进行。G-G已有R24候选骨架，正式评测、干净复现、最终Word/PDF/PPT/视频尚未形成可验候选。主控仅此真实时点创建报告，历史首次写作未伪造。

## 3. 并行执行与独立审查

R19作者独占scripts/annotation/prepare.py+新测试；R20新loader reviewer仅读9c043脱敏冻结；R24 preparation独立17988bb1f0eed6eb665ff75b13e15e44507b317d只批准早期骨架。Root公共合同/状态/迁移/锁/集成/Git/push，作者不签accepted。见progress/recovery_workstreams.md。

## 4. 问题台账

- R19-atomic：发现实际时间见作者ownrun（本报告不补造）；强制中断最终写入会留截断JSON，影响annotation导入/导出。Root已批准完整fsync+同目录排他hardlink，作者修复中/待非作者复核；Windows掉电目录持久性不声称保证。
- R20-secret-boundary：Root原ea stage失败却commit，局部ZIP7与13paths25未注册匹配，未push。32分类已有新独审，Root精确追加登记/锁ZIP边界尚未实现；实际秘密6refs窄比较0命中仍不证明全资产上下文，freshreview进行。
- R20-cpu：合法近阈输入误杀及异常child pipe EOF/handle归属未闭合；仍needs_changes，不降低原CPU门。
- Human-gold：双人独立核验与裁决人未提供，正式冻结外部阻塞。只有候选/工具，人标0；PPT模板后置未取消。

## 5. 实际验证

只引用已真实组件记录：R20 provenance新独审32分类/227边界；9c043窄比较6/6refs/10values/20forms/13paths+15members0exact，未作为整secret门；R24 prep独审36static/46paths/287证据/166路径。命令、UTC或+08时间、exit、rawhash见各冻结报告/ownrun；本报告创建不补造重跑命令。整阶段性能/恢复/CI/e2e/live/manual均not_run，fixture不计live；正式指标、分子分母、持续采集窗均未取得。

## 6. 合同与计划差异

无评分/gold/阈值/分母新差异。R19原子文件修复兼容原排他输出，无新公共schema/action；具体源码仍awaiting_review。G-G严格R24-A→R23→R24-B，preparation不算A候选ready。

## 7. 评分和场景证据

当前证据只证明工具/材料准备与局部安全边界；P1/P2/P3/A1/E1/U14完整证据未满足，无优秀/满分自评。逐条T00–T59/R00–R24映射由原manifest维护，未因重排漏项。

## 8. 阶段结论和下一步

允许继续不受阻塞影响的内部准备，不能通过本阶段门。下一：完成R19原子恢复与新独审、精确秘密门/真实恢复CI；六业务/变化前置闭合后同条件基线/消融/完整性能；人工冻结后R22正式运行，再R24-A候选、R23干净复现、R24-B最终冻结。没有暗中后台自动化或公开部署。

## 9. 文档修订记录

{started} /root首次创建：真实准备状态、未满足前置/未运行检查与问题登记。未声称历史已有本阶段报告。
""")
ended = clock()
for relative in [f"reports/stages/recovery/{stage}.md" for stage in ("G-C", "G-D", "G-E", "G-F", "G-G")]:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    for label in ("本次写作结束时间", "最后更新时间"):
        text = re.sub(r"(?m)^" + label + r"：.*$", label + "：" + ended, text, count=1)
    write(path, text)
receipt = {"started_at": started, "ended_at": ended, "baseline_sha": head, "original_60_tasks_preserved": True, "all_recovery_verification_layers_preserved": True, "created_stages": ["G-F", "G-G"], "notes_updated": list(notes), "stage_gate": "not_accepted", "push": "not_run"}
write(RUN / "continuity_batch8_receipt.json", json.dumps(receipt, ensure_ascii=False, indent=2))
print(json.dumps(receipt, ensure_ascii=False))
