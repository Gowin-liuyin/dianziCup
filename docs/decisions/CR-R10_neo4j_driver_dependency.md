# CR-R10 · 官方 Neo4j Python driver 锁定

文档首次创建时间：2026-10-16T07:49:23+08:00
本次写作开始时间：2026-10-16T07:49:23+08:00
本次写作结束时间：2026-10-16T07:49:26+08:00
最后更新时间：2026-10-16T07:49:26+08:00
状态：批准建设目标内的必要依赖 checkpoint；生产投影/整卡/阶段未验收。
主控：/root。基线：3baeb8809d3950a091e8db114be7a28049b74b36。

R10/R12 已批准图派生索引需要真实 Bolt 事务；复用官方 driver，避免自写 Bolt 协议、连接池、事务或重试框架。固定 neo4j==6.4.0，新增其传递依赖 pytz==2026.5；原 95 个包版本未改变，锁文件共 97 个包。项目 Python 3.12 在官方支持范围。

官方元数据与 wheel 校验依据：[PyPI 6.4.0](https://pypi.org/project/neo4j/6.4.0/)，wheel SHA256 fdd048ba827be138063b045cf59e40056fbf0405ac02dadc24f64e369fbd9d3d。该版本页面许可证为 Apache-2.0 AND Python-2.0；最终第三方许可证目录必须保留。存在较新 6.4.1 不代表本次已测试版本，不能将其兼容性套用本锁。

修改仅 pyproject.toml/uv.lock 与本变更单，不改公共评分/八对象/原验收。原 approved 基础设施目标不需新的用户审批。R10 投影 adapter 会使用固定参数 Cypher，PG 为事实/权限/任务权威；driver 与测试 server telemetry 均关闭，由 owned-runtime 实测证据核对。不能把 driver 导入成功称为产品图接通。

兼容性：官方 driver 配置保持独立；已有 PG/API/Celery 返回值与认证合同不变。测试 Community5.26.32 已独立 owner 实际认证返回 Bolt5.8；具体运行、安全负例与版本证据仍待新独立 reviewer，本变更单不代签。当前测试 tini TERM 转发因缺KILL失败，exact Docker stop 已发生但 graceful shutdown 未通过，另记 runtime 问题不掩盖。

迁移：本依赖无需数据库 migration。后续 PG 投影表为独立前向0025，由主控所有；不得用 Neo4j 另建事实真相。回滚：先关闭新 graph_apply/default projection wiring，再回退这三个依赖 checkpoint 文件并 uv sync --locked；保留 PG 历史与派生测试卷，不 destructive downgrade、不删 volume。已发布后的依赖撤除需查所有 import 与 worker 配置再审。

验证：本脚本实际执行 uv sync --locked，exit0；离线构造 driver telemetry_disabled=True 不发网络，已记录 smoke JSON。实际 auth/Bolt/transaction 用例在 R10 owned-runtime/作者包中，不合并为 live 来源证据。原 uv add 命令发生在此前工具输出中，其逐秒起止未单独落盘，写历史未记录；不根据mtime推算。本次命令的起止与退出在 neo4j_dependency_commit_receipt.json；新增下载费用 unknown，不写0。

任务与测试影响：R10 真实 projection 与恢复/并发负例；R12 多跳可选派生候选仍须回 PG ACL；R20 资源恢复与租户隔离。初审冻结将核本 CR/锁/hash、原包版本不变、真实资源与负例，不签整个 R10/G-C。没有改变金标、分母、阈值或授权资产。
