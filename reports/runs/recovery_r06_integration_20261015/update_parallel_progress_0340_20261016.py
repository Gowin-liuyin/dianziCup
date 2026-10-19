"""Preserve prior evidence while recording the current parallel recovery snapshot."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert head == "8a1b04d48346d8550f0326a77f003246a0ebbab5"
remote = subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=ROOT, text=True).strip()
assert remote == "https://github.com/Gowin-liuyin/dianziCup.git"
state_path = ROOT / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_fields)
original = json.dumps(state["tasks"], sort_keys=True, ensure_ascii=False)
notes = {
    "R06": "离线观察器b088及新review da7d限定Ship。8a产品新真实段03:47:57至03:50:08实际131秒，被35秒running watchdog停止；九beat roots/8响应收据，首轮仍失败，不能称六小时。新诊断与有限第二段准备中。",
    "R07": "单维模型b05/新独立review28da限定Ship待主控合入。发布初审3 Must真实成立，ACL锁a804与CVSS2ba组合20fb，root新schema2可读rule/context provenance已红绿PG验证但尚未冻审。异步job WT b3cc已有request合同27绿，迁移/worker/API尚未实现。",
    "R08": "四次真实Hunter/Quake聚合成功仅总量；新的PG/cache/service作者已派，资产扫描0。未真实发布到产品暴露维度，不等于受影响资产统计。",
    "R09": "知识卡组合b5ca和原reviewer4501限定Ship待合入；公开资料真实模型与知识卡PG/API/检索尚未接。",
    "R10": "PG只读初审三P1一P2成立；作者正在语义支持校验、新提交围栏和目标ACL去重修复，1.1规则，无新独立结论。Neo4j与默认API接线未完成。",
    "R11": "版本范围8f5已集成8a；清单parser37e/原reviewerbfed限定Ship待合入。新资产inventory PG/router独立作者已派，root统一0018迁移，条件/四态自查整链未完成。",
    "R17": "证据图前端已封存370f、源码b58，作者394unit/10Edge fixture绿；新reviewer独立审查中，App未注册且真实graph后端浏览器not_run。旧详情UI已集成。",
    "R20": "8a完整pure2489通过/11失败，七环境项定向复核绿但原四CPU产品失败未关闭。新根因诊断d56120样本支持早期bootstrap/父监督，已派新作者，不把旧startup限定Ship当整限额安全通过。",
}
for task, note in notes.items():
    item = state["recovery_tasks"][task]
    item.setdefault("history", []).append({"recorded_at": started, "prior_status": item["status"], "prior_implementation": item["implementation"], "event": note})
    item["status"], item["implementation"] = "in_progress", "partial"
    item["verification_scope_notes"] = {"recorded_at": started, "current": note + " 切片限定通过不提升整卡八层验收。"}
state["updated_at"], state["updated_by_task"] = started, "parallel recovery integration and frozen reviews"
assert json.dumps(state["tasks"], sort_keys=True, ensure_ascii=False) == original
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
snapshot = f"""## 当前权威续接与并行文件所有权 · {started}

主控 codex/full-delivery-recovery@{head}；origin核实仍为授权URL；最后已核远端G-B/c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7。8a已新合共享Generation预派发typed超时df0及成熟版本范围8f5/f624。G-C in_progress/partial，没有阶段放行或本阶段push。原T60及分母/金标未改，用户tsconfig.tsbuildinfo修改保护。

当前调度8路含root，宿主16硬上限/目标6–10：root（公共schema/0017–0019迁移/接口/锁/集成Git/progress）；R06自有runtime WT D:/wt/r06-live-8a-20261016及固定observer WT D:/wt/r06-live-observer-20261016（只自有进程/报告，产品8a不改）；R10作者D:/wt/r10-pg-graph（graph读服务/独立router）；R17新reviewerD:/wt/r17-graph-review1@370f（只review证据）；R20新作者D:/wt/r20-early-bootstrap（固定worker启动/限额模块与直属tests）；R11新作者D:/wt/r11-asset-inventory（assets inventory内部/router）；R08新作者D:/wt/r08-aggregate-persistence（assets aggregate内部）；第五批归档Agent（只canonical reports原bytes）。禁止一级Agent自行spawn、改状态、push或签accepted；非作者新初审冻结版本，作者继续独立下一切片。

root发布组合D:/wt/r07-pub-combined@20fb98541f9cc9035a2a2dad31e676b2a122e161，加未提交schema2 readable context/rule provenance/1PG测试及CR；provenance红exit1、绿exit0原bytes均保留，尚未冻审。ACL/锁a804与CVSS2ba来自两限定修复作者，原独立review三Must仍需组合复核。job WT D:/wt/r07-enrichment-jobs@b3cc1a2ae231a4d1872f14d8a911d221c5272302（旧发布71+单维d8），仅request27绿；尚无新DDL/handler/worker/API，不可live。R09b5ca、R11parser37e、singleb05已独立限定Ship待root合入，完整R卡不accepted。

真实采集新8a段03:47:57–03:50:08共131秒被35秒running watchdog停止，九beat根任务/8来源响应收据，第一启动验收失败。MinIO 03:46:10起最迟11:46:10，WSL runtime deadline2026-10-17T21:49:15+08。重启另run/固定版本/实际起止，不能拼成连续六小时；HTTP wire预算不能用fetch_attempts或receipts代替。旧1927段11067秒与1156段1187秒原日志不变。

8a独立完整pure2489通过/11失败；七环境项定向复核通过并保留原red，四R20 CPU产品red未闭；真实PG136、前端352、fixtureEdge3通过，后两不是新graph已接或live。R20诊断20/20primary后停，已有四页PDF真实成功，真实semantic重库未跑。R17新graph作者394+10fixture过但App原53modules未注册，新review进行中。

资源缺口：双人标注/裁决仍awaiting_human_label，FOFA授权资产范围缺失，ZoomEye401，CNNVD用户IAB登录未确认；不读holdout/秘密到索引。Hunter/Quake四实际聚合记录retrieval时间/observed unknown/fee unknown，没有owned资产查询。PPT按用户后置，独立可行开发持续，不越G-C live门。

下一步：root发布组合冻结→原reviewer复核，同步九维PG child任务接线；R06新段根因修复及同版本重新受控采集；R10修复冻批→原reviewer，R17新审→root默认App/router真接；R08/R11自有表协议先冻结由root生产迁移；R20新安全实现→新审；R09/parser/single已审材料合入及适用回归，之后剩余R12–R24继续。第五批归档只按manifest原bytes，R10源WT不存在review文件仅canonical自身核验，限制明确。

"""
for name in ("context_handoff.md", "recovery_workstreams.md", "blockers.md"):
    path = ROOT / "progress" / name
    path.write_text(snapshot + path.read_text(encoding="utf-8-sig"), encoding="utf-8")
ended = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
stage_path = ROOT / "reports/stages/recovery/G-C.md"
stage = stage_path.read_text(encoding="utf-8-sig")
for prefix, value in (("本次写作开始时间：", started), ("本次写作结束时间：", ended), ("最后更新时间：", ended), ("本报告证据截止时间：", started)):
    stage = "\n".join(prefix + value if line.startswith(prefix) else line for line in stage.splitlines()) + "\n"
stage = stage.replace("## 2. 当前真实状态与修改\n", "## 2. 当前真实状态与修改\n\n" + snapshot, 1)
stage += f"\n{ended} /root修订：更新8a组合真实回归、八路并行和131秒新段失败；不改首次创建时间，不提升阶段/整卡验收。\n"
stage_path.write_text(stage, encoding="utf-8")
receipt = {"started_at": started, "ended_at": ended, "head": head, "origin": remote, "original_T_tasks_unchanged": True, "original_T_tasks_sha256": hashlib.sha256(original.encode()).hexdigest(), "whole_cards_accepted": [], "stage": "G-C in_progress/partial", "active_at_snapshot": 8}
(Path(__file__).parent / "parallel_progress_20261016_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
