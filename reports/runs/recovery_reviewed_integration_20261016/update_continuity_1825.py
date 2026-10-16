"""同步冻结切片证据和当前所有权，保留原任务与历史验证状态。"""

import hashlib
import json
import re
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
assert head == "9b632296d8c2ca08fc4150bf1d7a7d799bdf326a"
user_file = ROOT / "frontend/tsconfig.tsbuildinfo"
user_hash = hashlib.sha256(user_file.read_bytes()).hexdigest()
assert user_hash == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
state_path = ROOT / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_pairs)
original_tasks = json.dumps(state["tasks"], ensure_ascii=False, sort_keys=True)
notes = {
    "R06": "9OPS55a63/11CORE440346联合准备冻结，fresh独审r06_nine_ops_core_first_independent_review已派；新OID/marker尚空、七flag false、ready false，私有final/新库/activation/6h未执行。真实旧ledger42累积，不能重置或拼旧1670.457817s。SourceProof8355/5f8新revision独审469=451offline18PG限定Ship，未main集成；old same-body仍partial。",
    "R07": "九维producer subject event:UUID/condition unknown 与Graph消费者互操作新独立诊断已派，不先改truth或放宽supported。九维真实live与whole验收未闭环。",
    "R12": "完整projection8223已独审后集成451646；main边界索引2465nodes13774edges。首schema缺project红保留，重试成功；XDG_CACHE_HOME单独未隔离CBM实际cache，后续须CBM_CACHE_DIR。worker完整20s/ACK/WAL未整证明。",
    "R14": "默认driverb8b75/ed549独审M01经新诊断实PG证实queued attempt0 publishedoutbox1且recover0。唯一作者D:/wt/r14-preclaim-delivery-recovery-fix1修shared jobs/runtime+专用driver；已批准own Redis26489/64MiB0.25CPU32PID/maxclients16、singleworker、15min和PGslotA≤2conn；不得用旧fakeIP模型失败代替live。DoH Planner200 deepseek-flash433tokens，仅Planner，QA/Critic未跑。",
    "R15": "HTTPa4/6dd原独审417通过后rootdd33集成，初漏recommendation_contracts真实collection红保留；9b补完整依赖/默认App挂载+23routeTests，root160通过。fresh默认API/browser独审9b limitedShip：243offline648frontend39originalPG+7TCPgroups10Edgegroups，服务17:56:58.594521前停/audit0。真实模型/质量/PGserver重启/性能未验。",
    "R16": "f56/014独审两Must：相关来源ACL不改epoch时旧cursor不失效；rule-only分页跨epoch漏新发布小ID。原作者18:10:18.616→27.490重跑原2probe均failed，B释放audit0。按批准相关ACL closure FP和frozen rule epoch/scope续页绑定修复中，不重置预算。默认factory/持久HEX64secret/parentfan-in/recommendation与negative-watch/双时间仍待。",
    "R17": "29frontend模块已完整4a依赖集成733/0e88，7e6默认App/workspace/proxy集成，9b补入口契约；default9b真实API/Edge limitedShip见R15，不当whole工作台/加载全部场景完成。用户buildinfo字节受保护。",
    "R18": "Actor/a7+gateway32d、SDKc5、Detached76独审后已集成。SDK02ce/3db正规入口fresh独审358joint+默认349重跑，limitedShip未main16test集成；3旧red保留。readonlyBearer六工具默认产品入口/三插件/cleanLinuxCI未验。",
    "R20": "secretfix source3b2/materialf1a002总136，fresh LF/CRLF各171+原T06gate作者green，原reviewer新LF/CRLF worktree定向复核中，5完整source依赖未main。native054e/2f2新handle诊断已派；bodyfault0.828125green，normal1.015625仍red，+3handle未闭合，不放宽原1s。",
    "R24": "候选交付骨架/13requirements-U-T真实gap映射新独立准备已派；用户PPT后置未取消，无最终评测/人工gold/WordPPTvideo冻结。R24-A→R23→R24-B顺序保持。",
}
for task_id, note in notes.items():
    task = state["recovery_tasks"][task_id]
    task.setdefault("history", []).append({"recorded_at": started, "event": "frozen_slice_evidence_and_ownership_refresh", "note": note})
    task["verification_scope_notes"] = note
state["updated_at"] = started
state["updated_by_task"] = "R00-R24-controller-continuity"
assert original_tasks == json.dumps(state["tasks"], ensure_ascii=False, sort_keys=True)
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

shared = f"""## 当前权威续接与所有权 · {started}

主控 codex/full-delivery-recovery@{head}，origin核对仍授权URL，最后已核远端G-B c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7；G-C in_progress/partial，无新阶段放行/push，G-D/G-E独立准备。原60T/历史/整卡验证不改绿，user frontend/tsconfig.tsbuildinfo SHA {user_hash}保持、不stage/build/restore。

实际主分支集成451646 R12、a7/32d Actor授权、c5 SDK、76 Detached、733/0e88全前端依赖、1cdb0028/29、7e6 App/proxy、30db0030+Assessment内部Actor、dd33/9b完整R15HTTP/defaultAPI。root两个遗漏依赖均保留collection红与修复证据。main全量旧3492=3469pass22fail1error未重新整跑；切片测试不能给whole背书。source/doc/remoteSHA分开。

主控唯一共享合同/schema/迁移/锁/配置/App/progress/集成commit/push；唯一指定R14作者拥有其隔离WT shared workers/jobs.py、workers/runtime.py、investigation/runtime.py、workers/investigation.py及直属tests，root当前不得重写这几文件。R16作者仅自有revalidation模块/tests；secret作者仅安全登记五依赖；其他新reviewer/诊断/交付骨架各自WT/runs/report。作者不push/签accepted，首审新Agent，原非作者只同批fix复核。

实际新并行：R14共享恢复修复；R16游标修复；R06 9+11 fresh独审；R20 secret fresh LF/CRLF复核；R20 native handle新诊断；R07→R14 evidence互操作新诊断；R24-A候选骨架准备。主控持续源集成/正式CR/真实资源门。PG最多2heavy，当前A限额授权R14恢复，B原R16两反例18:10:27前已释放audit0；每Agent单pytest串行/NullPool≤2conn/自有标记schema。不得增加PG上限/kill他人。真实静态WSL Docker路径已核，禁止误开Desktop替代。

PG25432/Redis26379/OS29200父截止2026-10-17T21:49:15+08不扩；Neo4j2026-10-16T19:35:43.312788+08不扩。新R06窗口21600s+关闭900s，ledger42成本unknown，OID/marker空activation全false，新采集尚未开始。old1670.457817s不拼新6h。模型仅DoH Planner真实200/deepseek-flash352input81output433total、costunknown，evidence partial后QA/Critic未跑。

外部：双人核验/裁决及FOFA授权资产范围仍未知，CNNVD内置登录未确认不取cookie、ZoomEye401；PPT后置未取消。内部尚有R14七write adapters/search、R11 default assessment、R16 fan-in/历史/旧新空/撤回、公开六tool/三plugin、正式评测/性能/恢复/CI/材料/cleanrepro；不能说只剩外部或整个目标blocked。下一：两Must修复复核→共享runtime接线，SourceProof+SDK完整依赖显式集成与针对回归，R06fresh总协议审查→root实际资源identity激活门→真实单版本新窗口。维持R24-A→R23→R24-B。

"""
for relative in ("progress/context_handoff.md", "progress/recovery_workstreams.md", "progress/blockers.md"):
    path = ROOT / relative
    path.write_text(shared + path.read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")

for stage in ("G-C", "G-D", "G-E"):
    path = ROOT / f"reports/stages/recovery/{stage}.md"
    content = path.read_text(encoding="utf-8-sig")
    for label in ("本次写作开始时间", "最后更新时间", "本报告证据截止时间"):
        content = re.sub(r"(?m)^" + label + r"：.*$", label + "：" + started, content, count=1)
    content += "\n" + shared + "\n本轮切片证据（不更改整体gate）：\n\n" + "\n".join(f"- {key}：{value}" for key, value in notes.items()) + "\n\n修订人/root；问题与原红如上，阶段新reviewer未放行，无本阶段push。\n"
    ended = clock()
    content = re.sub(r"(?m)^本次写作结束时间：.*$", "本次写作结束时间：" + ended, content, count=1)
    content += f"\n文档修订记录：{ended}，同步冻结切片和所有权，首次创建时间保持；整体阶段未验收。\n"
    path.write_text(content, encoding="utf-8", newline="\n")

def append(relative, text):
    path = ROOT / relative
    prior = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    path.write_text(prior + text + f"\n本次写作结束/最后更新时间：{clock()}；修订人/root。\n", encoding="utf-8", newline="\n")

append("docs/decisions/CR-R14_preclaim_delivery_recovery.md", f"""# CR-R14 · 认领前投递恢复与有界补偿

文档首次创建时间：{started}
本次写作开始时间：{started}
状态：approved_for_implementation；本次用户完整批次授权内必要缺陷修复，awaiting独立复核。

实PG诊断source b8b75/ed549证明认领前OperationalError被Celery ACK后job仍queued/attempt0/leaseNone，publishedoutbox1且recover0，重进程也不补。旧恢复只扫running根因共享，不能仅补调查一个caller。独立报告G-D-R14-default-runtime-review-1.md与R14-preclaim-recovery-diagnosis.md保留原反例。

批准唯一作者workers/jobs.py/runtime.py和调查专用driver：due queued/retry_wait在最后真实published_at超过60s且无有效pending时，同事务SKIPLOCKED追加同job/payload outbox；无outbox仅created_at超过60s后补，已有有效pending不重复。全job历史delivery_attempts聚合上限job.max_attempts×3（默认15），耗尽job failed/delivery_attempts_exhausted；终态或耗尽未发outbox仍published_at NULL，next_delivery_at UTC9999-12-31和固定停止错误，不假造publication。一次GROUP BY聚合后join，不逐job扫描；beat扫描→relay持固定事务advisory try-lock，抢不到返回既有字段0。task从权威PG job_type选取，不信broker自报topic；消费前PG失败标delivery_unavailable，directdriver保留原OperationalError oracle，补偿靠共享PG扫描，不无界autoretry。

兼容/迁移：无新表/索引/身份权限/任务业务attempt/lease/模型预算更改，source450/caps不改；对既有shared任务恢复生效。回滚可停新dispatcher入口，保留真实outbox/事实/history，不downgrade/删除旧任务。测试：原queued反例原断言、重复beat/并发/有效pending/后续retry/15次上限/终态不可假published/原消费者、真实PG/Redis/Celery单workerACK补偿/重进程恢复。独立reviewer固定新source亲跑；6类及live分列。Root批准own Redis26489 64MiB CPU0.25/PIDs32/maxclients16、≤15min、PGslotA≤2conn，0model/public请求。原PG服务不重启不清队列，持久秘密只环境/加密引用。共享事实权威仍PG，费用unknown，评分/盲测不变。
""")
append("docs/decisions/CR-R16_immutable_revalidation_actor_binding.md", f"""\n## 两个独立游标缺陷的兼容修复 · {started}

本次写作开始时间：{started}；状态approved_for_implementation，原f56/014独审两Must未关闭。M1无旧assessment时相关source ACL改变且epoch未变，cutoff cursor未失效；仅证明合同冻结漏ACL，不声称已有泄露。M2rule-only续页跨真实publish epoch，after_id使新小ID规则漏调度。原两PG反例18:10:18.616→27.490+08 2failed保留。

批准cutoff非None候选相关latest visible rule及event/doc/revision/evidence/claim ACL闭包fingerprint，避免无关全source扫描。内部CandidatePage/RevalidationPlan可选rule_scope_fingerprint 64hex；ChangeRequest成对可选frozen_scope_epoch_map和frozen_rule_scope_fingerprint，strict校验；默认None保留原raw cursor/querydigest形状，不加公开HTTP输入。nextparent同immutable binding持久这些字段；rule-only续页先核frozen epoch/map/FP再after_id，变化时一次有界restart同时清cursor/afterid/两frozen字段，剩余预算不重置。legacy afterid缺新binding显式从头restart；首无位置按原coalescing。enqueue前再次核FP，覆盖无epoch的ACL改变。

兼容/迁移/回滚：不新表/index/权限/评分或gold，更不unknown改safe；停新调度仍保留旧history/outbox/binding。root公共0030不再变，指定作者仅revalidation内部+tests；原reviewer必须原两probe亲复green，并追加ACL/lowerID/重放/预算/旧None/v1形状回归。默认factory和secret/parentfan-in不因本修复声称完成。
""")
append("docs/decisions/CR-R06_reprepared_nine_script_binding.md", f"""\n## 联合身份、原生marker和累计额度修订 · {started}

本次写作开始时间：{started}；批准实现/准备，独立激活门未过。实际旧ToolRoot804e clean依赖要求与新core直接复制矛盾，因此明确双身份：旧ToolRootDEPLOY@804e保持clean与旧observer，独立固定CORE目录D:/dianzi-runtime-cache/r06-nine-script-core-20261016只放新source440346十一Gitblobs，OPS55a九Gitblobs。准备启动时ToolRoot必须全clean；运行中仅固定currentnonce原observer root_live_gate.json与live_RUN_ID未跟踪输出允许，tracked/HEAD/其他变化拒绝。原gate14fields不加nonce，通过segment_id='segment_'+nonce绑定。

新库test_dianzi_r06_nine_script_20261016只前向0029；OID/marker尚None不启用。root实际创建后原生COMMENT ON DATABASE/读取shobj_description确认strictJSON exactproject/kind/run_id/owner/product_sha/maximum_seconds/queue/redis_prefix/created_at和rawSHA，不拿旁表metadata自称身份。旧OID3680428/旧facts/cursors不变，不默认clone。公开冻结OPS/core互相引用hash不要求文档自提交SHA，避免自引用循环。

累计budget ledger42经旧初11subset+旧close42+fresh42同ID/type/time/provenance并集去重亲只读验证，source_budget_ledger SHA2604347a4559d3353a045a57393ea632f90ba74fd2c98615400751672e0d03b9；总450/prestop410/solo418不扩，对应remaining408/368/376。21600+900/父deadline/其他资源cap不改，真实wire/cost unknown。准备finalprivate/newcore安装/新库/activation不因临时WSL正例记live。兼容回滚仅停止新自有资源，保留旧包/旧库/失败证据，绝不清全WSL/用户资料。新fresh reviewer完整20文件冻结亲复后root再做实际OID/marker/端口/预算/权限资源门，6h不能拼历史段。评分/原分母/gold不变。
""")
receipt = {"started_at": started, "ended_at": clock(), "head": head, "original_tasks_unchanged": True, "user_buildinfo_sha256": user_hash, "whole_verification_statuses_not_promoted": True, "stage_gate": "G-C in_progress, no push", "updated_tasks": list(notes)}
(RUN / "continuity_1825_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=True))
