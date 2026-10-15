# CR-R12 · 混合检索生产前向迁移

创建时间：历史未记录；本文件实际写作时间将在任务报告按系统时钟登记。

依据：用户批准 R12/T30 的真实 PostgreSQL、pgvector、OpenSearch 与 R00 的能力切片执行；内部模型和独立审查已冻结于 ba1548d/d3f553，限定 Ship 不代表产品入口已接通。本补充准确实现已批准建设范围，不改官方评分、金标、分母、阈值或盲测原则。

原行为：hybrid_schema 独立 metadata 提案只有生成代外键，作者 PG 测试通过临时 create tables 验证服务，生产 head0019 尚无这四张派生表。新行为：0020 在普通 Alembic forward 链增加四表，与现有服务列、主键、索引、vector(384)和已有 check 保持一致；附加六种事实身份外键及两处 outbox 外键，防止不存在的证据、事实或任务收据成为已索引投影。PG 仍是事实和任务权威，派生表不新增业务事实。

兼容：旧 R05 的 retrieval_chunks/grounded_answers 和旧 vector 空间不修改；旧事实、任务、游标、版本、源、资产快照不回写。源表历史不得删除，派生投影通过原 indexer 已验证 epoch、ACL、当前父绑定和水位。独立外键保证身份存在，不能替代返回前完整父关系与权限校验。新迁移不设置 create_all 产品路径，不自动迁移用户生产库。

迁移：先备份并执行普通 forward upgrade，再由唯一 indexer prepare_generation/refresh_scope 写投影。旧安装新增四表没有回填；应逐授权 scope 从已记录知识变化任务重建。worker 注册、catalog 无 outbox reconciliation、默认语义服务与问答 API 是后续接线切片，不能因 DDL 完成声称接通。

回滚：优先停止新索引消费者并回退应用读取路径，保留派生表和历史证据；若确需删除这四张可重建派生表，应先导出其水位/收据并确认停止全部新消费者，再在明确隔离或授权维护范围使用对应 downgrade。此批不运行 destructive downgrade；旧事实绝不删除。

任务影响：R12:T30 的生产部署切片；完整 R12/T30/T35 仍需 API、worker、图候选、多轮多跳、真实支持判断、前端、正式评测。不会提前验收 R11/R14/G-D。

测试影响：真实隔离 PG forward0019→0020 的全部旧行保留；反射四表列/PK/vector/authorityFK；非法维度/state/缺 outbox 被拒；把原 T30 的全部行为函数和断言原样导入新的自有 testDB/schema fixture，使用真实迁移且禁止 MetaData.create_all，真实 OpenSearch 和已有 E5 权重仅测试本有界切片。原测试文件不改，fixture 语义与唯一真实 E5 检查分别计层，完整回答 SLA/gold/manual 不计通过。初次 fixture ScopeMismatch 为真实 harness error，保留原1/7 errors，不包装成业务红→绿。

独立审查：作者仅 awaiting_review；生产迁移冻结 SHA 后新非作者 reviewer 必须复跑上述 forward、权限和失败检查，并核对源码/调用链与此变更记录，再由主控登记限定结论。
