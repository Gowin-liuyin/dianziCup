# G-C · R07 core 初审三项修复独立定向复核 v2

独立意见：`Ship`，仅限固定提交上内部九维候选与 typed Claim v3 账本基础片的三项 Must 修复。未发现本范围新增的 Must/Should/Nice finding；不签整 R07、T13/T19/T20/T22/T23/T41 或 G-C accepted，主控按限定意见登记。

首次创建/写作开始：2026-10-16T00:36:45+08:00；写作结束/最后更新时间：2026-10-16T00:36:45+08:00。时区 Asia/Shanghai，秒级命令起止见下表及 receipts。独立 reviewer：`/root/r07_core_fix_independent_recheck_v2`，未参与被审实现。

固定代码：`ce1da8811495f1ea1de538c67cb12b16e6d8a280`；完整冻结：`cb34097898b412390ee7e119d0d5c2c90d090673`；初审基线：`74d8e9ba8b49360ca90ade390f7b6c00cd40b815`。独立新 WT：`D:/wt/r07-core-fix-recheck-v2`，分支 `codex/r07-core-fix-recheck-v2`。报告 run：`recovery_r07_core_review_1_recheck_v2_20261016`；PG run_id：`r06_catalog_r07_core_recheck_v2_20261016`。

## 本次修改做了什么

VersionInterval 导出固定/包含上界互斥及真实非空边界规则，LiteratureReferenceValue 导出目标 document/revision 的成对 UUID 规则。现有知识发布事务在写入前核对内部文献目标真实配对、认证可见性与派生范围，阻止公共 claim 携带私有目标 UUID；正常公开、同租户和外部文献引用保留。

这次补丁复用现有 Schema 扩展、PG 事务和权限函数。基线到代码冻结的产品范围只有 `backend/src/ai_intel/domain/enrichment_values.py`、`backend/src/ai_intel/knowledge/persistence.py`、直接 Schema/PG 测试和 `contracts/schemas/schema_bundle.json`，以及批准记录 `CR-R07_typed_signal_claim_v3.md` 的修订附录。未改依赖、迁移、认证、阈值、分母或金标。

## 依据、隔离与证据来源

已读取本 WT AGENTS、执行地图、恢复11/12、03/04/05/06/07合同、R07卡、原T13/T19/T20/T22/T23/T41卡、两份 R07 接口/账本变更单、冻结 task_state/交接、作者 R07-core/fix1 报告。初审为 `D:/wt/r07-core-review-1/reports/reviews/recovery/G-C-R07-core-review-1.md`，旧未完复核 WT `D:/wt/r07-core-review-fix1` 未使用或覆盖。

采用 `C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md`，中文交付遵从任务。按共享 PG、多租户/多 worker 的仓库合同审查；新候选尚无生产发布者。报告只列具体输入与实测结果，不据图边/作者数量判断通过。

作者 manifest SHA256 `48cbfb075841db59358eb52634a5c159ef8b5d822c5e33a03ee597677c111cc6` 已独立从 `git show cb340978:...` 取原 blob，30项 byte长度与SHA256全部匹配（`author_blob_audit.json`）。checkout CRLF没有当作篡改。`git diff --name-only ce1da881 cb340978 -- backend/src backend/tests contracts` 无输出；本 WT 产品/测试/合同/进度保持干净。

reviewer 只新增本报告、新 run 日志/receipts/探针及范围内 `.gitattributes`。后者仅使本 run 的 log/json/xml/基线源快照保持原字节，cr-at-eol仅作用于这些证据，不豁免产品规则。未改作者业务代码、合同、已有测试、task_state、交接；未提交或 push。

## 三项 Must 的逐项结论

1. **版本区间导出约束：修复有效。** 原初审 `both_upper_boundaries`（introduced=1.0、fixed=1.2、last_affected=1.1）及 `empty_boundary`（仅branch=main）的完整输入原样重读，Runtime和导出 Schema/FormatChecker均拒绝。独立补充空对象、全null、branch+全null、空字符串及introduced-only/fixed-only/last_affected-only、null另一上界等边界，结果一致。对应 `enrichment_values.py:71–105`；24个原始结构输入的观察见 `independent_schema_observations.json`，其原源SHA256为 `c43b1b1270eca95e536007652d7db973fc0c4fb2777bf939700c133f2e150871`。

2. **文献目标配对导出约束：修复有效。** 原 `unpaired_literature_target` 仅给document UUID已由两层均拒绝。直接检查省略/双方null/仅一方null合法正例，单UUID、UUID+null、null+UUID及错误UUID负例；双方合法UUID保持有效。检查输入为未归一JSON，没有先用 model_dump 补齐字段来回避缺省差异。对应 `enrichment_values.py:122–157`；Schema与runtime输出一致不被扩张为语义、quote hash或ACL均能由JSON Schema证明。

3. **公共文献内嵌私有目标 UUID：修复有效。** 在真实新 PG 中重新构造原 public claim/public evidence→私有tenant目标的 relationally equivalent 输入，UUID由每例隔离fixture新建，不复用旧库身份。现在实际 `CrossTenantAccessError(resource not found)`，未写 claim，其他租户无法读该 claim 或目标证据；新增原先可见私有target的同tenant SYSTEM_ADMIN上下文仍因派生public范围更宽而抛 `KnowledgePublicationError`。跨租户、目标document/revision不存在和两个真实但不匹配的身份均拒绝，8张业务表及scope_epochs完全不变。对应 `knowledge/persistence.py:369–385`；实际完整合成提交和前后观察见 `independent_pg_observations.json`。

新增14个独立 PG 用例还验证 public→public、同tenant→同tenant、tenant→public、无内部目标外部文献的省略/null正例；完整JSONB新session重读不变，model_hypothesis仍unverified/unknown。批次同时含合法与非法目标时全部拒绝，同事务继续使用原key提交修正输入成功；第二次重放不增claim/evidence/assertion/receipt/change/job/outbox/epoch。同key变更目标身份会抛IdempotencyConflictError且无副作用。构造器绕过后的单目标/非法promoted hypothesis在publish重新校验并拒绝。

## 独立执行命令与结果

工作目录均为 `D:/wt/r07-core-fix-recheck-v2/backend`；每行完整argv、固定SHA、产品树状态在同名JSON，stdout/stderr在log，pytest真实JUnit在xml。`-o addopts=`仅显式关闭本定向调用的全套coverage配置；没有改原60%门，不计全套pure/覆盖通过。

| 标签 | 实际命令（JUnit路径在receipt） | 上海起止 | exit / 数量 |
|---|---|---|---|
| targeted_unit | `.venv/Scripts/python.exe -m pytest tests/contract/test_r07_signal_schema_boundaries.py tests/contract/test_r07_signal_claim_values.py tests/contract/test_r02_value_contract.py tests/unit/test_r02_knowledge_publication_contract.py tests/unit/test_r07_enrichment_contracts.py -o addopts= -q` | 2026-10-16T00:25:54+08:00 → 2026-10-16T00:26:02+08:00 | 0；87 passed，0 failure/error/skip |
| independent_schema | `.venv/Scripts/python.exe -m pytest D:\wt\r07-core-fix-recheck-v2\reports\runs\recovery_r07_core_review_1_recheck_v2_20261016\test_independent_schema.py -p tests.conftest -o addopts= -q` | 2026-10-16T00:27:12+08:00 → 2026-10-16T00:27:16+08:00 | 0；27 passed，0 failure/error/skip |
| targeted_pg_after_runtime | `.venv/Scripts/python.exe -m pytest tests/integration/test_r07_literature_target_scope_pg.py tests/integration/test_r07_signal_claim_values_pg.py tests/integration/test_r06_catalog_documents_pg.py -o addopts= -q` | 2026-10-16T00:34:44+08:00 → 2026-10-16T00:35:22+08:00 | 0；41 passed，0 failure/error/skip |
| independent_pg_after_runtime | `.venv/Scripts/python.exe -m pytest D:\wt\r07-core-fix-recheck-v2\reports\runs\recovery_r07_core_review_1_recheck_v2_20261016\test_independent_target_scope.py -p tests.conftest -o addopts= -q` | 2026-10-16T00:35:02+08:00 → 2026-10-16T00:35:19+08:00 | 0；14 passed，0 failure/error/skip |
| changed_ruff | `.venv/Scripts/python.exe -m ruff check src/ai_intel/domain/enrichment_values.py src/ai_intel/knowledge/persistence.py tests/contract/test_r07_signal_schema_boundaries.py tests/integration/test_r07_literature_target_scope_pg.py` | 2026-10-16T00:25:54+08:00 → 2026-10-16T00:25:54+08:00 | 0；非测试 |
| changed_format | `.venv/Scripts/python.exe -m ruff format --check src/ai_intel/domain/enrichment_values.py src/ai_intel/knowledge/persistence.py tests/contract/test_r07_signal_schema_boundaries.py tests/integration/test_r07_literature_target_scope_pg.py` | 2026-10-16T00:25:55+08:00 → 2026-10-16T00:25:55+08:00 | 0；非测试 |
| backend_mypy | `.venv/Scripts/python.exe -m mypy src` | 2026-10-16T00:25:56+08:00 → 2026-10-16T00:26:12+08:00 | 0；非测试；类型95文件 |

自有环境：`uv sync --frozen --offline --extra semantic` 于2026-10-16T00:23:11+08:00–00:23:24+08:00 exit0，不使用作者venv，没有外网安装。87定向unit/contract与27独立schema/兼容检查合计114用例；41定向真实PG为20个R07（原13+目标7）及旧catalog21，另外14为本次独立ACL/rollback/replay，共55 PG用例。全部0 failure/error/skip。

首次PG bootstrap在pytest前发生 `psycopg.errors.ConnectionTimeout`，exit1/0测试，起止未写入文件（工具输出保留在chat，不能补造秒值）。00:28:01–00:28:06只读诊断确认loopback拒绝连接，裸WSL docker不在PATH；`pg_environment_diagnosis.json`保留。主控随后安排唯一原受控runtime恢复任务；不将首次环境失败算业务红或skip，不换共享worker库。恢复后新标签复跑如上，旧诊断没有覆盖。

PG只从 `wsl.exe -d Ubuntu-22.04 -u root --exec cat /tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json` 捕获配置在内存，不输出DSN/密码，不读DPAPI。bootstrap只在既有测试连接执行pg_database目录检查和创建指定新数据库；所有迁移和业务用例仅访问 `test_dianzi_r06_catalog_r07_core_recheck_v2_20261016`。每例 `catalog_engine` 建新UUID schema、设statement_timeout=15000/lock_timeout=5000、迁移0015，finally只DropSchema自己schema；未跑原R02硬编码生产DSN fixture，没有生产库/共享固定worker库业务访问。

## 兼容与真实调用流

两个旧DTO从pre-R07 `1a52e17ffe327fb8a0c1d4f97372948a699910e3` 的Git源码独立载入、重生成并按规范字节比较：EnrichmentProjection `0589d3f32bb39f6397bf632d83bb4ac3c5b8288118ce1b2e29ad97e0c368940d`，DimensionSubmission `35357914105c7ed74b774a9e48b8974870e612edaebddff45ad577c00b35e9d4`，before/after相同。v1/v2/default2与九类typed roundtrip在87用例中复跑。

冻结bundle Git原字节等于当前 `render_schema_bundle()`；与初审74d bundle比较，仅ClaimRecord.$defs.VersionInterval.allOf和LiteratureReferenceValue.oneOf新增，去掉这两个批准规则后其余全部结构相同（`bundle_compatibility.json`）。不使用checkout换行来判断byte兼容。

CBM官方0.11.0位于 `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp`。00:22:48–00:22:56独立src-only索引项目 `r07-core-fix-recheck-v2-src-20261016`，缓存 `/tmp/dianzi-r07-core-fix-recheck-v2-cache`；1289 nodes/6409 edges，not_indexed/skipped/parse_partial/parse_unusable均0。随后schema及完整限定名 publish/_validate_submission/_save_claim出向trace均exit0，命令逐秒见 `bootstrap_commands.json`。仅backend/src，不索引reports/holdout/秘密/作者WT；本source树无CBM生成修改。

图谱再与rg及源码核对：既有source_documents→KnowledgeRepository.publish→先revalidate输入→begin_nested→对各submission执行目标校验→_save_claim→save_change_publication；拒绝走savepoint回滚。现有save_document_revision校验revision scope等于document scope（revisions.py:134–135），目标查询用revision_id+document_id精确匹配。_claim_from_row与get_claim保留v3完整结构，显示截断和HTTP2路径保持。新候选没有生产consumer；已有来源产物仍走其既有v2接口。图confidence/无边不代替真正Pydantic/PG触发输入。

## 未检查层、合同偏差与评分证据限制

本次unit/contract、限定真实PG integration/security通过。全pure、前端/e2e、真实来源/模型/资产、性能、持续运行、人工标注及原T整卡验收均not_run。0外网/模型/资产调用，无付费任务；不能以fixture/PG结果推算F2/P2/R1覆盖率、准确率、召回率或在线富化通过。

初审记录的继承int coercion、尚无生产九维worker/API/UI、真实块转永久坐标/语义支持、更新/冲突重判、v3特有并发首次发布和双时间修订链继续保留，不因本定向修复涂绿。已经存在于未审历史库的错误私有目标引用没有审计/修复；本次证明限定新写入边界与其正常重放，不涉及历史修复迁移。

批准v3回滚合同已核对：尚无v3写入可回退代码；写入后关闭新发布者并保留v3读取兼容层，不能删除事实/覆盖历史来回退。没有运行downgrade、回滚旧binary或修改数据库来伪证恢复。唯一执行偏差为本轮PG环境中断，已保存诊断并在原runtime恢复后独立复跑；原验收、阈值、分母、金标、盲测不变。

同run `artifact_manifest.json`封存报告和本轮独立制品SHA256，`seal.json`单独封存manifest/report哈希（manifest不自包含）。下一步主控可依据固定ce1/cb34的本意见登记/集成限定core修复；继续R07后续真实产品链及对应独立审查，不自动签整R07或跨G-C检查点。

Verdict: Ship（仅本次三项Must修复及所列core回归）。Not checked: 全pure、前端/e2e、外部live、性能、人工与整R07/G-C。
