"""Record the current integration and parallel ownership without promoting whole tasks."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent


def clock():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


started = clock()
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
protected = ROOT / "frontend/tsconfig.tsbuildinfo"
protected_hash = hashlib.sha256(protected.read_bytes()).hexdigest()
if protected_hash != "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d":
    raise RuntimeError("protected user file changed; do not alter or stage it")

note = f"""## 当前权威续接与文件所有权 · {started}

主控 codex/full-delivery-recovery@{head}；origin本轮22:13:45实际核对为授权URL；最后已核远端仍G-B c229a7f43ec9684a4e2d2e7a2ccb9f6ebfbfbee7。G-C仍in_progress/partial，无新阶段放行/push，后段仅独立准备；用户tsbuildinfo完整SHA {protected_hash}原样，不stage。原60T与整卡各层验证不因局部Ship改绿。

当前滚动并行：Root独占默认App/config/公共合同/schema/迁移/locks/progress/Git；新r17_investigation_workspace_implementation只新frontend/features/investigations与直属测试；新r18_public_read_producer_implementation只两个public_extension模块与直属测试，PG lane A已授权一次240s；新r20_backup_restore_rehearsal_implementation只backup_restore脚本/测试/runbook，PG lane B先准备后真实受控演练；ContentStore作者新fix1只专属ContentStore+直属测试，新的非作者first review固定03/6fea；secret-loader作者helper显式guards与合成测试，连续两次仪器同根因停止扩patch，由新console-host诊断处理；六tool新review固定40b2/4959；R06原reviewer只封存已完成191静态材料。全部独立WT，主控实际7至10个Agent滚动（非长期background承诺）；不向其他用户聊天或自行push/accepted。

R11/R17 Root默认接线d884经新的非作者材料1aa9限定Ship：126后端、27真实PG、713前端、14 Edge场景通过。真实资源窗口21:37:55.757至21:42:38.421，DB/schema/conn/监听与已记录PID0；Edge所有原生子PID审计not_run。原初始fixture/assert/selector红完整保留；全阶段没有因此通过。R18模型011资格修复经3366独立567green限定Ship。R19原atomic d6/6298修复经094c独立27green，FD关闭/foreign保留/未知残留failclosed；旧118全树峰10越旧cap4不合规保持，不能被新峰5覆盖。

Root当前未提交R14批9：已精确合e56完整driver/preclaim/outbox并只叠c6 workflow_service 13行QA指令，默认调查router挂/v1与/api/v1；普通worker按持久cursor key注册既有R16 Detached handler。首离线163中151green/12因遗漏QA保存输入失败；22:16:11从冻结6e27恢复一项66426B原输入，SHA769b0684ce0a1b9b6ca01adc386d2098154ffcdf8d0cd9fe6073cc8985f6aa5d与原oracle相符，不修改测试预期。22:20:38至22:20:42相关14+新增默认registration2共16green，pytest1.37s；旧失败不抹。类型15source此前0，新增unit格式首check1后只格式化。read3适配仍未接workflow消费者；R07桥bb04、R16 fan-in/watch/history、public六producer/三插件及完整九角色还有内部工作。

ContentStore独审新Must：写入失败后cleanup lstat/unlink错误覆盖主异常，三负例真实红，作者新WT修复中；原作者新增一个unit异常期待错误仅获批准更正该expect，历史03/6fea不改，非金标/194旧合同。首次213全树峰11触cap10终止exit124保留，base launcher同213重跑green峰10；strict7根原Celery Any subclass单错与常规配置区分，不称全strict绿。secret-loader optimize绕assert修复合成业务预期两轮一致但outerexit1/全树保守9超cap8；新的诊断处理conhost生命周期，不隐去计数。

PG父截止2026-10-17T21:49:15+08:00不延长，A/B最多各一重pytest/NullPool≤2conn。旧Neo4j已停，新R06单版本6h仍未启动；旧Product1cdb已知缺陷不重启做观察。秘密精确registry25与ZIP7边界门尚未闭合，新frontend XML单shape仍withheld；不将局部0match当全秘密通过。双人金标/裁决、FOFA授权资产范围、CNNVD登录下载仍未知，PPT后置；费用unknown如实。不称只剩外部/完成/blocked。

下一：冻结默认调查Root批9给新非作者真PG/wire审查；完整输入证据22项入tree；read3/R07消费者与专用worker部署、R16历史重判、六producer/插件、backup恢复、安全门及R06新版本激活真实6h。阶段最终仍R22→R24-A→R23→R24-B。

"""
for relative in ("progress/recovery_workstreams.md", "progress/context_handoff.md", "progress/blockers.md"):
    path = ROOT / relative
    previous = path.read_text(encoding="utf-8-sig")
    path.write_text(note + previous, encoding="utf-8", newline="\n")

state_path = ROOT / "progress/task_state.json"
state = json.loads(state_path.read_text(encoding="utf-8-sig"), object_pairs_hook=no_duplicate_keys)
original_tasks = json.dumps(state["tasks"], sort_keys=True, ensure_ascii=False)
state["updated_at"] = started
state["updated_by_task"] = "R00-R24-controller-parallel-batch9"
updates = {
    "R14": "Root批9合e56+仅c6 QA指令，默认router挂载与持久key条件下R16handler注册；151green/12输入缺失红保留，恢复冻结原输入后相关16green。默认PG新审查待冻结，read3实际消费者及完整九角色仍缺。",
    "R17": "Rootd884默认研判与工作台由新独立1aa9限定Ship，126后端/27PG/713前端/14Edge；不扩签整R17。新的调查workspace独立feature实现中，RootApp唯一所有权。",
    "R18": "011公共模型资格修复3366独立567green限定Ship；40b2六tool SDK freshreview正在封存。新PG public producer独立实现，NormalizedIntel文档身份绑定补CR；ask/stack/tasks产品接线仍缺，不称六全通。",
    "R19": "6298标注FD修复094c原非作者27green限定Ship；旧118资源峰10>4保留。候选/人工金标未完整，双核裁决缺输入，不升级整卡。",
    "R20": "ContentStore cleanup覆盖主异常3红，新fix1修复；secret-loader优化guard修复两轮业务预期通过但仪器exit1/资源9>8，新诊断处理，不签全安全。backup恢复独立实现；原CPU/秘密门未闭。",
}
for task_id, description in updates.items():
    task = state["recovery_tasks"][task_id]
    task.setdefault("history", []).append({"recorded_at": started, "event": "parallel_batch9_evidence_and_ownership", "note": description})
    prior_notes = task.get("verification_scope_notes")
    if isinstance(prior_notes, str):
        task["verification_scope_notes"] = prior_notes + "\n" + started + " /root: " + description
if json.dumps(state["tasks"], sort_keys=True, ensure_ascii=False) != original_tasks:
    raise RuntimeError("original T task records must remain unchanged")
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

contract = ROOT / "docs/decisions/CR-R18_public_read_identity_bindings.md"
with contract.open("a", encoding="utf-8", newline="\n") as document:
    document.write(f"""
## {started} · PG producer内部身份映射澄清

依据R18既定NormalizedIntel语义与现有PG schema，intel_id绑定documents.document_id，revision_id只引用同document的当前归一化revision；这是内部字段接线，公开schema/评分/权限/分母不变。Vulnerability路径仍event_id，intel_id由当前可见event_documents→document/revision关联取得。多来源用共享事件聚合并保留每条证据文档归属，禁止一个document冒充全部event；稳定业务排序选择可投影的当前document，缺关联/归一化/权限时明确缺口。

实际冻结六SDK工具是ask/check_stack两POST与search_vulns/get_vuln/list_sources/get_task_result四GET；Root派单中getAssetRiskSummary命名错误已更正，未新增工具或GET。risk摘要属于check_stack的冻结envelope。当前backend仅questions/assessments/jobs，缺公共typed task关联时返回not_configured，不能把任意job包装成ask/stack成功。

Source.enabled表示该来源在当前固定注册与global polling配置下是否可自动调度，不新增逐来源持久状态或把global开关当逐源证据。health与data_mode按真实采集收据/原文metadata，未知保留。兼容性：既有reader和ID不迁移、不重写历史；回滚移除新增公开adapter入口，PG源数据保留。影响R18 producer/SDK pagination/身份错配、权限、来源状态及风险分母测试；新非作者必须核本澄清是否准确落实授权，尚不等于producer验收。
""")

ended = clock()
receipt = {"started_at": started, "ended_at": ended, "baseline_sha": head, "protected_user_file_sha256": protected_hash, "task_statuses_promoted": False, "original_T_records_preserved": True, "secret_values_read": False, "holdout_answers_read": False}
(RUN / "parallel_continuity_batch9.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
