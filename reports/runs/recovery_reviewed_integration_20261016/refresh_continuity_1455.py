"""同步已取得证据的续接索引，保留原任务、历史与整卡验收状态。"""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
ZONE = ZoneInfo("Asia/Shanghai")
STARTED = datetime.now(ZONE).isoformat(timespec="seconds")
SOURCE = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """拒绝重复键，避免状态更新吞掉先前登记。"""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


protected = ROOT / "frontend/tsconfig.tsbuildinfo"
protected_before = hashlib.sha256(protected.read_bytes()).hexdigest()
state_path = ROOT / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
original_tasks = json.dumps(state["tasks"], ensure_ascii=False, sort_keys=True)
notes = {
    "R06": "83bfabab源码/028db098材料在新非作者fix2复核。34unit与33native为作者局部证据；225个自有进程组归零。真实新6小时采集尚未启动；旧段1670.457817秒已结束，不能拼接。9-script配置兼容/源库identity等启动门待主控落实。",
    "R12": "822c6f55/627edfd7在独立复核；COMMIT负例、生产预算、direct/default epoch与网络分类已实际复跑。原58单批55绿3资源guard红保留，随后原三例独占max3短批3绿；原network分类1红另保留。生产整体20秒、WAL/ACK限制仍未闭合。",
    "R14": "42f工具网关有限独立Ship已源集成048c；LangGraph dbc34d72/875f122b作者146离线和34真实PG，已创建全新非作者审查。七写adapter未配置、真模型not_run、默认API/worker未挂载。Detached086d/a0f已157离线，12PG现在获单槽；graph120秒与legacy lease60秒/worker25/30秒尚待接线解决。",
    "R15": "7f纯推荐策略经独立局部Ship已源集成7ae。持久服务5e2d3cbc作者20真实PG与253离线待材料冻结/新独立审查。root0027@9e6与public27def schema已提交；真实API尚未写，POST Idempotency-Key持久receipt待增量，不提升整卡验证。",
    "R16": "2ff候选重判器经独立局部Ship已源集成52b。原空结果/旧命中/新命中选择有局部算法PG证据，真实变化worker、历史失效/撤回与推荐重判闭环尚未挂载。",
    "R17": "推荐/报告UI521c3bb7作者638全前端、107target、6Edge fixture，已创建全新非作者审查。App导航与/api/v1代理由root接入，尚未完成真实后端浏览器联测。动态背景/reduced-motion有前期独立局部证据，不等整工作台验收。",
    "R18": "SDK普通异常封闭27778/cf933经独立352+6绿有限Ship；旧sync3原样另3红。Actor53f/5f原98中窄key1红，消费方dbc34修复组合fresh复核获PG单槽。原main尚未合全部async/closure/Actor增量，不声称六工具全HTTP/live。",
    "R20": "Windows两CPU原门仍失败1.109375/1.15625秒；第二诊断证明守卫故障窗停止采样且当前产品未启CPUrate，清树成功不能追回CPU。24核平台rate2000不代表0.2核，83对照仍不证明严格总量门。最小实现修复待独立包，不放宽阈值。",
}
for task_id, note in notes.items():
    task = state["recovery_tasks"][task_id]
    task.setdefault("history", []).append({
        "recorded_at": STARTED,
        "prior_status": task["status"],
        "prior_implementation": task["implementation"],
        "event": note,
    })
    task.setdefault("verification_scope_notes", {}).update({"recorded_at": STARTED, "current_batch": note})
assert json.dumps(state["tasks"], ensure_ascii=False, sort_keys=True) == original_tasks
state["updated_at"] = STARTED
state["updated_by_task"] = "root recovery integration evidence and rolling independent review"
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

handoff = f"""## 当前权威续接与所有权 · {STARTED}

主控codex/full-delivery-recovery@{SOURCE}；origin授权URL不变，最后已核远端仍G-B c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7，G-C未放行/未push，G-D/G-E仅独立准备。受保护用户frontend/tsconfig.tsbuildinfo SHA {protected_before}，不stage/build/restore。原60T、金标、阈值、分母和历史保留；整卡状态不因局部Ship提升。

实际集成：312958正式5CR/2直接+18传递依赖；84871补root遗漏job_types；048c工具网关、7ae推荐策略、52b变化候选；e4c289精确补3冻结R15 fixture；9e6 root0027四表迁移/public27defs/文档精度修订。主仓离线3492=3469pass/22fail/1error/69.41%，原日志recovery_integrated_offline_20261016_1238保存，尚未整批重跑：三fixture红已恢复依赖待复核，16旧codec预期、旧迁移head、2真CPU红和T07 PG缺配置分列，不能改skip。源集成曾漏job_types与fixture是主控实际缺陷，非依赖环境借口。

正在并行：R06原独立reviewer fresh fix2；R12最后封包（全部PG audit0已released）；R14新非作者LangGraph审查；R17新非作者推荐/报告UI审查；R15持久服务材料冻结；Detached作者12PG；Actor原reviewer fresh组合PG。root负责公共合同/0028–29迁移/API/App/worker、资源与秘密配置、续接/阶段文档、唯一commit/push。作者和review均独立WT，不写main业务/progress，不自行push/accepted或递归spawn。每批初审必须新非作者；旧review只定向复核同批修复。

PG最多2heavy batches：当前Detached与Actor各一个、每人串行pytest/NullPool≤2conn；R14新review先offline准备后申请。原R12 max3两独占窗均已结束audit0，不能当全局并发扩大。PG25432/Redis26379/OS29200期限2026-10-17T21:49:15+08，Neo4j期限2026-10-16T19:35:43.312788+08。真来源6h尚未新启动，9-script配置与资源启动门仍待root。原06:19:43–06:47:34段1670.457817秒不算6h。

关键接线：R15已0027/schema但API/PG request receipt未实现；R14 graph源码已出，但default120/max600秒与旧lease60/Celery25/30秒需实际一致方案，Detached未注册；Actor窄key消费方误拒已作者修，须复核后源集成；SDK async闭环组合待源集成；前端521c导出workspace尚未App挂载和/api/v1代理。正式live/人工/性能/持续时效/盲测/cleanrepro与R24-A→R23→R24-B仍不完整，不是仅剩外部阻塞。

模型/API费用用户已授权任务内使用、不设人工费用上限；仍需每任务调用/并发/期限上限和实际usage/cost未知记unknown。已有授权凭据旧仓外locator需重新定位，不能把Codex账号当产品密钥或向Agent传密钥。人工双人独立label/裁决、FOFA授权资产范围、CNNVD登录/下载未确认；PPT后置未取消。Goal active，继续实施/审查/集成，不能结束或假称后台不停工作。

"""
for relative in ("progress/context_handoff.md", "progress/recovery_workstreams.md"):
    path = ROOT / relative
    path.write_text(handoff + path.read_text(encoding="utf-8"), encoding="utf-8")

for stage in ("G-C", "G-D", "G-E"):
    path = ROOT / f"reports/stages/recovery/{stage}.md"
    text = path.read_text(encoding="utf-8")
    appendix = f"""\n\n## 最新证据与修订 · {STARTED}

本次写作开始时间：{STARTED}；实际结束由本轮续接收据记录。主控：/root；已集成代码SHA：{SOURCE}。阶段仍in_progress/partial，未整阶段审查、未push。原首次创建时间保留。旧正文为历史时点，本节更正：06:19:43启动段已在06:47:34结束，1670.457817秒，非连续6小时；新真实采集尚未启动。

{"；".join(notes[key] for key in ({"G-C": ["R06", "R12", "R20"], "G-D": ["R12", "R14", "R16"], "G-E": ["R15", "R17", "R18"]}[stage]))}

当前真实验证：主仓离线recovery_integrated_offline_20261016_1238记录3492项/3469通过/22失败/1错误/零skip，覆盖69.41%。三冻结fixture已修复未整批复跑，其余旧codec/migration oracle、两CPU业务红与PG环境缺失不能合写正常。独立各包的命令/精确时间/版本见各自报告与run，重复测试数不累计为整阶段通过数。browser fixture不作live，模型/人工/正式性能/干净环境复现not_run或blocked，评分不自评通过。

独立审查：SDK资源/stdio组合27778/cf933经新组合358绿，旧sync3另红；R12原三fence独占7.297秒/pytest5.45秒三绿，旧单批3guard红与network分类红保留；新R14/R17首次非作者已启动，Actor/Detached各获真实PG单槽。所有报告尚待主控归档与集成核验，局部Ship不替代本阶段候选review。

具体开放问题：R06九脚本新配置尚未启动；R14图lease与worker超时/持久身份接线；R15真实API与POST请求receipt；R17默认workspace挂载/代理；R20严格CPU总量门。负责人root协调对应独立作者，修复需新固定源码与复验。合同变化记录312958五CR与9e6 public/0027，无评分/盲测/范围削减。提交与推送尚未发生；最后已核远端仍G-B c229a7f4，本阶段不能过门。

"""
    text += appendix
    ended = datetime.now(ZONE).isoformat(timespec="seconds")
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("最后更新时间：") or line.startswith("本报告证据截止时间："):
            lines[index] = line.split("：", 1)[0] + "：" + ended
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

ended = datetime.now(ZONE).isoformat(timespec="seconds")
assert hashlib.sha256(protected.read_bytes()).hexdigest() == protected_before
receipt = {"started_at": STARTED, "ended_at": ended, "source_sha": SOURCE, "scope": "documentation/index only; whole-task verification/status retained", "task_count": len(state["tasks"]), "protected_sha256": protected_before, "state_sha256": hashlib.sha256(state_path.read_bytes()).hexdigest()}
Path(__file__).with_suffix(".json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=True))
