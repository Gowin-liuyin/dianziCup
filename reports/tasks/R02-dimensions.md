# R02 · 维度尝试与历史持久化

首次创建/本次写作开始/结束/最后更新时间：2026-10-15T11:35:26+08:00。
主控/root；awaiting_review/partial；基底60fe4c311f98a0692e2207b884d83b676f5fb9c2。新源码冻结后记录实际SHA，不能自行accepted；G-A尚未过门/无push。

复用canonical DimensionStatus/FreshnessStatus、PG事件/claims/引文/同Session知识发布收据、scope lock/epoch/change/job/outbox。新增明确DimensionRepository与最小0010前向迁移，必要原因是0009同输入唯一会阻止失败重试的新成功结果；没有再建事实库或通用CRUD。内部输入只引用当前已验证source事实与事件来源引文，支持九维名/七态、逐维历史、同key同payload幂等、不同payload冲突、事件版本fence、租户读写/历史权限。依赖与解释见CR-R04-R02_dimension_publication.md。

真实命令cwd D:/dianzi/backend。11:31:26–11:31:40，在全新test_dianzi_r02_dimensions_20261015库运行完整unit160+PG维度8+旧0009升级1+空/0006升级2，共171passed/0失败/error/skip、cov69.86%。增加真实PG outbox SQL除零故障和非空游标回归后11:33:17–11:33:30，共173passed、0失败/error/skip、cov69.86%，原60门不变，1warning保留；原始命令与XML/log见recovery_r02_minio_20261015/dimensions_pg_outbox_and_cursor.*。outbox失败后当前结果恢复原样、幂等key可重试，旧行时间/值保持未知，新API/worker没有被这些测试假装接通。

纯unit160/cov62.91%此前通过（新增游标后161，须后续单独冻结复跑）；源码mypy58与Ruff/format已实际exit0。首次静态因行长和混用SQL Row/RowMapping局部变量报错，已修为source_row/reference_row/claim_row/job_row并重跑，不用Any/cast/ignore掩盖。unit/contract fixture不计live；本批unit/integration有上述限定范围，contract/security/frontend/e2e/live/manual专门层仍not_run，等待新的非作者复跑。

剩余限制：R03统一job lease执行尚未实现，R04 API/worker实际业务接线未完成，R07九维真实聚合算法/来源和后续变化重判另卡保留。各维真实效果/正式准确率不由此报告宣称通过。MinIO固定候选60fe独立review仍使用其0009专库，本批从未升级它。

本次证据截止：2026-10-15T11:35:26+08:00。
