# R20 · PostgreSQL 与原文对象隔离恢复

本入口用于受控、带所有权标记的本地测试数据库演练。`scripts/backup_restore.py` 提供可信离线 Python 操作接口；它不接受产品请求体、模型生成的 SQL、shell 或任意 URL。整体 R20/T50 的故障注入、索引服务、研判及最终部署验收仍分别保留。

## 范围与前置

PostgreSQL 仍是事实、应用认证、历史、任务与 outbox 的唯一权威。备份包含整个专库的 schema、约束、函数、应用记录及所有 `content_objects` 登记的原文字节，包括历史修订所引用的对象。模型、搜索服务、Redis、Neo4j、Celery 结果和 LangGraph 检查点不作为事实备份来源。

原文读取复用 `ContentStorage.read_verified`，支持已配置的本地/MinIO 适配器；备份中的对象和恢复目录使用现有内容寻址 `ContentStore`。本次真实演练只验证本地原文目录。生产 MinIO 账户、独立配置文件和外置提示词文件未在本轮授权范围内；PG 中的规则/配置记录随库保存，代码中的提示词由 Git 版本固定。环境秘密不进入归档。

操作前必须有：来自认证服务的 system_admin `AccessScope`、可信进程环境中的连接秘密、受控 PostgreSQL 客户端目录、明确测试数据库、已观察并登记的 DB OID/COMMENT 与 source schema OID/COMMENT、专属临时目录、原文存储实例和当前代码 SHA。路径必须绝对、位于 `.rehearsal-owner` 标记的独立目录下；拒绝任何 symlink/junction、路径回退及 Git checkout 内路径。标记文本为同一次演练的 `dianzi-rehearsal:<run_id>`，数据库和 source schema 的 COMMENT 必须精确一致。

仅名字以 `test_` 开头不足以授权。入口核验可信 URL 的 host/port/name、实际服务器端口、数据库 OID 与 COMMENT 和 schema OID/COMMENT；host 仅允许 loopback。source 仅允许专属 schema 与无业务表的 public。target 必须只有空 public，且不得存在关系、函数、自定义类型、额外 extension 或 event trigger。

## 备份

调用 `create_backup(engine, source_target, authenticated_scope, content_storage, source_tools, owned_root, backup_directory, code_sha)`。数据库使用 `NullPool` 并设置连接、SQL 和锁等待期限；`NativePgTools` 从可信客户端目录仅选择 `pg_dump`/`pg_restore`，连接秘密只进入其子进程环境，不放入 argv 或日志。

入口先开启 REPEATABLE READ，取得 PostgreSQL 导出快照；同快照保存全表行数和排序后的行摘要，`pg_dump --format=custom --snapshot=...` 读取相同快照。整个导出期间对 `content_objects` 持有 SHARE 锁，阻止登记被删除后原文对象被并发回收。每个对象同时校验数据库记录的字节数与 SHA256。

`manifest.json` 最后写入，包含范围、开始/结束、PG 版本、schema revision、代码 SHA、dump SHA256、表计数/摘要和内容 hash/字节数。返回的 manifest SHA256 必须单独固定在可信回执中；只修改 manifest 内的 hash 不能绕过检查。元数据和备份正文都属于内部制品，真实用户/资产内容不得提交 Git。

任何失败会留下 `FAILED` 标记并抛出脱敏错误。残缺目录不得重用或视为成功。入口不会覆盖已经存在的备份目录。

## 空库恢复

可信资源控制器先创建独立空测试库并登记其精确 OID/COMMENT；恢复入口不会创建、drop、clean 或 downgrade 数据库。源库与目标库必须不同，原文目标必须是新的专属目录。

调用 `restore_backup(target_engine, empty_target, authenticated_scope, target_tools, owned_root, backup_directory, fresh_content_directory, pinned_manifest_sha256, rebuild_indexes)`。完整性核验先于恢复：固定 manifest pin、精确文件集合、dump hash、全部对象 hash/大小；拒绝多余 partial 文件、缺失文件和链接。

恢复持有目标数据库的事务 advisory 锁，拒绝另一合作实例同时恢复；核对空库后才创建内容目录。该锁不阻止不遵循本入口的客户端写入，资源控制器必须保证专库独占。入口在 pg_restore 前重复核验空库，工具结束后再次核对 DB/schema identity 与准确行摘要；它不宣称 advisory 锁提供生产级写入隔离。原文先校验复制，PG 使用 `pg_restore --dbname=<test_name> --single-transaction --exit-on-error --no-owner --no-acl`。随后核对所有恢复表的行数/摘要，包括要求为空的派生表。SQL 数据库拥有者与 grants 不随恢复复制；应用租户权限、用户密码 hash 与会话记录随 PG 事实保存，因此此入口不构成生产迁移/授权替换。

成功完成事实和对象核验会得到 `database=verified`、`content=verified`。这两个值不代表搜索已经恢复。`retrieval_chunks` 和四张 `hybrid_*` 派生表保留 schema、排除数据；搜索索引必须由现有索引运行时从已恢复的有效事实重建。调用方应传入现有索引器的可信、有界重建操作，权限与版本校验继续由该索引器执行。缺少重建操作返回 `indexes=rebuild_required`，重建抛错则写 `indexes=failed` 并抛错；只在回调成功后登记 `rebuilt`。本轮未连接搜索/真实语义模型，实际回执为 `rebuild_required`。

失败回执是独立 `<content_directory>.restore.json`，保留已取得的核验状态，未验证部分为 `incomplete`。入口拒绝覆盖既有内容目录和回执。PG 工具失败时由单事务避免其部分 SQL 生效；后验不符或索引失败时隔离已恢复内容，先读回执再人工升级，不回报健康、不放宽权限、不删除历史来修复。

## 本次复现入口

在 Windows 独立工作树执行：

```powershell
& D:/dianzi/backend/.venv/Scripts/python.exe reports/runs/recovery_reviewed_integration_20261016/check_backup_batch12.py
```

上述主控命令仅运行 32 个离线单元及静态检查，不连接数据库。原作者的旧 `checks.py` 不随本次集成采用；其外层资源审计不足不能用作新运行放行。PG 用例在 `backend/tests/integration/test_r20_backup_restore_pg.py`，`process_metadata.py` 与 `restart_read.py` 两个冻结 Windows 测试依赖已随集成恢复。实际 PG 必须由主控分配资源窗口，并用已核控制器内存注入当前授权连接、校验父资源和每 case 的新库 OID/COMMENT/nonce，再执行用例；未配置控制器不能直接执行本文件中的 PG 测试。

独立审查冻结提交 `ab04855085f828548222443c31020852f7ca2970` 的最终控制器与 2 项真实 PG 结果在其 `reports/runs/recovery_r20_backup_restore_review1_20261016/`，不是 Root 本批重新执行的结果。每 case 创建两座精确新专库、专属 source schema，前向迁移到实际代码 head；测试专用工厂使用 `NullPool`，不修改迁移源码。固定 Docker adapter 使用既有官方 portable Docker、socket/config 和父 PG16 容器真实客户端；本机 NativePgTools、MinIO 和索引重建仍需单独实测。

备份/恢复正文存于 `D:/dianzi-private/r20-backup-rehearsal/<owned_run>`，验收后仅在 OID/COMMENT、连接数与目录 marker 再次核验后清除本次自有资源。harness 单窗 240 秒、Windows 进程树上限 10，记录 launcher/child/WSL shim birth、Linux Docker/工具 PID 与 `/proc` birth ticks。没有启动新监听器或停止父服务。

测试使用真实 PostgreSQL 与真实原文文件系统，业务输入显式为合成。断言覆盖已认证租户会话、两个历史版本、证据引用、retry_wait/error_code、内容 hash 和新应用进程再次读取；OS/PG 服务重启、浏览器/前端、真实模型、真实来源、索引重建与完整研判均未在本包实测。查看本次任务报告及每条命令日志，再由非作者复跑评审。
