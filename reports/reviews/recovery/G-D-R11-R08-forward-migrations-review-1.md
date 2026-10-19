# R11 / R08 生产前向迁移独立初审 1

What this change does: 0018 将已审私有资产身份、current、不可变快照和导入收据纳入正式 Alembic 链；0019 将安全聚合观测纳入同一权威 PostgreSQL。两项迁移追加新表和约束，历史事实、游标与任务状态仍由原表负责。

**Verdict: Ship，仅限冻结的 0018 / 0019 生产 DDL 前向迁移。** 本审查未发现需要先修复的新增迁移缺陷。被审切片仍为 awaiting_review；本 reviewer 不登记 accepted，不签整 R11/R08、原 T24/T08/T19/T23 或 G-C/G-D，不认可尚未测量的产品、live、manual 能力。

## 版本、权限与改动范围

新非作者 reviewer `/root/r11_r08_forward_migrations_first_independent_review`。首次从存在的 `D:/dianzi` 执行 `git worktree add -b codex/r11-r08-migrations-review1 D:/wt/r11-r08-migrations-review1 99fec14d1a64f9c5adaa5beb294e804da3e1d18d`，exit 0；随后只在独立 WT 工作。主区已有未提交修改没有触碰。

- 生产代码：`c842333fe56a4ab3018a3216a8ddcd6a34639ae1`；tree `6ad70a2699c19341236ae53e82fca030a9f7925b`。
- 作者材料：`99fec14d1a64f9c5adaa5beb294e804da3e1d18d`。与代码提交间 backend/contracts/fixtures/progress 的 Git diff 为空。
- 0017 兼容依据：`281371b072a696d972aa3c38519b8646393c98e2`；0017、job_models、job_contracts 及原 metadata PG 测试与本材料 Git blob 严格相等。当前 R07 WT 后续未审执行/API WIP 没有用于本次源码判断。
- 读取 AGENTS、00、恢复 R08/R11、T24、03/05/06、task_state、作者报告、CR-R11_asset_inventory、CR-R08_aggregate_persistence 和新版 Ponytail 5.2 review；原验收案例和合同未删改。

本 reviewer 仅新增本报告和 [独立 run](../../runs/recovery_r11_r08_forward_migrations_review1_20261016/)。没有修改业务、生产迁移、原测试、fixture、gold、public schema、依赖、progress、accepted 或 push。费用授权使用 0；没有下载模型、第三方扫描或 PoC 执行。

## 独立资源与真实命令

本 WT 自有 Windows CPython 3.12.13 venv，经 `uv sync --frozen --offline --all-extras --no-progress` 建立。首次成功安装 93 包，但最早日志路径误用 backend cwd，两个 Out-File 捕获失败；开始时间未预先记录，未补造时间。随后同一离线命令经 runner 复核 exit 0，精确时间和该捕获问题保存在 review_summary。硬链接回退复制不是业务测试失败。

DSN 只从获准 WSL `test-services/connection.json` 捕获进内存，检查 loopback:25432、test_dianzi_ 库与 test_ 用户；DSN/密码未进入 argv、报告或工具输出。只创建并保留自己的两个数据库；没有开发 DSN、旧库修改、downgrade、flush、drop 或服务重启。metadata 兼容用例另外保留本库内独立命名 schema，复用原 fixture 每例独立语义，没有清理服务。

完整 argv/cwd/+08 开始结束/exit 见 [commands.jsonl](../../runs/recovery_r11_r08_forward_migrations_review1_20261016/commands.jsonl)，JUnit 和 stdout/stderr 均是新实跑原字节。下表不累计失败后复跑或上游数量。

| 命令组 | 真实 +08 开始—结束 | exit / 实际结果 |
|---|---|---|
| uv_sync_retry：离线 frozen sync | 05:27:15.048—05:27:15.403 | 0 |
| cbm_review：自有 src/assets index/schema/architecture/search/trace | 05:28:10.618—05:29:00.875 | 0；内部 14 条均 exit 0 |
| material_audit_recheck：实际作者 raw 与 Git blob | 05:29:46.953—05:30:04.721 | 0；132 raw、8 upstream source、20 test blob 比较（17 唯一文件） |
| prepare_review_pg：独立空库和历史库 | 05:30:35.158—05:30:40.927 | 0；普通 Alembic 到 head0019 |
| pg_production_regression_resource_fix | 05:31:48.255—05:31:59.500 | 0；100 passed，0 failure/error/skip，测试耗时 9.29s |
| pure_migration_related | 05:33:15.664—05:33:20.147 | 0；78 passed，0 failure/error/skip，测试耗时 2.15s |
| pg_independent_negatives_schema_fix | 05:34:03.077—05:34:34.545 | 0；26 passed，0 failure/error/skip，测试耗时 29.53s |
| ruff_frozen_scope / format_frozen_scope | 05:33:15.610—05:33:16.357 | 0 / 0；两迁移及四直属测试 |
| mypy_migrations / mypy_source | 05:33:16.484—05:33:29.060 | 0 / 0；2 migrations、118 source files |
| ruff_review_helpers_verified2 / format_review_helpers_verified2 | 05:37:02.668—05:37:03.054 | 0 / 0；8 个自有 helper |

100 是原资产 46、原 aggregate 20、TTL 10、四表反射/trigger/保留/重放 9、原新安全 15。资产原函数和 API fixture 经作者 head harness 原样加载；反射只替换数据库姓名 guard 与 artifact 目标，历史保留断言使用本 reviewer 自己的 37 表记录。78 是 R11 inventory 与 R08 service/TTL 的 unit/contract/security 加迁移 contract。26 单列为 19 个原 0017 metadata 行为、1 个无重复 job status/固定 blob 核验、2 个 Python None 兼容负例和 4 个自有负例。26 内同类边界与原回归相关，报告不把这些组或历次运行相加成全系统覆盖数量，也不累加 root 原 20、作者 178、上游 206/8/90。

## 空库、旧数据与迁移入口

[database_receipts](../../runs/recovery_r11_r08_forward_migrations_review1_20261016/database_receipts.json) 记录 PostgreSQL 16.14：

- `test_dianzi_r11r08_review1_20261016_fresh`：05:30:37.755—05:30:39.343，空库普通 0001→0017→0018→0019。
- `test_dianzi_r11r08_review1_20261016_hist`：05:30:39.345—05:30:40.710，普通升级到 0016 后写入真实 PG 合成资料、正文块、revision/evidence/claim/claim_evidence、用户、event、succeeded job、两次 transition、payload、published outbox 与 cursor，再普通 upgrade head0019。

前后独立枚举全部 37 张旧表，按完整行 `to_jsonb` 排序后逐表 hash；[before](../../runs/recovery_r11_r08_forward_migrations_review1_20261016/history_before_0016.json) 与 [after](../../runs/recovery_r11_r08_forward_migrations_review1_20261016/history_after_0019.json) 的行数/hash 完全相同。未把空表略去；非空核心资料、已发布消息、游标代次和 job 历史都有实存数据。此为合成历史保留试验，不冒称来源 live 或备份恢复演练。

准备进程将 `MetaData.create_all` 替换为必定失败断言，两个 upgrade 仍成功。源码核查 `infrastructure/database.py:64`→`alembic.command.upgrade`→`migrations/env.py:36`→`context.run_migrations`；0018/0019 仅 import SQLAlchemy/Alembic，冻结普通 op DDL 与固定 SQL，不 import 可变业务 metadata。两条 downgrade 原函数经 contract 实测 RuntimeError，未调用数据库 downgrade。重复 head 升级的已存快照/聚合行数保持。

## 数据库边界与兼容观测

四表反射比较每列顺序、类型、nullable/default、PK/UQ/FK/check/index。参考 schema 仅在生产升级成功以后用 CreateTable/CreateIndex/AddConstraint 编译冻结 metadata；它不是生产建表入口。所有字段和约束相同，assets 默认 unknown/true，current FK deferrable initially deferred；所有 FK 无 cascade。三条非内部 trigger 的函数体、事件位、启用和延期属性逐项匹配，见 reflection_*_fresh.json 和 100 用例 raw。

0018 真实 PG 验证 snapshot→asset、previous、receipt、current 的 asset/tenant 联合 FK；跨 tenant current/前驱/收据不能写。current 为空的执行阶段允许通过，commit 失败回滚；快照 UPDATE/DELETE 失败；A→B→A 历史、幂等重放不倒退 current、并发线性历史和发布失败事务回滚均经原 46 行为测试通过。0019 单表 append-only，JSON/hash/服务器范围由关闭的 repository 校验；DB 的 schema/provider/query/version/mode/fee/hash 形状和 outcome/error/scope domain 检查通过 15 个真实 SQL 负例，UPDATE/DELETE SQLSTATE55000，fee 始终 unknown。TTL 原 10 用例在生产 head 的已提交 UUID/hash 上验证半秒、1秒、24小时和两时钟，不把合成 live 标签当外网接通。

新增负例的输入、位置、结果如下；都是预期拒绝或失败闭合，没有新增实证缺陷：

| 输入 / 代码位置 | 实测结果与影响 |
|---|---|
| 成功资产 current 临时 NULL→恢复，再另事务只置 NULL；0018:135–145 | 前者 commit 成功；后者执行成功而 commit SQLSTATE23514，原 current 保持。延迟 trigger 检查最终状态，无部分成功。 |
| current 置 NULL 后 SET CONSTRAINTS asset_current_snapshot_required IMMEDIATE；0018:143 | 立即 SQLSTATE23514；事务回滚。 |
| 从合法快照复制，改 snapshot_id/number、canonical_payload=None；0018:82–84 | SQLAlchemy 绑定 JSON null；ck_snapshot_payload / 23514 拒绝，未插入伪快照。 |
| 合法 aggregate JSON、64hex 但不匹配 payload hash，另 UUID 与更晚 recorded_at；repository:124–160 / 0019:54–57 | DB 只承担冻结的 hash 形状约束，允许直接合成 SQL；权威 read_latest 拒绝为 aggregate storage integrity failed，未输出篡改 value。没有把 DB 形状校验冒充完整 JSON/哈希核验。 |
| 0017 原 metadata 的 input_context=None / result_payload=None；job_models:43/98，0017:94–101/171–178 | 两者绑定 JSON null，不是 SQL NULL；原完整组合 Check 均 SQLSTATE23514 拒绝，原字段仍 SQL NULL。18 个原非法组合与独立 reservation 行锁行为保持。 |

根据原 root0017 [freeze receipt](../../runs/recovery_r11_r08_forward_migrations_review1_20261016/reference_root0017_freeze_workflow_contract_receipt.json)，其原 20 PG / 32.43s 只作为历史辅助；本次自己复验并未读取 root 后续未审执行代码。0017 此处证明 metadata/SQLCHECK 与前向链兼容，不证明 R07 workflow 执行、API、Celery 注册或真实模型。

## 调用方、类型、负载与复杂度

官方 WSL CBM 0.11.0 对自己 WT 的排除缓存源码副本独立建图：src 1446 nodes/7458 edges，明确排除 assets；另 assets 198/823。两份 index/schema/architecture、四个 actual qualified-name search 和 inventory import、aggregate save/collect、run_migrations 双向 trace 全部保留。图未解析 factory/lambda/Protocol 的所有调用边，import/save/run 的 callers=0 不是无调用依据；[源码 rg](../../runs/recovery_r11_r08_forward_migrations_review1_20261016/caller_source_scan.stdout.log) 回查所有 src/tests/scripts/migrations。

已读 inventory_routes:76–93 的短事务、认证锁，以及 :171/:220 两个 import 调用；InventoryService 使用调用者 Session，current/receipt/change/job/outbox 同事务。aggregate_service:356 是 save 调用方，网络收集结束后 repository 才开短事务；repository 使用单表，与旧 job/fact 状态不重复。本批没有 app/worker 接线，不能从独立 TestClient 通过推导产品在线。

类型实跑无错误。负载判断按 repo 的多租户、多个 worker 与有界分页/导入；新 DDL 的索引只建在新空表，没有在既有 37 张有数据的表上新增昂贵索引或回填。current trigger 以 PK 查询最终行；私有 FK 和事务并发经原测试验证。未做生产规模、QPS、p95 或长时间基准，不能用上述秒数当性能验收。

迁移有意重复冻结少量 metadata DDL，避免历史迁移随业务 import 漂移；249 行 DDL 没有通用 BaseService、额外依赖或动态 SQL 配置。参考 schema 和 guard harness 仅用于测试，没有进入运行时。未发现可删除且影响本迁移评审的复杂度。

既有非阻断债务仍保持：inventory.py:417 历史分页选择完整 snapshot，其中 private raw BYTEA 最高 1MiB，却只用 canonical_payload 构造响应。上游独立输入为 1MiB 合成清单，观测 SQL 取 raw 而响应仅 869 bytes；最小修复只投影 snapshot_number/canonical_payload。此代码与上游 blob 相同，本次没有修改或重新计该性能探针；修复及投影复验 not_run，后续重跑 current/history/pagination/raw 不泄露。它不是新增 DDL 阻断项。

## 红字、材料封存与未检查

所有原失败没有改成 skip 或业务 green：

- 自有首 production regression 的 run_id 漏 `_fresh`，隔离 guard 给 91 setup errors，9 反射 passed；只修自己 runner 环境后 100 passed，旧 XML/raw 保留。
- 自有首单 reports 负例缺少原 conftest plugin，26 setup errors；加 `-p tests.conftest -c pyproject.toml` 后原 metadata seeded_event 共用 public schema导致 20 failure/6 passed。核对原 catalog fixture 每例新 schema，恢复资源隔离后 26 passed；原断言字节未改，未将 20 个 seed 失败登记为迁移缺陷或通过。
- 自有首次材料核验把 reviewer checkout 当作者原 bytes，8 个默认 text 文件被 Git LF→CRLF 展开，其中 attributes 为作者/blob169、checkout173 bytes。改为分别核作者实际 WT raw、Git blob 与 reviewer checkout后 132 全部严格匹配原 manifest；三份长度/hash各存。未改任何作者文件或期待 checksum。
- 作者原 StatementError `:true`、42703 `revision_index`→`revision_number` 的 seed red、5 contract red、ruff/format red 和 material_diff_red 都在其 132 raw 中核验保留。它们是 bootstrap/代码生成历史，不是本版本业务 green。自有 helper lint/format red 也留存；只修自有 helper，最终通过。

作者 raw manifest 本体实际 SHA256 **7a3adc9c434122f2e979eeb0b967eff9b5fe3f98a1db90c6c205f29f37b877ad**；132 条作者 raw 大小/hash 及 Git blob 全相同。8 upstream source 对 bc8798/a76374 材料逐 blob 核验；20 次原 test 比较涉及 17 唯一文件。281→material 的 conftest/contracts/fixtures/progress diff 为空，没有 gold/阈值/分母改动。作者局部 attributes 只对其 JSON/JSONL 识别 cr-at-eol，仍检查真实 trailing-space/space-before-tab；原 diff red 字节不动。自己的 attributes 仅覆盖本 run 的 log/xml/json/jsonl，没有源码豁免或全局规则。

[material_audit](../../runs/recovery_r11_r08_forward_migrations_review1_20261016/material_audit.json) 与 [review_summary](../../runs/recovery_r11_r08_forward_migrations_review1_20261016/review_summary.json) 记录来源、全部 hash、原红、计数、图和秘密精确匹配检查；实际配置的 DSN/password 未匹配任何自有 artifact。自己的 [raw manifest](../../runs/recovery_r11_r08_forward_migrations_review1_20261016/artifact_manifest.json) 与 [freeze receipt](../../runs/recovery_r11_r08_forward_migrations_review1_20261016/freeze_receipt.json) 冻结 raw 长度/hash 和本报告 hash，manifest/receipt 排除自引用。

unit/contract/integration/security 在上述限定切片 passed；frontend/e2e/live/manual、全仓覆盖门、备份恢复/生产部署、真实 Redis IO/TLS、产品资产/聚合接线、SBOM、四态/证据包/OpenVEX、3→5 产品真值、来源/模型/供应商真实外网和持续运行均 **not_run**。本次 source/provider/model 外网请求为 0；合成 fixture 不计 live，观测费用 unknown 保留。没有准确率、性能达标或全系统完成结论。

评分项证据只增加 F2/F3/P2 的授权资产历史和事务边界、F2/X1 的安全聚合历史及 E1 的可复跑前向 DDL。下一建议：主控可据固定 SHA 和本次 raw 证据集成限定生产 DDL；另开边界清晰的产品/API/worker 批次，再派新非作者审查，继续保留原阶段与 live/manual 门。

Not checked: 整 R11/R08、R07 执行/API/Celery、阶段检查点、frontend/e2e/live/manual、覆盖门、生产规模性能和恢复演练。
