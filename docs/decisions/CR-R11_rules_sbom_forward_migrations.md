# CR-R11 · 规则、评估与 SBOM sidecar 的生产前向迁移

创建/开始写作：2026-10-16T07:18:20+08:00。作者：R11 前向迁移集成人；状态 `awaiting_review`，独立审查待主控安排。

依据：主控明确指定编号与范围、已限定 Ship 的规则/评估源码 `2ddc8fe2ff3e7becfad3b1774a10407911eacbe6` / 材料 `6b10f2c4ed013f4375d51fc31e1cb317409730ac`，以及主控冻结的 [SBOM sidecar seam](CR-R11_sbom_sidecar_table.md)。起点为 `ed0e14a03a06ed104f23afd0be5407d873ed8edf`，沿用 [0020 生产迁移合同](CR-R12_production_hybrid_migration.md)。0020 的独立审查仍是本切片最终前置门；本变更不签整 R11、T24/T27/T28 或 G-D。

原行为：规则/评估只有六张 metadata 表提案，作者的局部建表只证明内部服务行为；SBOM sidecar 同样只有 metadata。普通生产 Alembic head0020 尚不创建这些表。

新行为：普通正向链 `0020_hybrid_retrieval → 0021_condition_assessments → 0022_sbom_sidecars` 创建七张表。0021 完整冻结六表列、类型、nullable、PK、既有 FK、唯一键、check、两个索引、两函数和六个 trigger；`uq_current_published_rule_family` 仍只约束 `status='published'`。0022 完整冻结 sidecar 的 snapshot 主键与 `(asset_id,tenant_id,snapshot_id)` 主快照复合 FK、版本与租户长度、两个小写 hex hash、JSON object 和 UPDATE/DELETE trigger。冻结的静态 PostgreSQL SQL 由 Alembic `op.execute` 执行，不在生产迁移导入业务 metadata 或随未来模块变化重新编译 DDL。

不改既有 metadata、业务算法、权限、生命周期、rule family identity、来源 roster、原文核验、完整 epoch map、snapshot 判等与 hash 计算。未新增跨权威 FK；复杂父绑定与权限仍由原服务在 PG 锁和原文核验下验证。当前六表中未声明的 JSON shape/check 不擅自加强。本切片只增加正式迁移，未接 SBOM importer、默认 API、worker、OpenVEX 或 T36 调度。

兼容：不回填、不解析、不改写任何旧行。JSON/CSV 资产历史、raw bytes、projection hash、原检索/vector 空间、源文档版本与收据保持原值。新迁移不自动初始化用户运行库；部署仍由已授权运维显式执行正常 forward upgrade。生产代码没有新增 `create_all` 路径。

回滚：七表承载不可变历史，`downgrade()` 显式拒绝删除；先关闭新增写入并保留读兼容，必要时走批准的前向修复。隔离 PG 验证在同一真实事务中执行0021/0022 DDL和 Alembic revision stamp，再注入失败：新表、函数、trigger 与版本一起回滚到0020，全部旧行逐字保持。未执行 destructive downgrade。

验证：空 schema 正向到0022；已填0019与0020逐20→21→22，所有旧表排序 raw row JSON/count/SHA256 对比及重启重复 head；七表反射；每张历史表实际 UPDATE/DELETE 拒绝；FK、scope/type/hash/JSON 负例；sidecar 同键两线程只有一行；不可变输出事务失败无部分结果。原 R11 33+fix15 与 R12 22 行为函数及断言原样导入新 wrapper，只替换自有资源、schema、生产 head fixture，不修改原文件或期待值。实际数目与原红、静态检查和资源记录见 [任务报告](../../reports/tasks/R11-forward-rules-sbom.md)。

资源：仅自有 `test_dianzi_r11_forward_rules_sbom_20261016`、随机 `test_r11_forward_` schema（上限80），loopback25432、test_用户；search 只创建/清理 `dianzi_test_r11_forward_` 临时索引。凭据来自明确授权的私有 DPAPI，pwsh7 stdout 只由内存子进程 capture解析；密码不进 argv、报告、日志或提示。不操作来源运行库的业务表、Redis15、既有 OpenSearch 索引、宿主 ACL 或系统库；0付费 API/外部来源/第三方扫描。frontend/e2e/live/manual 均 `not_run`。

本记录是已授权内部冻结的实现说明，不修改公共合同、官方评分、gold/holdout、分母或阈值。生产切片仅 `awaiting_review`，完整产品与人工/外部实测缺口保持。
