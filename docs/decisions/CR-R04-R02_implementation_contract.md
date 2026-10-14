# CR-R04 / R02 · 持久化实施合同

首次创建/写作开始：2026-10-15T01:56:45+08:00；本次写作结束：2026-10-15T01:59:20+08:00；状态：awaiting_review。
本单落实03数据合同与已批准R02范围，未变更评分、金标、分母、栈或建设目标。
R00生效依据及既有兼容规则见CR-R04。主控/root冻结接口；实际实现须新独立审查，本文不代表验收通过。

## 认证工作包

0006_auth_state由root唯一写入，auth_sessions/login_buckets/login_attempts/audit_events见迁移源码。认证实现者只写authentication.py、新具体PG auth_state.py、专属测试和报告；禁止改此迁移、shared models、app.py、锁与全局状态。

保留现有HTTP返回、Cookie、30分钟TTL、5次/15分钟失败及在途限流、成功只释放自身占位、CSRF非ASCII403、服务端当前role。默认API必须显式装配PG状态，数据库失败不能退回内存。内存兼容仅供显式fixture；真实产品会话、审计与限制在PG，不使用Redis/Celery作另一权威。

AuthenticationSessionService增加关键字state_store（具体协议由实现文件定义并保持原位置参数兼容）。具体业务方法：reserve_login_attempt在短事务锁定client_key_hash桶、先提交占位再昂贵IO；失败保留至窗口过期；successful_login在同一事务保存session_hash、仅释放自己的attempt_id并写成功审计。authenticated_session单查询join有效session+当前users，保持身份/CSRF同快照；撤销幂等并立即对其他进程失效。session明文只给Cookie、不进库/日志；CSRF仅在可信数据库存储和当前会话响应中使用，不进审计/日志。

审计固定event/actor/tenant/trace/reason/submitted_keys/time列，不存任意请求JSON。数据库审计读取必须接受AccessScope、READ_AUDIT、租户过滤及有界分页；无scope的旧audit_events只用于明确fixture，不允许真实数据库无授权导出。失败未知用户审计tenant为空，只系统管理员可读。目录或PG错误固定503，不在错误/JUnit中回显凭据、DSN、hash或CSRF。

## 事实与富化工作包

复用0001 claims表，root保留公共迁移0007与knowledge/models.py所有权；实施者先交具体增量列/子表草案，root冻结后才能创建其映射。不得另建默认事实表或把整个对象塞进metadata。现有domain.ClaimRecord/enums/VisibilityScope为canonical，公共记录tenant=null，tenant记录由AccessScope限制。

旧knowledge ClaimRecord/private/current/published/value:object只能作为显式旧fixture适配，不能静默导入业务。public+非空tenant拒绝，不能清租户升为公开；model_hypothesis只能unverified，缺来源/支持校验不升为supported。旧SQL值/时间保留，新provenance缺失标legacy_unverified，不编引用。predicate受限值联合类型由root后续冻结，当前字符串合同不掩饰成完整九维。

具体仓储接受同一SQLAlchemy Session和AccessScope，内部不commit；批次先整体校验，保存实体/来源断言/证据/状态历史/关系/变更收据/epoch/jobs/outbox一起提交。publication_key按scope唯一，同digest返回原收据、不同digest冲突；SQL失败全部回滚、失败不占幂等key。两worker/连接并发发布必须通过真实PG实验。supersede只改当前有效性，历史不可覆盖；404只记录获取失败，不撤回事实。九维聚合/分类业务尚属后续卡，R02只提供真实可接线持久化能力。

ChangeEvent及可重放payload内容必须保存到PG或不可变对象，payload_ref明确为可读取实体引用；不能继续仅存哈希又声称可重放。复用jobs/outbox而不另建消息真相；R03负责真正消费。

## 证据、版本及事务公共约束

EvidenceSpan.start_offset/end_offset统一为规范全文Unicode code point、左闭右开。block.start/end也是全文坐标；quote校验使用block.text[start-block.start:end-block.start]。03 §3.3旧切片式中的局部下标须显式转换。旧证据无坐标版本，不猜测；0007增加坐标标识并按能验证的block归属迁移，无法确认者保留legacy并拒绝作为已核验引用。定位输出与持久化必须串接一个非零block起点的实际输入负/正例；重复引文需指定出现位置，不能默认首条。调用方/原测试若使用局部坐标必须显式适配，保留原行为意图而不删负例。

save_document_revision复用原函数并锁document父行；只末版相等复用，A→B→A保留三个revision。content_objects注册使用PG幂等upsert；scope epoch使用原子upsert递增RETURNING，不select后写回丢增量。未引用原文orphan可以保留待回收，不删除正在提交引用；GC与发布使用同一hash锁/保护规则。MinIO接口/实际资源在独立包落实，尚未验证不写通过。

## 前置与验收边界

当前R01整体仍needs_changes，G-A未过门。实际PG迁移/用户目录/认证HTTP自动检查已独立复跑；Vitest主版本批准、搜索TLS与前端cache不影响隔离数据库中的这些后端实现。按用户资源阻塞例外推进同G-A独立部分，独立runtime reviewer核对理由；不跨阶段签accepted、不越过依赖live门。

独立/root/r01_runtime_review本轮核对manifest.requires_slices及CR-R07后确认这些有限后端子步骤可独立实施，依据其G-A-R01-runtime-review-1-cache-recheck报告；未签R01:T03全部、R02或G-A。0006真实专用PG从0005升级，8运行边界集成例通过，仍不能替代空库/会话实现验收。

保留R02六实验与原T04/T05/T06/T17/T19/T21的36案例，见R02-preflight。真实PG跨进程登录/撤销/并发、发布中途回滚、A→B→A、当前/历史、越权读/搜候选/导出、同key不同digest、旧库升级及空库迁移必须实跑。unit/contract/security/frontend/e2e/live/manual逐层记录，未运行not_run。无模型、外源、人工金标不能声称正式指标通过。

回滚采用停止新写、保留原表/历史、前向修复或经实测的隔离备份恢复；不自动downgrade有数据的库。实施者仅awaiting_review，主控依据新的独立报告登记。
