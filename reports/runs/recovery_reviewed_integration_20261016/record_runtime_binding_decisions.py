"""记录实际核到的运行绑定缺口及最小持久身份适配，不提升验收状态。"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
ZONE = ZoneInfo("Asia/Shanghai")
started = datetime.now(ZONE).isoformat(timespec="seconds")
core_path = ROOT / "docs/decisions/CR-R06_reprepared_nine_script_binding.md"
core_appendix = f"""

## 核心绑定兼容修订 · {started}

本次写作开始时间：{started}；修订人：/root。

实际只读核查发现原Core804并不支持配置换绑：authorization.py固定PRODUCT_SHA=e310；controlled_supervise.py固定产品目录、e310、旧sourceDB/0016与旧queue；deploy_runtime_entry.py固定旧Redis prefix/queue。新9脚本仅改configuration会被拒绝，或仍指旧资源。本条纠正此前“原core行为保持”适用于新包的错误兼容判断；旧10core物理字节和历史8ops包仍只读保留。

批准指定独立核心集成人在新worktree/new-core目录为上述三个入口增加唯一固定运行绑定适配，必要时新增一个小run_binding.py，不对旧文件原地改写。新绑定精确包含产品1cdb9e7d99b7d24f702f5f19309a56d5afedd526及clean checkout、marked新库name/OID/0029_recommendation_receipts、新queue/Redis15 prefix、新RUN/nonce/OPS/DEPLOY路径、原observer与9ops/新core全部hash。绑定来自root准备后冻结并独立复核的文件，字段缺失/未知/不一致在外部IO前拒绝；不得把schema检查取消、把任意body/path/URL变为配置自由度或静默兼容旧queue。

所有资源caps、父期限、七activation=false和ready=false保持。新core所有变更要连同9ops/config/prepare/deploy重新固定source/material与总manifest审查，旧804的Ship不自动背书新core。准备作者唯一写9ops/config，核心作者唯一写新core及直属tests，root负责公共变更、库创建/0030不纳入本采集基线和最终启动。原sourceDB只读保护，无游标/事实迁移的默认许可；新段如不迁移，必须注明从新的可证起点观察，不能声称延续旧段。

测试影响：重复键/未知字段、产品/表head/DBname+OID+marker/queue/prefix/run/nonce任一变更、旧8hash缺controller、corehash漂移、父期限/预算、activation缺失全部拒绝；正例只能准备成功，不能假造live启动。回滚只停新自有资源/保留材料与新库，不清旧库/旧queue、不downgrade/改全局权限。此为已授权持续采集运行入口的必要兼容修复，无新增范围、评分或费用授权变化。
"""
core_path.write_text(core_path.read_text(encoding="utf-8").rstrip() + core_appendix, encoding="utf-8")

owner_path = ROOT / "docs/decisions/CR-R16_immutable_revalidation_actor_binding.md"
owner_text = f"""# CR-R16 · 自动重判任务的不可变持久身份绑定

文档首次创建时间：{started}
本次写作开始时间：{started}
修订人：/root
状态：approved_for_implementation；实现与独立验收另行登记。

## 问题与授权依据

已批准R16/T36–39要求变化后重判，R18内部ActorReference要求真实PG owner绑定。现job_payloads没有数据库不可变guard；仅把Actor放该JSON并称不可变会削弱授权，不能用change.actor_user_id冒充当前用户。采用已有认证工厂、PG job/outbox和AssessmentService，不创建第二套任务状态。

## 最小合同

新增revalidation_job_bindings，仅7字段：job_id为PK/FK job_runs.job_id；actor_user_id为FK users.user_id；tenant_id可空但资产执行必须当前租户；authorized_role仅现有四Role；actor_reference为NOT NULL JSONB object且由服务端认证工厂产生；payload_sha256为64hex；created_at为NOT NULL timestamptz。0030迁移唯一由root写，新增表UPDATE/DELETE触发器拒绝，绑定与job/payload/outbox同事务创建。

执行owner port先锁job与binding，核job_type、user/tenant和恢复payload的SHA；ActorJobOwner仅取可信行，不从HTTP body、change自报字段或队列参数构造。再通过已有lock_actor_job_scope检查当前会话/key/角色/权限、撤销和过期，现有权限不增加。AssessmentService及CandidateDiscoveryService构造函数类型允许str或内部ActorReference，认证逻辑复用现有锁与检查，不接受新公开凭据形态。

子任务revalidate_assessment，持久输入仅change_id、target_epoch、asset_id、asset_snapshot_id、rule_id、rule_version。先只读有界发现再enqueue子任务，避免追加历史使分页fingerprint失效；单规则/单资产复用prepare/commit，不覆盖历史，不改变原knowledge_change索引任务。发现预算未完保持partial并记录未处理位置；未知/无规则/冲突/撤回均不伪造safe。正常generic DetachedJobHandler可完成该子任务，调查graph自完成语义另处理。

## 兼容、迁移和回滚

原cookie字符串构造函数与公开API合同兼容；无原表改列、无原事实/历史覆写。部署前只做0029→0030前向迁移。旧无binding任务拒绝或明确blocked，不凭user_id补身份。回滚应用可停止新增重判调度，保留新表及已追加历史，不downgrade或删除任务。新表只有授权绑定元数据，不储存Bearer/key明文。

## 任务与测试影响

R16执行切片与R18内部owner适配，不代表整T39/R16完成；推荐/问答负watch、双时间查询与默认注册仍需各自证据。指定作者唯一写revalidation模块/7列表定义和直接tests，root写Assessment类型、迁移与默认job注册。必要unit/contract/security/真实PG覆盖缺binding、payload篡改、跨租户、窄key、撤销、角色变化、会话过期、同job重放、子任务幂等、事务回滚、乱序epoch、旧/新/空候选及历史追加。独立reviewer核本合同与实际触发器/产品路径后才能放行；不改金标、阈值、分母或盲测原则。
"""
owner_path.write_text(owner_text, encoding="utf-8")
ended = datetime.now(ZONE).isoformat(timespec="seconds")
for path in (core_path, owner_path):
    text = path.read_text(encoding="utf-8").rstrip()
    text += f"\n\n本次修订写作结束时间：{ended}\n最后更新时间：{ended}\n"
    path.write_text(text, encoding="utf-8")
receipt = {"started_at": started, "ended_at": ended, "files": [str(core_path.relative_to(ROOT)), str(owner_path.relative_to(ROOT))], "phase_accepted": False, "live_activated": False}
Path(__file__).with_suffix(".json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=True))
