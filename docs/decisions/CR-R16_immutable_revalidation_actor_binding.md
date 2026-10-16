# CR-R16 · 自动重判任务的不可变持久身份绑定

文档首次创建时间：2026-10-16T16:35:50+08:00
本次写作开始时间：2026-10-16T16:35:50+08:00
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

本次修订写作结束时间：2026-10-16T16:35:50+08:00
最后更新时间：2026-10-16T16:35:50+08:00

## 分页兼容补充 · 2026-10-16T16:43:52+08:00

原候选fingerprint包含评估历史，写一页新历史后会使下一页cursor失效。批准唯一R16作者为内部CandidateDiscoveryService增加可选assessment_created_before：默认None保持原候选与旧cursor合同；使用时必须aware，取服务端持久parent时点，签入游标/query fingerprint且筛选assessment.created_at<=截止。新重算追加历史不改变这份历史候选集合；资产、权限、epoch或规则真实变化仍必须拒绝旧cursor。截止值不来自HTTP自报，不能用该冻结掩盖事实/授权变化。

父任务每页发现→同事务创建幂等子任务及带冻结截止/游标的下一parent，调用和页/child预算保持可控；未消费位置必须持久化并返回partial，不把发现上限当已全部处理。无需新增平行签名游标、索引或业务表。独立复验须覆盖默认旧行为、截止边界、后写续页、真实变化拒绝、空/旧/新增候选与重放。schema与身份7列合同不变。

本次补充写作结束时间：2026-10-16T16:43:52+08:00
最后更新时间：2026-10-16T16:43:52+08:00
