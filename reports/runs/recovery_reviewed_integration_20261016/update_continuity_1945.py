"""记录独立切片证据、受控资源和当前恢复合同，不提升整卡验证状态。"""

import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent


def strict_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def clock():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=strict_pairs)


def write_text(path, content):
    path.write_text(content, encoding="utf-8", newline="\n")


started = clock()
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert head == "ea15232a627e5c4871f1676bc5358cf67ca67b69"
user_hash = hashlib.sha256((ROOT / "frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest()
assert user_hash == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
state_path = ROOT / "progress/task_state.json"
state = read_json(state_path)
original_tasks = json.dumps(state["tasks"], sort_keys=True, ensure_ascii=False)
layers_before = {key: value["verification"].copy() for key, value in state["recovery_tasks"].items()}
notes = {
    "R06": "SourceProof8355/5f8独审469限定Ship后cb868主集成，root final444green，先7missing archive红保留。9OPS55a+11CORE440联合首审4Must；CORE7be/9a3e修5文件并131+14offline/native3<=22.5s，自有进程0；原严格type旧3注解须限定补齐，OPS未对齐新core/freshjoint复核未做。OID/marker空、activation七false，final安装/6h未开始；原ledger42不重置，old1670.457817s不拼。",
    "R07": "Structured bridge dd296/4a2f新模块+3test frozen，207offline25security10legacy通过。旧b141模块PG30green但final LIMIT9只2offline/final PG not_run；fresh独审r07_structured_fact_bridge_first_independent_review已派先离线、待槽B。CVSS/EPSS/KEV only reported非适用安全，CWE缺同claimowner/另五维unsupported显式partial；默认消费者未接，Graph/UNKNOWN不放宽。",
    "R12": "Full projection822已主集成451646；旧完整worker20s/ACK/WAL仍未整证明。批5CBM真实CBM_CACHE_DIR独立缓存2592nodes14818edges/schema+callers0，源码交叉定位不以图单边证明能力。",
    "R14": "三个read adapters427/b30 frozen138offline25PGgreen，fresh独审已派槽B；默认factory/其余四工具未接。真实链5885 actual22.390s/Planner430tokens+QA1996tokens共2426费用unknown，6同evidence重复引用正确拒绝，Critic/Reporter未跑。QA prompt c6b9/6e27只instruction+promptversion395offlinegreen，fresh独审0paid。preclaim sharedff7/58469offline50PG；broker原业务3红+准备2红均保留，新诊断证明URLschema被connect_args覆盖；仅test builder append strictschema/NullPool，7920harness/doc6e latest一次A480s已授权，19:39真实57014+ACK待60sec补投，不提前判green。",
    "R15": "主9b default实际API/browser独审限定Ship，243backend648frontend39PG+7TCP组10Edge组，服务17:56:58.594521前停/audit0；模型质量/wholeR15/live/PGserver重启尚未验证。",
    "R16": "ca47/ec54游标M1ACL无epoch、M2rule新小ID已原非作者fix复核limitedShip，75offline38PGgreen/audit0，原两红保留。Root尚未整合full f56 runtime+ca47 closure，默认factory/persistentHEX64secret/parentfan-in/recommendation和negativewatch/双时间未完成，wholepartial。",
    "R17": "主9b默认UI/API限定Ship见R15，用户buildinfo保护。R14/R16新业务尚未默认接通，工作台整卡/e2e全部场景未完成，不把此前648组件断言算live。",
    "R18": "02ce/3db正规入口SDK16tests与完整source cb868已主集成；Root372=349SDK+23publicextensions，非独审canonical358=349+9publicv2。Default readonlyBearer六tool/SDK安装打包/三plugin/cleanLinuxCI仍未闭环。",
    "R20": "registry136独审限定Ship，完整5输入ea已本地；root144green，原combined120s timeout因helper缺start/raw记录事实保留；原rootgate109.703s exit1/25未登记命中13 untracked路径未解除。ea本地提交前stageguard拒绝ZIP7database_userinfo但Root错误继续commit，未push；metadata4f508ZIP/6同bdc5+1同0f13，values不打印。新provenance唯一作者只diagnosis/proposal，6为脱敏Engine显示、1负例仍核，不能按synthetic目录一概豁免。CPU746/947新独审3daa证实合法near最终0.953125<1却0.9提前杀，12native10pass2fail，earlyfaultpipe8sec缺readiness/EOF ownerunknown；唯一作者限定离线修复，native旧12不重置，wholeR20/securitygate仍failed。",
    "R24": "提前准备eb95726files与fresh独审17988限定Ship，13官方/U14/T60/110slice对照完整，36/36静态、46paths、官方PDF4page亲看；仅骨架。R24-A候选未ready、R23未执行、整R24partial。PPT后置不取消，人工双人gold/授权资产范围未知，正式指标unknown。",
}
for task_id, note in notes.items():
    task = state["recovery_tasks"][task_id]
    task.setdefault("history", []).append({"recorded_at": started, "event": "review_pipeline_and_gate_correction", "note": note})
    task["verification_scope_notes"] = note
state["recovery_tasks"]["R24"]["status"] = "in_progress"
state["recovery_tasks"]["R24"]["implementation"] = "partial"
state["recovery_tasks"]["R24"]["slices"]["A"]["status"] = "in_progress"
state["recovery_tasks"]["R24"]["slices"]["A"]["implementation"] = "partial"
state["updated_at"] = started
state["updated_by_task"] = "R00-R24-controller-continuity"
assert original_tasks == json.dumps(state["tasks"], sort_keys=True, ensure_ascii=False)
assert layers_before == {key: value["verification"] for key, value in state["recovery_tasks"].items()}
write_text(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")

shared = f"""## 当前权威续接与所有权 · {started}

主控 codex/full-delivery-recovery@{head}；origin=https://github.com/Gowin-liuyin/dianziCup.git，最后已核远端G-B c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7。G-C in_progress/partial，无新阶段pass/push；G-D/E独立切片准备。用户frontend/tsconfig.tsbuildinfo SHA {user_hash}原样，不stage/build/restore；原60T/历史/整卡layer状态不改绿。

本地ea暂存检查failed却Root错误继续commit，已告知用户；stageZIP7命中只保存元数据，不输出值，未经新精确provenance审查绝不push。Root根门25新untracked/13路径failed，旧136registry并不覆盖它们；新诊断/proposal等待freshreview，不放宽scanner或目录/压缩包规则。完整扫描原109.703s材料保留，CPU硬界新独审needs_changes，不能把仅171/144unit通过叫安全门通过。

实际工作并行（报告时间采样，勿当长期background）：新readtools独审/QA prompt独审/R07 bridge独审；原R14作者latest7920真实broker复验；Core作者限定runtime_limits类型边界补齐；CPU原作者near+pipe限定离线修复；secret原作者ZIP7与13未登记provenance诊断。Root唯一App/config/公共合同/schema/迁移/锁/progress/主合/push；各author/reviewer只owncodexWT、rawreports。共有16槽允许6–10+按必要性分配；PG最多A/B两个heavy，A broker一次480s、B readreview一次480s，R07先离线待明确换槽。各≤2conn/NullPool/单pytest/自有marked DB/schema，禁止硬编码生产DSN/downgrade/全局改上限/kill他人。

真实父PG25432/Redis26379/OS29200截止2026-10-17T21:49:15+08不扩。Neo4j原deadline19:35:43.312788已真实guardian截止，stop19:35:45.626509–58.116515 exit0，termination显示Runningfalse/Pid0/ExitCode0/OOMfalse；graceful日志尚待核，不仅Docker0称优雅。R06新OID/marker空/七flagfalse，尚未启动6h；原单版本段不得拼。真实R14旧chain2modelcalls2426tokens22.390s却引用重复失败，costunknown，无新增paid请求。生成密钥仅隔离DPAPI到childenv，无秘密出报告。

下一关键路径：Core final类型→唯一OPS对齐11corehash→原非作者joint20复核→Root实际资源identity/privatefinal/新DB/6h；broker实际ACK补偿→原独审fix→默认LangGraph fullclosure；新read/QA/bridge首次review→分别defaultconsumer接线，R16完整runtime+持久cursorsecret及fan-in/history/watch；协议六tools/安装/三plugins、R11defaultAssessment和正式性能/恢复/CI/cleanrepro/材料仍内部可执行。双人核验/裁决、FOFA授权资产范围未知，CNNVD IAB login未确认，ZoomEye401；PPT后置未取消。不能目标complete/blocked或说只剩外部。R24-A→R23→R24-B顺序不变。

"""
for relative in ("progress/context_handoff.md", "progress/recovery_workstreams.md", "progress/blockers.md"):
    path = ROOT / relative
    write_text(path, shared + path.read_text(encoding="utf-8-sig"))

addenda = {
    "CR-R14_shared_read_adapters.md": ("R14", "三种共享读取工具的内部联合类型", "GET_ADVISORY 接Event UUID并复用EventDetailResponse；GET_INVENTORY接asset/snapshot UUID并复用AssetSnapshotResponse及原READ_ASSET；FIND_CHANGES接event UUID/limit1..25/cursor<=2048并返最小ChangesPage(change_id/type/epoch/time)，不返payload/entity_ids/source IDs。参数以各distinct tool Literal严格校验，旧{}仍UnconfiguredArguments/not_configured，已配置缺ID为invalid_arguments，不全表扫。工具可用集合只新增真实注入三adapter的implspec；default TOOL_SPECS两纯工具保持。Changes cursor复用原OpaqueEventCursor与currentACL/epoch，候选<=101/closure<=257。Inventory不隐式授READ_PUBLIC，仅读固定tenant epoch一行。") ,
    "CR-R14_qa_citation_instruction.md": ("R14", "QA引用合同的模型输入说明", "仅QA generation_request补13instruction lines及prompt_version r14-qa-2：全局citations按evidence_id唯一，claims复用同citation；quote为exact连续单行覆盖所附claims，不拼原文/元数据或生成UUID/offset，不能支持则unknown。schema仍r14-qa-1/max2048/repair0；原validate_citations/Graph/Critic/Reporter不变。5885旧真实六重复引用继续被拒绝，不能去重旧输出当live成功。"),
    "CR-R07_structured_fact_proof_bridge.md": ("R07", "结构化事实的原文支持读取", "新StructuredFactProofPort以当前认证Actor/tenant和3UUID(event/evidence/revision)读取原ClaimRecordV3+Owner路径，输出reported/partial/not_found。reported仅指来源报告值，不把unknown条件改TRUE/资产影响或安全。CVSS/EPSS/KEV必须同claimowner+assertion/evidence/path/span/hash；CWE无sameclaimowner为partial、其余五维unsupported，不从raw/兄弟claim推owner。最多8facts、原5s、有界SQL每claim证据LIMIT9(8+lookahead)，原文IO两短事务中间、父/claim/assertion/link/evidence/block/epoch有序锁二次核验当前ACL/版本。legacy SourceProof、R10四predicate门保持。")
}
manifest_path = ROOT / "contracts/task_manifest.json"
manifest = read_json(manifest_path)
for filename, (task_id, title, behavior) in addenda.items():
    path = ROOT / "docs/decisions" / filename
    assert not path.exists(), "do not overwrite addendum: " + filename
    write_text(path, f"""# {filename.removesuffix('.md')} · {title}

文档首次创建时间：{started}
本次写作开始时间：{started}
状态：approved_for_implementation；当前有界完整授权内的实现合同细化，awaiting独立首审核对。

{behavior}

兼容性：不新表/迁移/依赖主版本/公开REST权限/金标/阈值/分母。共享公开旧DTO、raw历史、fact condition/freshness和权限不改；新内部read能力未注册时仍原not_configured，未知不默认成功。迁移无需数据重写。回滚仅撤销新adapter注入或新QA prompt配置，保留事实、任务和原审查/失败证据；不得delete历史或downgrade。主控持有公共合同与默认App入口；作者只冻结报告所列文件；本卡及原映射T卡全部切片仍需合并验收。

任务/测试影响：{task_id}原范围与六类验收完整保留，受影响R12/R14/R17/R18消费需重新caller核查及定向回归。首次必须新非作者冻结完整source/material输入亲复offline/关键负例；PG所需read/bridge亲复实际finalSHA并测currentACL/tenant/history/conflict/statement预算/锁。QA本批0新增付费，审查后真实模型另开显式有限run并保存原请求输出和完整耗时。frontend/e2e/live/manual未执行写not_run，不用fixture顶live。无需新的用户重大授权，独审未过不记accepted。

本次写作结束/最后更新时间：{clock()}；修订人/root。
""")
    target = manifest["recovery"]["tasks"][task_id] if "tasks" in manifest["recovery"] else None
    if target is None:
        for value in manifest["recovery"].values():
            if isinstance(value, dict) and task_id in value:
                target = value[task_id]
                break
    assert isinstance(target, dict), "find recovery task map"
    target["dependency_reason"] += " 实现合同补充：docs/decisions/" + filename + "，须独立核对；原slice/whole前置与最终验收不变。"
write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
execution = ROOT / "docs/plan/00_execution_map.md"
content = execution.read_text(encoding="utf-8-sig")
assert "G4：四角色真实协作" in content
content = content.replace("G4：四角色真实协作", "G4：九职责真实协作（四角色仅为同条件基线）", 1)
write_text(execution, content + "\n\n## 内部恢复合同与阶段门补充 · " + started + "\n\n" + "\n".join("- [" + filename.removesuffix(".md") + "](../decisions/" + filename + ")：" + title + "，原卡最终验收不变，独审后生效。" for filename, (_, title, _) in addenda.items()) + "\n\nG4概要九职责更正依据原已批准CR-R01；四角色仅同条件基线，未改变评分/原金标/分母。R24提前材料仅partial，不越过R24-A→R23→R24-B。\n")
cards = ROOT / "docs/plan/12_recovery_task_cards_20261014.md"
write_text(cards, cards.read_text(encoding="utf-8-sig") + "\n\n### 内部读取与引用合同补充 · " + started + "\n\n" + "\n".join("- " + task_id + "：docs/decisions/" + filename + "；该切片不等于整卡完成。" for filename, (task_id, _, _) in addenda.items()) + "\n")

for stage in ("G-C", "G-D", "G-E"):
    path = ROOT / f"reports/stages/recovery/{stage}.md"
    content = path.read_text(encoding="utf-8-sig")
    for label in ("本次写作开始时间", "最后更新时间", "本报告证据截止时间"):
        content = re.sub(r"(?m)^" + label + r"：.*$", label + "：" + started, content, count=1)
    content += "\n" + shared + "\n本轮切片证据（原全卡gate未变）：\n\n" + "\n".join(f"- {key}：{value}" for key, value in notes.items()) + "\n\n本轮合同补充：" + "、".join(addenda) + "；awaiting新独审，阶段不放行。\n"
    ended = clock()
    content = re.sub(r"(?m)^本次写作结束时间：.*$", "本次写作结束时间：" + ended, content, count=1)
    content += f"\n文档修订记录：{ended}，/root同步新review与CPU/安全门证据、更正本地commit过门失误及受控Neo4j截止；首次创建时间保持，原红不覆写，原T状态不变。\n"
    write_text(path, content)

receipt = {"started_at": started, "ended_at": clock(), "head": head, "original_tasks_unchanged": True, "whole_layer_states_unchanged": True, "protected_user_sha256": user_hash, "formal_addenda": list(addenda), "stage_gate": "G-C in_progress; no push; ea boundary failed pending provenance review", "R24": "in_progress/partial; A only preparation"}
write_text(RUN / "continuity_1945_receipt.json", json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(receipt, ensure_ascii=True))
