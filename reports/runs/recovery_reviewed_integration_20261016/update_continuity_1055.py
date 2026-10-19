"""Record scoped evidence, protect original task history, and restore a required frozen fixture."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def clock():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


started = clock()
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert head == "8d62b54d83a3e6b56aeeb23102faa777496328db"
user_file = ROOT / "frontend/tsconfig.tsbuildinfo"
assert hashlib.sha256(user_file.read_bytes()).hexdigest() == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
state_path = ROOT / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_pairs)
original_tasks = json.dumps(state["tasks"], ensure_ascii=False, sort_keys=True)
notes = {
    "R06": "PREP f13 独立kernel review ea2baca6 needs_changes：selector初始化异常遗留child/只停止child后额外自有后代残留；真实WSL两负例，review自有清理0。新fix1 WT实施中，activation七false，尚无新6h采集。旧1670.457817秒不能拼接。",
    "R07": "输入审计0c57/648经原独立f1ff有限Ship，3真实父ACL竞态关闭；生产0023 16484已独立86d有限Ship待集成，九维真实模型仍未整验收；旧NVD oracle红保留。",
    "R10": "Neo4j投影707经d7有限Ship，11源/测试文件已实际集成e514；生产0025 16484已有限审待合，default knowledge_change图消费者未接。Neo4j自有deadline19:35:43.312788+08不延长。",
    "R11": "SBOM隐私dcbc独立58cf有限Ship，2源文件集成05684；forward0021/22在main。真实默认API/browser source17ab联测原单位资源缺失549+1红保留，精确原fixture恢复后557绿；live产品资产仍须授权范围。",
    "R12": "conversation1e/eb独立022e有限Ship，268执行绿，生产0024 16484待合；default projection eeb独审d5发现22.843秒IO超20及public10000/tenant1无关分区SQL57014两Must，root8d62修完整async IOdeadline/SQL分区先过滤，原reviewer新WT复核中。其他变化消费者仍partial。",
    "R14": "已显式独立分派tool_gateway/capabilities内部实际授权PG证据读取与纯版本比较，WT从17ab；九职责LangGraph持久图/真实协作尚未实现，不能以2工具当九角色。",
    "R15": "独立policy/report_builder纯规则包WT从17ab，复用AssessmentReceipt和引文，不造第二研判；真实PG订阅/推荐持久API与R14前置尚未接。",
    "R16": "独立真实PGassessment变化候选包WT从8d62，新模块only，涵盖旧watch/空规则watch/新增asset候选；完整失效重判推荐撤回/双时间读取尚未接。",
    "R17": "已审5587/18d的16frontend文件集成8d50；独立新真实Edge author最终6/6含第四snapshot历史只刷新产生REVALIDATE→current刷新恢复，557原unit。awaiting新非作者冻结review；不代替整工作台。",
    "R18": "SDK060十源测试文件已合17ab；MCP c691/260原review3377限定Ship，299distinct绿，待主合。SDK整体deadline/执行中IO取消新独立包实施；APIkey expiry锁竞态原review red，fix2 8e048原真实probe红→绿，原20/新4/57/Ubuntu15绿awaiting冻结复核。公共profile831独立768 Ship 28+97，4ccc GitSHA文档同步；六REST/MCP工具、HTTP current-auth/async ActorRef/三插件仍未接。",
}
for task_id, note in notes.items():
    item = state["recovery_tasks"][task_id]
    item.setdefault("history", []).append({"recorded_at": started, "prior_status": item["status"], "prior_implementation": item["implementation"], "event": note})
    item["status"], item["implementation"] = "in_progress", "partial"
    item["verification_scope_notes"] = {"recorded_at": started, "current": note + " 整卡验证层不因局部通过提升。"}
state["updated_at"], state["updated_by_task"] = started, "root bounded recovery integration and parallel execution"
assert original_tasks == json.dumps(state["tasks"], ensure_ascii=False, sort_keys=True)
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
snapshot = f"""## 当前权威续接与所有权 · {started}

主控codex/full-delivery-recovery@{head}，origin=https://github.com/Gowin-liuyin/dianziCup.git本轮真实复核。最后已核远端G-B/c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7，未G-C阶段放行/push；G-C仍in_progress/partial，G-D/G-E明确独立准备。原60T和历史不变；保护用户frontend/tsconfig.tsbuildinfo SHA3c587e，不stage/build/restore。

实际源集成：05684 SBOM privacy、8d50 frontend16、e514 N4 projection11、17ab SDK10；通过显式source-only Git blob diff，不覆盖原raw/report。8d62 root R12完整IO deadline和SQL分区过滤修两真实Must，新WT非作者复核；不是旧eeb通过。source-only曾遗漏8 frontend serializer所需原报告JSON，freshGit ENOENT红保留，root此轮补提交原冻结fixture，不改tests。

并行文件所有权：root公共合同/API/worker/DB迁移/锁/状态/Git/push；R06作者D:/wt/r06-observed-restart-fix1仅minio helper及直属验证；R12独立review新D:/wt/r12-default-projection-review1-fix1仅读8d62；R17实际UI验收D:/wt/r17-integrated-sbom-browser-workbench（实际路径以作者材料为准），仅自有browser tests/run；R18 key作者D:/wt/r18-api-key-expiry-fix2仅credentials与直接tests；R18 SDK deadline新WT从260仅sdk/client/MCP调度；R14 D:/wt/r14-tool-gateway仅investigation/tool_contracts/tool_gateway/capabilities；R15 D:/wt/r15-recommendation-policy仅recommendations/contracts/policy/report_builder；R16 D:/wt/r16-assessment-candidates仅revalidation/candidates/contracts。全部禁止自行扩大范围、push/accepted/progress、读秘密holdout、递归spawn。每新批初审均新非作者，修复可原reviewer新WT复核。

资源：最多2heavy PG batches、每Agent一个pytest串行/NullPool/own markedDB/schema；现在R12复核占1，UI/key已释放0ownconn。任何后续先申请slot，不提PG上限、不杀其他session。WSL PG25432/Redis26379/OS29200截止2026-10-17T21:49:15+08；Neo4j2cb自有deadline2026-10-16T19:35:43.312788+08。受控来源未新启动；kernel PREP两Must要闭环并fresh sourceDB identity/marker/resource gate后才允许新6h。旧11h授权记录未知不伪造，新21600s当前任务授权已明确。

已审待源集成：R07 audit0c57、R12 context1e、生产0023–26 16484、MCPc691。key8e048作者已真实锁等待修复绿但须原独立复核。新review报告/manifest/raw必须归档，源SHA/文档SHA/remoteSHA分开，有限Ship不当整卡accepted。

外部人工仍双人独立label/裁决未知、FOFA授权资产scope未知、CNNVD内置浏览器登录未确认（不取cookies）、ZoomEye401；PPT后置未取消。R14–24完整平台/正式盲测/性能/cleanrepro/最终文档演示未闭环；用户最新扩并行不替代验收，持续实现。下一关键路径：修复审查→真实采集新段；root合已审内部模块/production迁移→API/worker接线；R14工具+LangGraph、R15持久推荐、R16变化处理与UI/client流水线。R24-A→R23→R24-B顺序不变。

"""
for relative in ("progress/context_handoff.md", "progress/recovery_workstreams.md"):
    path = ROOT / relative
    path.write_text(snapshot + path.read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")
blockers = ROOT / "progress/blockers.md"
blockers.write_text(f"## 最新阻断传播 · {started}\n\nR06新采集启动被两真实kernel残留Must阻断，作者fix1中；R12索引M01/M02 root8d62等待原reviewer真实复核；R18 expiry锁等待fix2待独立复核，完整sdk执行中取消待实现。局部准备和不依赖这些能力的内部模块继续开发，不宣称G-C或整卡过门。双人金标/授权资产scope/CNNVD可下载资料/ZoomEye仍外部缺口。\n\n" + blockers.read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")
fixture_path = "reports/runs/recovery_r17_sbom_workbench_20261016/backend_contract_samples.json"
fixture = subprocess.check_output(["git", "show", "5587deb124f06b9aa14fb7feb22cdc9493ae4883:" + fixture_path], cwd=ROOT)
destination = ROOT / fixture_path
assert destination.is_file(), "canonical archived source must exist"
assert hashlib.sha256(destination.read_bytes()).hexdigest() == "92f5a0cac56ccd97c63af16bd14418cbc1c42cf4803c3ab6627f419235a6e331"
assert subprocess.check_output(["git", "hash-object", "--path", fixture_path, str(destination)], cwd=ROOT, text=True).strip() == "82c40263274fb65517037ab5e3f2d3982f151d67"
assert json.loads(fixture) == json.loads(destination.read_bytes())
(RUN / "continuity_1055_receipt.json").write_text(json.dumps({"started_at": started, "ended_at": clock(), "head": head, "original_tasks_unchanged": True, "fixture_git_blob": "82c40263274fb65517037ab5e3f2d3982f151d67", "fixture_raw_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(), "user_buildinfo_unchanged": True}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"started_at": started, "head": head, "original_tasks_unchanged": True, "fixture_verified": True}))
