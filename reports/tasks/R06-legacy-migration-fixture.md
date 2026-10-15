# R06 legacy migration fixture repair

任务状态：`awaiting_review`；限定实现：`complete`。unit/contract：`passed`（限定纯回归）；integration：`passed`（原 35 项及种子完整性）；live/manual：`not_run`。不登记整张 R06/R05 或阶段验收，不修改 progress，不 push。

## 范围与根因

基线 `7b8103e6d91a7274bcfb661d8e6f1d5b7180be17`，独立分支 `codex/r06-legacy-migration-fixture`，工作树 `D:/wt/r06-legacy-migration-fixture`。代码冻结为 `412b0bf3662d1d2990f2993f6d2838f8737b49ea`（前两实现提交 `b58e1087e3653aabb46221c23fba344c8207288f`、`5c6a0e579f6984baa7916b0386966bcd951cc0cb`）。最终报告/日志提交只追加证据。

原夹具将新 UUID schema 迁移到 `0013_revision_source_metadata`，随后调用当前 `persist_source_response`。当前 `EventRepository.publish_events` 的全行 SELECT 包含仅在 0015 新增的 `source_metadata`，使升级前建数阶段失败。`red_one.log/xml/json` 记录单个原失败：1 setup error、退出 1，未将环境错误或业务错误改成 skip。原 writer → revisions → event publication → knowledge publication 的真实链由独立 src-only CBM 0.11 索引、trace 及 `rg` 定位确认；产品代码不应为测试种子支持旧 schema 而扩大兼容补丁。

本轮只修改 `backend/tests/integration/test_r05_vector_persistence.py`、新增 `fixtures/recorded/r05_legacy_0013_vllm_public_v1.json`，以及本报告和自有运行目录。未修改产品 `backend/src`、迁移、合同、锁文件、认证、金标、评分、用户数据。`test_r05_question_api_pg.py` Git blob 不变，原 vector 文件所有 `test_*` 函数 AST 不变。

## 真实旧种子与完整性

种子由已审 `1927eeb00a7e0c1335f76340b0382f46102f08f2` 代码、其旧 Python 解释器 `D:/wt/gb-stage-final/backend/.venv/Scripts/python.exe`，在全新 `test_r05_legacy_export_<UUID>` schema 上先迁移到真实 0013，再执行原来的管理员 `SourceResponse` 生成。输入仅原仓库 `fixtures/recorded/vllm_vendor_20261015_public.json` 第 0 条；响应仍为 `json.dumps([record]).encode()`、原 GitHub 固定 endpoint、观察/入库时刻 `2026-10-15T08:00:00+00:00`。

- 来源文件 SHA256：`f084ddcb1eecd43494ac0244dd3b650431727add18deb330bc3df1722912cedf`。
- 原响应 body SHA256：`ed8547c71c74f9fe73edef9de024dd8603d76ae1f80b9c8afff53b3aaa874ba9`。
- 原 writer 文件 SHA256：`b688f3eb1393c9bb0914980f75578b55c024ab58bd3cf57b3b18f89b78109f8a`；完整旧模块 import 路径/hash 见 `artifact_manifest.json`，均来自旧 worktree。
- 冻结种子 Windows CRLF 原文件 SHA256：`172738559f16571d1854f302708633f48178b38fae854d3d782fad775b267fc4`；Git blob/规范 LF SHA256（加载器固定校验）：`6170ce55e63a70a557f62fc79213d20b596222220e2a04d5e050e67b7e188336`。约 121 KiB，含版本/fixture 标记/源 hash/required tables/实际 UTF-8 ContentStore payload。仅将 JSON 文件自身物理 CRLF 转为 LF 做文件校验；内嵌原文 payload 的转义换行与内容 hash 完全不改，LF/CRLF 双路径 self-check 均通过。
- ContentStore 实际对象 hash 为 `b0571da15760e3d42c130f3b9662ff4afebfdddd973aaf0b8c696aaecd25910b`、`ed8547c71c74f9fe73edef9de024dd8603d76ae1f80b9c8afff53b3aaa874ba9`，加载时逐个核对内容/hash/字节数并实际写入临时 ContentStore、读回验证。

19 个非空表共 154 行：sources 1、content_objects 2、documents 1、document_revisions 1、text_blocks 126、evidence 2、events 1、event_external_ids 1、event_documents 1、claims 2、claim_assertions 2、claim_evidence 2、claim_status_history 2、scope_epochs 1、change_events 2、job_runs 2、outbox_events 2、publication_receipts 2、fetch_attempts 1。jobs/outbox 是旧知识发布器生成的合成任务链；未导出或载入 users/auth/session/secret 表，也未读取 holdout。首次导出漏选 publication_receipts 的必需 FK 业务表 job_runs，在加载实现之前发现并重新完整导出；两次导出日志均保留，最终 seed 使用后一份固定 hash。

加载器先验证 schema 位于 `test_r05_` 命名空间、seed SHA、来源/响应 SHA、固定版本与表集合，再检查当前自有 schema/version。仅反射迁移后自有 0013 表，不使用当前全行 ORM；精确核对列集合、行键、非空/空目标表、public/tenant 范围、带时区时间。所有 DateTime 由 ISO 值解析为 aware UTC。`claim_status_history.transition_sequence` 为 GENERATED ALWAYS：让数据库在新 schema 生成 1/2，RETURNING 与旧 seed 序号逐一相同；不禁用约束、不修改序列或公共数据。

原前向路径仍是 **全新 schema → 0013 → 非空旧种子 → head/0015**。升级前后除原非空 evidence ID/hash 对比外，还比较全部 19 表的全部旧列及 154 行完全一致。旧 source_metadata 升级为 `{}`，vector 实际版本 `0.8.2`；原 35 业务断言继续执行。生成种子需要旧代码仅用于本次 provenance；日常测试只依赖已冻结 JSON、当前迁移和当前测试文件，可在无旧 worktree 的干净环境运行。

## 隔离与调用方影响

专库仅 `test_dianzi_r05_pgvector_20261015`，凭据从已授权 WSL connection.json 读取到进程环境，`DIANZI_TEST_RUN_ID=r05_pgvector_20261015`；日志不输出 DSN/口令。migration URL 为 schema-only，runtime URL 才包含自有 schema,public。原 `alembic_version` 的 pg_namespace 所属检查保留；反射与 INSERT 明确限定自有 schema。所有执行均记录 public 表 counts 和 public version 前后相等，未清理此前 reviewer 写入的 public 记录，未依赖其版本/表建数。

调用方仅 `vector_database` 及 question 测试对它的既有导入；无产品接口变化。新产品能力仍必须迁移 0015，本修复没有允许产品在 0013 上运行。原合成向量/生成 wire 仍标 fixture，不计语义检索、真实模型、准确率或 live 来源证据。

## 实际命令与结果

命令在 `D:/wt/r06-legacy-migration-fixture/backend` 执行；检查 Python 为 `D:/wt/r06-integration/backend/.venv/Scripts/python.exe`，通过显式 `PYTHONPATH=D:/wt/r06-legacy-migration-fixture/backend/src` 使用本 worktree 源码。下列命令由 `../reports/runs/recovery_r06_legacy_migration_fixture_20261015/run_check.py` 封存每次 argv/cwd/开始结束时间/退出码/code SHA/public 前后快照；后期还记录候选文件 SHA256。精确可复跑 argv 以同名 `.json` 为准，不包含秘密。

| 日志名 | 实际核心命令 | 退出/结果 |
|---|---|---|
| red_one | `python -m pytest tests/integration/test_r05_vector_persistence.py::test_upgrade_preserves_immutable_evidence_and_real_extension --no-cov -q --tb=short --junitxml=.../red_one.xml` | 1；1 setup error，UndefinedColumn |
| export_0013_final | 旧 Python 执行自有 `export_0013_seed.py` | 0；真实旧 0013 种子，19 表、2 个内容对象 |
| green_one | 同单测试，加载器首次实现 | 1；GeneratedAlways，红日志保留 |
| green_one_identity | 同单测试，identity 精确核对后 | 0；1 passed |
| original_35 | `python -m pytest tests/integration/test_r05_vector_persistence.py tests/integration/test_r05_question_api_pg.py --no-cov -q --tb=short --junitxml=.../original_35.xml` | 0；35 passed，45.19s |
| original_35_frozen | 相同原 35 命令，代码 b58e108 冻结复跑 | 0；35 passed，41.39s |
| original_35_final | 相同原 35 命令，代码 5c6a0e5 冻结复跑 | 0；35 passed，46.45s |
| original_35_portable | 相同原 35 命令，最终代码 412b0bf 冻结复跑 | 0；35 passed，46.00s |
| pure_regression | `python -m pytest tests/unit tests/contract -m 'not real_pg' --no-cov -q --tb=short --junitxml=.../pure_regression.xml` | 0；1256 passed、1 deselected，38.81s |
| constraints_portable | `python .../seed_constraints.py` | 0；13 个明确 self-check，通过原函数/文件不变、坐标/hash、LF/CRLF、tamper/表/列/来源拒绝、public/非空旧 schema/head 拒绝、全表保留 |
| ruff / format | `python -m ruff check tests/integration/test_r05_vector_persistence.py`；`python -m ruff format --check ...` | 0；目标文件通过 |
| mypy | `python -m mypy src` | 0；85 source files 无问题 |
| static_portable_pass / format_portable_pass | `python -m ruff check --config pyproject.toml tests/integration/test_r05_vector_persistence.py ../reports/runs/recovery_r06_legacy_migration_fixture_20261015`；同范围 format --check | 0；代码和证据脚本通过 |
| seal_portable | `python .../seal_evidence.py` | 0；候选范围/文件 hash、旧 import 链、实际口令/DSN 未进入 artifacts、全部 public guard 通过 |

首次约束脚本 Windows 子进程 UTF-8 解码失败及 CRLF/Git blob 比较失败分别保留 `constraints`、`constraints_recheck` 红日志，修正脚本后真实通过。证据脚本 lint/format 的初始长行、动态导入和工作目录影响 import 分类等红日志也全部保留；未用测试 skip 或降低检查解决。pytest 保留既有 Starlette/httpx deprecation warning。未增加依赖或修改锁文件。

`git diff 7b8103e6d91a7274bcfb661d8e6f1d5b7180be17 HEAD --check -- backend/tests/integration/test_r05_vector_persistence.py fixtures/recorded/r05_legacy_0013_vllm_public_v1.json` 退出 0。全部新增证据的 `git diff --cached --check` 退出 1：原红例 `red_one.log` 第 48/49 行及 `red_one.xml` 第 45/46 行保留 SQLAlchemy 原始 SQL 渲染的行尾空格，共 4 处；没有修改失败日志或扩大忽略规则以隐藏这项证据格式限制，产品/测试代码 diff 无空白错误。

## 计划偏差、评分证据与交接

这是 R06 变更触发的 R05 历史升级回归夹具修复，属于本轮授权的小范围测试边界，不改变冻结合同、评分/分母/金标。证据支持 E1 工程前向迁移、不可变原文/证据与隔离 PG 回归；不增加 F1/P1 来源覆盖、性能或 live 得分。当前实现/自动检查完成，交独立 reviewer 审查后才能改变验收状态。建议 root 在当前产品候选上组合本分支的三个测试代码提交，并由新的独立 reviewer 复核精确 test/seed diff 与原 35 路径。后续产品采集、真实来源/模型、完整 R06/R09/R17 验收不在本子任务范围。

运行证据目录：`reports/runs/recovery_r06_legacy_migration_fixture_20261015/`。基线到代码冻结 diff 只有上述 test 与版本化 seed；`artifact_manifest.json` 给出精确候选 hash。报告、日志与自检脚本独立提交，便于 reviewer 审阅测试改动。
