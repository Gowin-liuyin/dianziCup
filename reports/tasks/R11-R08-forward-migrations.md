# R11 / R08 · 0018 / 0019 生产前向迁移

状态：**awaiting_review**；实现 complete，仅指这两项前向迁移与直属验证。记录日期 2026-10-16，作者 `/root/r11_r08_forward_migrations_integration`。未登记 accepted，未修改 progress，未 push。整 R11、R08、T24、T08/T19/T23 和 G-C/G-D 的原验收范围保持。

0018 将已审资产身份、current、不可变快照与幂等收据正式落入 Alembic 链；0019 将已审安全聚合观测落入同一 PostgreSQL。空库与保留旧资料的库均由普通 `run_migrations(..., 'head')` 前向到 0019，未把 metadata 建表当作生产迁移证据。

## 输入、范围与冻结

自 `281371b072a696d972aa3c38519b8646393c98e2` 创建独立 `D:/wt/r11-r08-forward-migrations` / `codex/r11-r08-forward-migrations`。首次命令 cwd 为 D:/dianzi；之后仅在本 WT 修改。按授权 `--no-ff` 合入 R11 材料 `bc8798cf5efc81e210a429884930ca545af43ad8` 与 R08 TTL 材料 `a76374ca9200945441a83421050eceef00db47d8`，merge SHA 分别为 `af83872`、`fbf81f9`。

读取 AGENTS、00_execution_map、恢复 R08/R11、T24/T08、03/05/06、progress/task_state/context_handoff、CR-R11_asset_inventory、CR-R08_aggregate_persistence，以及新版 Ponytail 5.2 full。原 T24 C01–C06、T08 C01–C06、官方范围和阈值未删减。父任务的唯一迁移所有权授权覆盖旧 CR 文本中“由主控冻结”的执行人员限制；未变更其表或业务合同。

两份独立意见仅为限定切片 Ship：

- [R11 首审](D:/wt/r11-inventory-review1/reports/reviews/recovery/G-D-R11-asset-inventory-review-1.md)：206 原回归 + 8 探针；生产迁移未验收，保留 P3 历史查询多读 raw BYTEA 债务及覆盖门限制。
- [R08 TTL 复核](D:/wt/r08-persistence-recheck1/reports/reviews/recovery/G-C-R08-aggregate-persistence-review-1-recheck.md)：90 定向通过；生产迁移、真实 Redis、产品接线未验收。

代码冻结 `c842333fe56a4ab3018a3216a8ddcd6a34639ae1`，tree `6ad70a2699c19341236ae53e82fca030a9f7925b`，2026-10-16T05:16:59+08:00 本地提交。冻结后新建 fresh2/hist2 复跑。源 manifest 对这两份材料的八个 metadata/service/parser/router 源文件逐 Git blob 严格相等；两迁移和四直属测试分别保存 raw SHA256 与 Git blob SHA256。最终材料提交只增加本报告、日志、manifest 和封存 helper；不得改变冻结 source/tests/migrations。

## 改动文件与实现

- `backend/migrations/versions/0018_asset_inventory.py`：parent `0017_enrichment_job_workflows`。三张表精确采用 inventory_models 冻结列/类型/默认值/约束/索引。snapshot→asset、previous→snapshot、receipt→snapshot 与 current→snapshot 均含 asset/tenant 复合键；current FK 与非空提交 constraint trigger 延迟到提交。快照 BEFORE UPDATE/DELETE 明确拒绝，FK 无 cascade。允许同事务先建 asset、再 snapshot、最后 current。
- `backend/migrations/versions/0019_aggregate_observations.py`：parent `0018_asset_inventory`。唯一 `r08_aggregate_observations` 保留 UUID、规范 JSON/hash、call-key、provider/query/version、双时间、outcome/error、mode、fee unknown 与服务器 scope。原 current 排序含 failure 优先表达式和 UUID 确定顺序，UPDATE/DELETE 由数据库拒绝。
- `backend/tests/contract/test_r11_r08_forward_migrations.py`：单 head 与精确 ancestry、禁止业务模块 DDL import / create_all、两条 downgrade 均拒绝历史删除。
- `backend/tests/integration/test_r11_r08_migration_head_regression.py`：原 T24 函数与 API fixture 原样加载，只提供 head0019 的新 inventory_engine fixture。原测试文件未改；其旧 guard 只允许 0016/0018，不能直接拿它在 0019 上收集的 guard error 代替业务验证。
- `backend/tests/integration/test_r11_r08_forward_migration_schema.py`：四表所有列/default/nullable/PK/UQ/FK/check/index 的真实 PG 反射比较；三 trigger 函数体、事件、启用与延期属性比较；旧事实保持和重复 upgrade head。
- `backend/tests/security/test_r11_r08_forward_migration_boundaries.py`：13 个直接 SQL 非法安全字段/check 拒绝与两种聚合 mutation 拒绝。
- 自有 `reports/runs/recovery_r11_r08_forward_migrations_20261016/`：离线环境、CBM、隔离数据库/命令 runner、源码/hash 及原输出封存。没有业务应用、API/worker、角色、锁、settings、0017、公共 schema、阈值、金标、progress 变更。

迁移为独立 `op.create_table/create_foreign_key/create_index` 与固定 SQL，不 import 可变业务表或调用 runtime metadata.create_all。downgrade 明确 RuntimeError，恢复须前向修复或授权备份恢复；未执行任何 downgrade、flush、drop 或旧库修改。

## 实际环境与命令

Windows CPython 3.12.13，本 WT `backend/.venv/Scripts/python.exe`。`C:/Users/yinha/.local/bin/uv.exe sync --frozen --offline --all-extras --no-progress` exit 0，93 包，自有 venv，无锁变化和网络下载。首次 hardlink 不支持警告保留，uv 自动复制成功。

完整命令 argv/cwd/+08 开始结束/exit 见 [commands.jsonl](../runs/recovery_r11_r08_forward_migrations_20261016/commands.jsonl) 和 uv_sync.command.json；下面列主要最终验证，pytest 均保留 `--no-cov -q --junitxml=...`，没有降低原覆盖门。

| 命令/检查 | 实际 +08 窗口 | exit / 数量 |
|---|---|---|
| frozen_prepare：`python prepare_pg.py fresh2 hist2` | 05:17:12.473–05:17:15.974 | 0；两个新真实 PG 库普通 upgrade head |
| pg_frozen_regression：原资产 head harness、原 aggregate PG、新 TTL PG、反射、安全五文件 | 05:17:16.638–05:17:31.951 | 0；100 passed，0 failure/error/skip |
| frozen_pure：R11 inventory unit/contract/security；R08 service/TTL unit/contract/security；新迁移 contract | 05:17:45.268–05:17:48.934 | 0；78 passed，0 failure/error/skip |
| freeze_ruff：两迁移、四直属测试、当时所有自有 helper | 05:16:52.435–05:16:52.754 | 0；全部检查通过 |
| freeze_format：同范围 `ruff format --check` | 05:16:53.630–05:16:53.868 | 0；10 files formatted |
| `mypy src/ai_intel` | 见 mypy_final 收据 | 0；118 source files 无问题 |
| `mypy` 两新迁移 | 05:16:54.494–05:16:55.146 | 0；2 files 无问题 |
| material_ruff / material_format：封存 helper 后 | 05:19:00.111–05:19:00.933 | 0；5 helpers 无问题、格式通过 |
| seal_initial | 05:19:01.454–05:19:04.109 | 0；178 唯一成功 case 与八源 blob 断言通过；最终 raw 再封存见 manifest 时间 |

最终唯一用例数 `100 + 78 = 178`。100 PG 为原资产 46 + 原 aggregate 20 + TTL 10 + 新反射/保留/重放 9 + 新安全 15。早前 76/9/15/78、5 contract green 和冻结后复跑不重复累加；作者或上游 reviewer 的 206/8/90 不算本轮新通过数。FastAPI/Starlette 测试 client 的弃用 warning 保留，无依赖更新。

## 真实 PG 前向和完整反射

只将获准 WSL Ubuntu-22.04/root test-services connection.json 捕获进进程内存，校验 loopback:25432、test_dianzi_ 库及 test_ 用户前缀；DSN/密码未进入 argv/日志/报告，未读 dev DSN、vault 或 holdout。数据库只创建、保留本轮独占名字，最终生产证明为：

| 新库 | 路径 / 结果 |
|---|---|
| `test_dianzi_r11_r08_forward_migrations_20261016_fresh2` | 空库正常 0001→0017→0018→0019；05:17:13.617–05:17:14.817；PG 16.14 |
| `test_dianzi_r11_r08_forward_migrations_20261016_hist2` | 0016 保存合成来源、原文版本、evidence、claim、user、succeeded job、transition、payload、cursor 后前向 0019；05:17:14.819–05:17:15.848；37 张旧表行数/hash 完全保持 |

原始 empty/hist1 成功库、两次准备失败的自有库均保留，没有清理旧数据。首次长 recheck 名曾被 PostgreSQL 截到 63 bytes；最终 helper 增加 63 长度限制，正式证明库名与 current_database 一致。新库 receipt、retained_hist2_before/after 与 JUnit 均可复核。

生产 upgrade 时将 `MetaData.create_all` 替换成失败断言，正常 Alembic 仍成功。反射测试在生产升级完成后，另建 test-only `migration_reference_<id>` schema：仅通过 CreateTable/CreateIndex/AddConstraint 编译冻结 metadata 作为比较方，无 create_all，无 reference trigger，不代表生产迁移方法。四个 production/reflection JSON 同时记录实际与期望，所有类型/列序/默认值/nullable/键/检查/索引相同；current FK 保留 deferrable / initially deferred，全部 FK 保持 NO ACTION。

三个 trigger 的 prosrc 与冻结 metadata DDL 函数体去空白后精确相同，tgtype / tgenabled / tgdeferrable / tginitdeferred 对照通过。原 46 PG 用例在生产 head 实测租户 current/previous/receipt 错配 FK 拒绝、无 snapshot/current 的 commit 拒绝、snapshot UPDATE/DELETE 拒绝、A→B→A 历史、重放不倒退 current、并发线性历史及事务回滚。原 aggregate PG 和 15 新安全用例实测 append-only、不同 payload UUID collision、安全 check 与 UPDATE/DELETE SQLSTATE55000。原 TTL 10 PG 用例以 production head 已提交 UUID/hash 验证 1 秒/半秒/24 小时两时钟边界、fixture cache 隔离与最新失败不复用旧值。

## 失败、未运行与边界

- 改前新 contract red 为 5 failed/0 error/skip：两迁移尚不存在、旧 head0017。后来的 green 不覆盖该日志。
- 新准备 helper 首次 seed 的 SQLAlchemy text 将 JSON `:true` 当 bind，exit2 StatementError；改用 exec_driver_sql。第二次用了 0001 旧列 revision_index，0002 实际已 rename revision_number，exit2 SQLSTATE42703；核实链并修正合成 seed。迁移本体一直可前向；未改既有迁移或 metadata。safe diagnostic helper 的一次 PowerShell -c 转义错误、一次读后再 begin 的 InvalidRequestError 也保留。
- Ruff/format 初次长行、import、lambda、封存 helper 的 unused import 等红字保留，仅修自有新代码/脚本，最终检查通过。没有改原测试期待、原 gold/阈值/计分分母或将失败改 skip。
- 材料首次 staged diff check exit2：自有原字节 JSON/JSONL 的 Windows CRLF 被当 trailing whitespace。原红完整保存 material_diff_red.log/command.json 与旧 manifest；只对本 run 的 JSON/JSONL 增加 cr-at-eol 属性，仍检查 trailing-space/space-before-tab，不改原字节，不为 source 增加忽略规则。
- unit / contract / integration / security 在此迁移切片 passed；frontend / e2e / live / manual **not_run**。完整工程覆盖门、全仓测试、生产部署/恢复演练、真实 Redis IO、主应用资产/聚合接线、供应商/模型/来源外网、真实资产/SBOM/四态/产品真值均不在本轮通过范围。

本轮 provider/model/source 外网调用、付费 API、大模型下载、第三方扫描与 PoC 运行均为 0。安全观测中的 data_mode='live' 是显式合成测试时间边界，注入 fixture connector，不计 live 接通；费用保持 unknown。

## 调用方、材料与偏差

改前官方 WSL CBM 0.11.0 对排除缓存的自有源码副本建图：src 1446 nodes / 7458 edges，明确排除 assets；独立 assets 198 / 823。两个 schema/architecture、实际 qualified name search、InventoryService.import_manifest 与 AggregateService._cache 双向 trace 均 exit0。一次 helper import 重复执行索引留下第二次日志，不伪报图缺边为无 caller。rg/source 补查 service/repository→shared knowledge metadata、inventory router→service 和整个 0001–0017 链；本任务没有接入 app/worker，未推断新入口已在线。

唯一 merge 冲突 `.gitattributes` 只移除标记并保留两侧精确 reports 规则：R07 publication 的 `/**`、`*.log`、`*.xml`、roster_guard_staged.diff、两份 R07 task 报告、combined_fix `/*`；R11 manifest_parser `/**` 与 original_failure_move.stderr.log、fix1 `/**`、added_boundaries_red.stdout.log/.xml、review_38_red.stdout.log/.xml。R08 merge 无冲突。自有 run 的局部 `.gitattributes` 保留本目录 log/xml/json/jsonl 原始字节，并精确将 JSON/JSONL CRLF 行尾识别为换行，同时继续检查真正空格与 tab；没有全局禁用检查或源文件豁免。

没有 schema 重大差异或计划/业务合同变更。`source_manifest.json` 记录 code/tree、两材料/tree、八源 blob、六实现/测试 raw/blob hash 和两独立意见 raw hash；`artifact_manifest.json` 记录自有全部原字节长度/SHA256，并自检。旧红及原 bytes 不改写；最终 material commit 之后应按 Git blob 再由新非作者核验，不能只信作者报告。

评分证据仅为 F2/F3/P2 的资产可追溯历史、权限/幂等与 X1/F2 的安全聚合历史、不丢旧 facts/tasks/cursors。没有准确率、性能、连续时长或完整评分结论。下一建议：父任务冻结本材料后派全新非作者 reviewer 独立验证两迁移、旧数据保持、100 PG 与 78 pure，再据限定意见决定集成；本作者到 awaiting_review 停止，不签整 R11/R08。

未检查 frontend/e2e/live/manual、完整覆盖门和产品接线。迁移有意 forward-only；需要回退时保留历史，采用另行授权的前向修复或备份恢复。
