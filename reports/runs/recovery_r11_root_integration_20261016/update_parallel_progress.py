"""Update the single progress authority without changing original T-card acceptance."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


stamp = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert head == "6aeeeec5489b92bb49613fe5daa4eec379182348"
protected = ROOT / "frontend/tsconfig.tsbuildinfo"
assert hashlib.sha256(protected.read_bytes()).hexdigest() == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
path = ROOT / "progress/task_state.json"
state = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
original = canonical(state["tasks"])
updates = {
    "R06": "New observability4c/material804 independently reviewed limited Ship 65+11AST, report6bd600/manifestec07. Original e310 source stopped1670.457817s; no six-hour window or new actor started. Signed-age/phase root cause historical unknown; ready for a separately bounded restart preparation.",
    "R07": "Default90e and taxonomyb5 integrated. New input audit136/material014 has independent source/document/revision ACL race3 confirmed reds; author new isolatedfix under PG admission. Original NVD0wire oracle still32/1 and baseline red, not closed. Production0023 remains pending; whole nine-dimension live not proved.",
    "R10": "Neo4j resourceCAP_KILL fix1 independently limited Ship report638222; currentCID2cb/core261968, graceful5.650104s/container0/same-volume restore. Projectionfix2code707/materiale8 independent132+5 limited Ship reportd7a3; production0025/defaultworker/API not wired, futuredeadline/fault/live not_run.",
    "R11": "Main reviewed SBOM51ed and forward0021/22 sixa integrated, but new integratedreview6a needs_changes2Must relative locator/private path and placeholder early return. Fix source dcbc/material54f1 awaiting original reviewer;117/616 and PG25/18/105/119 author green not independent acceptance. OriginalHEAD0019 oracle and R07NVD oracle remain red; no phase gate/push.",
    "R12": "Conversation4module source6259/materialf557 awaiting NEW nonauthor review;31pure/41PG/156oldgreen author evidence,3businessreds retained. Production0024/grounding/publicquery event/time/defaulthybrid worker/modelstillunwired, no complete T31/T35 claim.",
    "R17": "SBOM frontend18d/material5587 original independent reviewer limited Ship report89cf/manifestc5e2:557unit66Edge typedfixture acceptance, oldbug-presence2red retained. Not merged to main yet; true currentPG/API/browser e2e/manual pending, wholeR17partial.",
    "R18": "RootKeyCRcd91 frozen; Keycode3c14/material8ae pendingNEWreview54tests/oldcookie23+1scannerred. Rootpublicextensions10+old14 identical/23contract/pinnedo200koffline3 prepared outsideworkspace, not yetfrozen/reviewed/wired. SDKsource6d230authorgreen; Gitrawseal2fail diagnosed8d8d, exact57renormalize1/110proof0/c5 checkpoint, finalrepairmaterial pending. Packaging677/595 pendingNEWreview; MCPf17/54e transportonly114fixture, 6tools/key/protocolbudget/plugins/fullClient/live stillpartial.",
    "R19": "Init recover source0b/material641 awaiting original reviewer109green author;old82/12protected. Capturablefailure cleanup repaired;SIGKILL/powerloss not implemented. Humanlabels0/gold0/fullscope/license still awaiting human and later toolwork, no formalblindfreeze.",
}
for task_id, event in updates.items():
    task = state["recovery_tasks"][task_id]
    task.setdefault("history", []).append({"recorded_at": stamp, "prior_status": task["status"], "prior_implementation": task["implementation"], "event": event})
    task["implementation"] = "partial"
    task["status"] = "needs_changes" if task_id == "R11" else "in_progress"
state["updated_at"] = stamp
state["updated_by_task"] = "R00 bounded recovery evidence integration"
assert canonical(state["tasks"]) == original
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
block = f"""## 当前权威续接 · {stamp}

主控 `codex/full-delivery-recovery@{head}`；origin实际授权URL未改变，最后远端核对仍G-B c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7。G-C in_progress/partial，无阶段放行或push；G-D/G-E为独立准备。原60T状态和历史原样保护；用户frontend/tsconfig.tsbuildinfo SHA3c587e未stage。

主控唯一public合同/默认API/worker/迁移0023–26/locks/progress/Git/push；package指定集成人只sdk/python metadata/license，credentials实现只两个新api内部文件，不改cookie管理路由。当前新公开schema/CR/report/test为rootWIP未freeze，不能给消费者拿尚未审的contract签完整能力。

已集成：R07默认durable90e/taxonomyb5、0020生产检索5b2、SBOM51ed、assessment/SBOM0021/22 sixa。新6a独审b8bb314/report与200manifest9a2d needs_changes：相对locator2输入与placeholder后危险段1输入3真红。作者新 dcbc/54f1已修并串行25/18/105/119绿，等待原reviewer复核。旧migrationhead0019和NVD全67→0wire oracle仍红，root正式合同演进待处理，不改gold/阈值/分母。

R07新审计136/014独审新3 private parentACL races阻断；fix1只ownedreader按source/document/revision历史refs SHARE +freshACL，原source/raw/历史不变。R12内部6259/f557等新review，0024/最终scopeeventtime/grounding/真实generation未接。R10projection707/e8已有限独审132+5绿、待归档/合/0025/defaulthandler。Neo4j2cb cap0xeb/core261968优雅关闭5.650104s与same-volume真实恢复；19:35:43.312788+08 deadline不变，未来截止/故障不算已测。

R17SBOM5587/18d已有限独审557unit66Edge，root待合；真实PG/浏览器尚待backendfix。R18SDK6d业务230绿但material归档发生两次failed还commit，诊断8d8d/toy16场景已核；精确57renormalize一次后110/raw/source169保护绿，c5 checkpoint，后续repair报告/新material仍未验收。Key3c14/8ae和package677/595等新review；MCPf17/54e仅两个工具/114fixture，不算六工具或真实HTTPauth。输出词表o200k officialhash446a...3613922B在工作区外，offline3/0network，初仪器错原红保留。

R19init0b/641捕获异常恢复109绿等原独审，SIGKILL/掉电恢复未实现；1真实dev候选、0human/0gold，正式冻结不成立。来源原段06:19:43.758521→06:47:34.216338共1670.457817s，42job/331doc/346rev/96459evidence/343knowledge_change blocked缺handler，新65test观测独审只允许root有限准备，不是新采集已经开始。

资源：PG25432被多pytest峰值打满FATAL too many clients，原红均保留；root当前重PG admission最多2，每Agent单pytest串行、ownfixture NullPool/显式dispose，不改生产pool/PG上限、不kill他人。R11fix已release0ownconn，N4review已release0schema/59ownnamespace清理，R07review已release0session，R07fix获1slot，其余新review先offline准备再申请slot。root实际查defaultApp已有lifespan engine.dispose，尚无已证产品泄漏，不能把峰值环境错误当它根因。

外部：双人独立标注裁决未提供、FOFA授权资产范围未提供、CNNVD内置浏览器登录未确认/不读cookies、ZoomEye401；PPT后置未取消。完整R13–24、真实九角色/报告推荐/全旧新empty重判/公开工具插件/正式评测复现/最终材料仍持续推进，不能因子片Ship结束目标。下一动作：新review/修复与production迁移、defaultknowledge_change/hybrid/model链、真实UI/API；R24-A→R23→R24-B顺序不变。

"""
for relative in ("progress/context_handoff.md", "progress/recovery_workstreams.md", "progress/blockers.md"):
    target = ROOT / relative
    old = target.read_text(encoding="utf-8")
    target.write_text(block + old, encoding="utf-8", newline="\n")
stage = ROOT / "reports/stages/recovery/G-C.md"
text = stage.read_text(encoding="utf-8")
for prefix in ("本次写作开始时间：", "本次写作结束时间：", "最后更新时间：", "本报告证据截止时间："):
    lines = text.splitlines()
    text = "\n".join(prefix + stamp if line.startswith(prefix) else line for line in lines) + "\n"
marker = "## 2. 当前真实状态与修改\n"
assert marker in text
text = text.replace(marker, marker + "\n" + block, 1)
stage.write_text(text, encoding="utf-8", newline="\n")
assert hashlib.sha256(protected.read_bytes()).hexdigest() == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
receipt = {"recorded_at": stamp, "head": head, "original_T_count": len(state["tasks"]), "original_T_unchanged_sha256": hashlib.sha256(original).hexdigest(), "whole_cards_accepted": [], "stage_accepted": False, "push": "not_run"}
(RUN / "progress_update_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
