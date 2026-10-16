# CR-R18 · 公开问答当前身份与原子限速

文档首次创建时间：2026-10-17T04:26:11+08:00
本次写作开始时间：2026-10-17T04:26:11+08:00
状态：approved_for_implementation；冻结源码和真实PG独审之前不验收。

依据已批准R18协议/API-key权限与PG权威，不新增公开DTO或问答评分门槛。现 GroundedQuestionService只接受cookie str，预约insert事务没有锁当前身份；公开适配不得拿APIkey绕此缝隙、另算一次rate或把WorkflowResult冒充QAAnswer。

_lock_answer_scope/_expire_pending_answer/read_grounded_answer/ask的session_token扩为str | ActorReference，沿用已审 lock_authenticated_scope。ask新增可选keyword credential: AuthenticatedCredential | None；ActorReference的API-key调用必须匹配同当前凭据/用户/tenant/operation。新预约insert返回成功的同事务先锁当前身份与READ_PUBLIC、再consume_api_key_rate_limit(operation='ask')；预算拒绝回滚预约，冲突/重放不重复计数，Model/检索IO不得发生在事务内。初读历史、预约、实际外部IO前和最终回执均验证现有身份/权限/截止，revoked/expired拒绝且不伪成功。cookie旧路径保持兼容。

任务用户/租户从认证上下文，不接受请求体自报；此前已保存answer/trace不覆盖，idempotency key冲突保持409。此改动只闭合credential seam，不称已支持多轮/资产/时间/调查：原限定单event不静默解除，R12/R14具体能力另接共享服务。费用/usage保存真实provider输出，未知unknown，不把编程账号当APIkey。

无需迁移/新依赖，影响R05/R12/R14/R18/R20和所有QuestionService调用方。回滚停止新credential调用，保留answer、usage和历史，cookie老接口正常。测试当前/过期/撤销/跨租户/限定scope、原子限速rollback、新请求与重放冲突/并发、无外部IO在锁内、真实PG以及原cookie回归。API适配/defaultApp/CORS/组件选择/typedtask绑定还有独立缺口，本切片不签整R18/Stage。


## 2026-10-17T05:04:19+08:00 · 真实PG初审后的根因修复

新独立审查在同一PG answer行实际等待后观测数据库预约期限已过；host墙钟滞后时仍返回scope。正常墙钟对照拒绝，原WHERE clock_timestamp在锁等待前计算不能替代等待后检查。唯一作者须复用同connection PostgreSQL clock在pending行锁、身份锁和终写提交前重验，核expire/history共同路径；completed历史不因420秒预约期过去而被抹除。原等待/正常对照oracle和红保留。

EventEvidenceRetriever constructor新增keyword-only data_mode:DataMode=live，只接受live或fixture；读取器使用受信构造mode，默认旧调用兼容live。require_current保持staticmethod，新增keyword-only data_mode=live；两个retrieval调用显式self.data_mode，最终问答调用显式服务mode。默认question_routes工厂唯一构造line传settings.data_mode。请求体不控制模式；unknown/unmarked与跨模式继续拒绝。原cookie PG barrier helper仅外部兼容新keyword透传，原锁时序和assert不改、双manifest记录；不修改hybrid另一业务切片。

新PG输入有明确fixture标签桥，使用成熟source_data_mode_metadata(fixture)合法policy，不能把合成内容标live。asset-only负例需合法ANALYST签发受限key，再验证ask拒绝，不能扩大VIEWER权限。锁等待观测使用同观察connection的pg_stat_clear_snapshot，避免事务缓存误称未等待，不增加第三target连接。实际收集为24new+24old=48；原26/22手算错误保留历史并更正，不改变case、金标、分母或验收阈值。原fixture/setup/instrument红与源ee06保留，新fix2继续awaiting_review，由原未参与实现的独审定向复跑。
