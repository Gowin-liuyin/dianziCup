"""Preserve task history while recording the current bounded parallel integration."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
path = ROOT / "progress/task_state.json"
state = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
original_tasks = json.dumps(state["tasks"], sort_keys=True, ensure_ascii=False)
events = {
    "R17": "Root精确合da43调查UI与固定revision callback，默认导航匿名恢复两新增例；770 frontend unit、TS/lint/Vite构建通过。旧用户tsbuildinfo hash不变。组件独审02c限定Ship；Root默认PG/Edge未审，整R17仍partial。",
    "R18": "Root合40b2六工具SDK与011资格models，保留1460包metadata；474 related offline通过。首SDK全收集15errors是base interpreter未处理pywin32.pth，原exit2保留；包安装/native/stdio未在本批验证。公开producer409经369复核仍1语义Must，原作者新fix2；不能签六默认REST/MCP/插件全通。",
    "R14": "26fa默认集成165离线通过，真PG/HTTP部分通过但broker旧26503超时，d536结论needs_changes。新diagnostic已证daemon bridge none与host unique Redis连通，尚未broker重验。5883三个真实read消费者新独审268pass/7fail/25setup errors且2个unknown后继续工具实证红，未合Main；材料18处CRLF错配待修。",
    "R06": "a3来源模式候选经新独审386离线/12真实PG通过，source无新Must，CBM仪器两次失败保留；CR b578冻结。默认worker模式注入未完成，未启动新6h。新activation preparation复用CORE/OPS，旧Product1cdb禁止启动；父PGdeadline不延长。",
    "R16": "新fanin作者仅owned revalidation实施：父partial/history不改，新的completion按原job重试有界汇总；requested/effective epoch分开不改cursor。新的唯一executor作者补可选final事务guard，Root正式CR记录后分开独审。36新作者unit/contract只是自检，PG/默认接线未验证。",
    "R20": "ContentStore fix3 e2f经cdfe独审229+4通过，本机NTFS限定Ship；Backup12f经ab048独审40distinct含2真实PG/freshchild，完整Win6+Linux4峰10/自有资源0，indexes仍rebuild_required。旧CPU/pipe安全与秘密provenance门尚未闭合，整R20不验收。",
}
for task_id, event in events.items():
    task = state["recovery_tasks"][task_id]
    task.setdefault("history", []).append({"recorded_at": started, "event": event, "root_baseline_sha": head, "whole_task_accepted": False})
    notes = task.setdefault("notes", [])
    if not isinstance(notes, list):
        raise ValueError("unexpected notes shape; preserve original instead of replacing")
    notes.append(event)
if json.dumps(state["tasks"], sort_keys=True, ensure_ascii=False) != original_tasks:
    raise RuntimeError("original T-card state must remain unchanged")
state["updated_at"] = started
state["updated_by_task"] = "R00-R24-controller-parallel-batch10"
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
section = f"""## 当前权威续接与文件所有权 · {started}

Root codex/full-delivery-recovery@{head}，产品基线26fa；b578只两份内部CR checkpoint，不是阶段通过。origin本轮23:26:52工具读取仍授权URL，最后已核远端G-B c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7。G-C仍in_progress/partial，无新push；所有后段独立准备不跨live验收门。

Root独占主App/nav/公共合同/配置/schema/迁移/locks/progress/集成push；Root UI/SDK batch10 WIP已770前端+474SDK related通过、原收集15errors保留，用户tsbuildinfo完整hash 3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d不stage。Frontend XML一处credential形状暂withheld，仅原字节hash/偏移与数量入checkpoint，原件保留工作目录供独立分类。R17默认Root产品入口仍需新非作者真PG+Edge审查，不以组件Ship代签。

滚动分工：R14 read新非作者审5883，已2unknown-stop实证红/三新PGfixture权限错误与原read-adapter25错名guard拒绝/两restart子进程依赖丢失，全部保留，无再重跑大批；旧read作者待冻结2probe定向修。R18原作者fix2只public_extension_reads与直属tests，原nonauthor369认为1版本声明引文不足Must未闭，健康与bytes2Must已闭；R06新非作者只a3模式与PG12/原证据，作者另WT只新activation builder/报告，不启动旧1cdb；R16作者只revalidation/newtests，R03唯一指定作者只executor optional completion guard/newtests，Root冻结四参数和兼容CR；旧Rootdefaultreview等待新host Redis诊断冻结后针对broker复验。所有独立WT，不自push/accepted；并行数量动态，不虚构恒定后台。

已限定Ship待集成：ContentStore e2f/cdfe，233不同独立验证仅NTFS；Backup12f/ab048，40different含两真实PG+fresh child，最后完整outer Win6/Linux4=10。R20 indexes仍需真实重建，MinIO/native/full研判/UI/live未验。原secret loader两个guard限定Ship但完整仪器包失败；CPU1s/pipe旧两个Must、registry25/ZIP7/holdout与资产秘密门未闭。不能称只剩外部。

父PG25432/Redis26379/OS29200截止2026-10-17T21:49:15+08:00不延长。A/B各单重型pytest/NullPool2；近期R14read/R06mode/R18复核/Backup都记录自有DB/schema/conn/PID/listener0并交回。新Redis诊断host26513仅setup2TCP/1PING成功，原bridge网络不存在与全局计数混入其他Agent的旧失败保留；broker/worker尚未验证。工具窗口16与业务10分别记录，不把普通CLI/default输出混成完整安全通过。

下一关键动作：冻结Root默认调查UI/SDK给新非作者；合限定通过FD/Mode并Root唯一注入trusted mode后真PG/新来源与新版本activation审查，实际启动受控6h；修R14unknown/R18声明支持，接read3/R07桥与完整九职责；fanin/history/retraction/negative watch、公共tasks/ask/stack/HTTP-MCP/OAuth/CLI三插件、R19双人候选、R20indexes/CI/security、R21同条件性能、R22→R24-A→R23→R24-B。双人核验/裁决、FOFA授权资产scope、CNNVD登录XML仍未知，PPT后置，费unknown；不新增购买/用户侧chat/自动提醒。

"""
for relative in ("progress/context_handoff.md", "progress/recovery_workstreams.md", "progress/blockers.md"):
    document = ROOT / relative
    document.write_text(section + document.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
xml = RUN / "frontend_batch10_unit.xml"
import re
pattern = re.compile(rb"(?i)\bsk-[a-z0-9]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|postgres(?:ql)?(?:\+psycopg)?://[^\s:]+:[^\s@]+@")
raw = xml.read_bytes()
matches = [{"byte_start": match.start(), "byte_end": match.end(), "sha256": hashlib.sha256(match.group()).hexdigest()} for match in pattern.finditer(raw)]
(RUN / "frontend_batch10_xml_withheld.json").write_text(json.dumps({"path": xml.relative_to(ROOT).as_posix(), "raw_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "matches": matches, "decision": "raw remains untracked pending independent synthetic fixture provenance classification; no matched content printed or exemption"}, indent=2) + "\n", encoding="utf-8", newline="\n")
(RUN / "continuity_batch10_receipt.json").write_text(json.dumps({"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "baseline_sha": head, "original_T_cards_unchanged": True, "whole_tasks_accepted": False}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"baseline_sha": head, "whole_tasks_accepted": False}))
