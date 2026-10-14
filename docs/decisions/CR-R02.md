# CR-R02 · 事实权威与可重建投影

状态：accepted（用户建设决策已授权，准确落实经独立核对生效）。
首次记录时间：2026-10-14T20:52:23+08:00；最后更新时间：2026-10-14T22:31:09+08:00
提出/记录者：主控 /root。
授权依据：`prompts/12_full_delivery_parallel_push.txt` §§1、7、9；用户当前明确批准CR-R01–CR-R09。
独立审查：/root/r00_independent_review；review_ref=reports/reviews/recovery/G-A-R00-review-1-recheck.md；被审SHA=15d0272bd2a9e25d19397d8147e9c3cbe6016f9b。

## 原合同与问题

docs/plan/02_architecture.md §1/§9，旧OpenSearch向量与不增图数据库。

## 新合同与原因

模块化单体不重写。PG为唯一事实/任务/ACL权威；OpenSearch保留BM25，pgvector为唯一语义向量存储，Neo4j为已验证PG关系的投影；Celery+Redis单队列，MinIO内容寻址对象接口，LangGraph数据库检查点，Prometheus/Grafana与脱敏Langfuse追踪。

这是已要求效果的最小完整路线，复用现有模块与成熟组件；不建设并行仓库或另一套业务真相。

## 影响范围

T03/T05/T07/T30/T33/T49/T50；R01–R03/R10/R12/R20；E1/F3/P1。不改官方评分、盲测原则、金标或计分分母；费用实际记录，unknown不写0，任务调用/并发/超时仍受控。公共合同由主控集成；相关文档与任务卡以R00生效说明同步。

## 兼容性与已有数据

新增表、扩展与索引均增量迁移；旧原文字节/hash保留且可导入MinIO。模型维度/空间/索引版本隔离，绝不把旧非语义向量迁移为真embedding。依赖版本在实际兼容探测后由uv/镜像digest锁定，本单不虚构版本。

## 迁移与验证

先isolated test PG升级/重启/事务；对象先存字节后提交元数据。outbox投影，召回前ACL、命中后PG有效性；图/搜索全量重建、滞后和故障回归。R01验证部署容量；R20备份恢复，R21性能成本。

尚未执行产品迁移/验证，结果须由对应任务报告和真实命令给出；本单不是能力通过证明。

## 回滚与失败恢复

关闭新投影消费者，恢复已备份PG/对象或前向修复，不破坏性downgrade；重新生成投影。PG缺失时not-ready；搜索/图失败显式partial，禁止内存事实或hash向量补成功。

## 批准记录

建设决策：用户已授权。准确落实核验：accepted（独立意见见下方生效记录）。生效依据将在独立审查报告冻结后追加，记录其被审SHA与报告路径，主控不自签。


2026-10-14T22:19:34+08:00：依据独立reviewer /root/r00_independent_review 的 [reports/reviews/recovery/G-A-R00-review-1-recheck.md](../../reports/reviews/recovery/G-A-R00-review-1-recheck.md)，冻结代码15d0272bd2a9e25d19397d8147e9c3cbe6016f9b上的准确落实核验通过并生效。主控仅登记该意见；本单产品实现结果仍按各R卡独立验收，原整T与G-A不自动通过。
