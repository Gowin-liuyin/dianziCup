# R12 / T30 生产 0020 前向迁移 · 第一次独立审查

What this change does: 在正常 Alembic 链新增四张混合检索派生表，与已审 indexer 的列、主键、索引、vector(384) 和检查约束一致。它另加六种事实身份外键及两处 outbox 外键，使不存在的事实或任务不能成为已索引投影。

**Verdict: Ship — 仅固定 0020 生产迁移及两张生产测试 adapter 切片。没有发现需阻断该切片的可复现缺陷；完整 R12/T30/T35 与 G-D 仍未通过。**

文稿实际写入时间：2026-10-16T07:33:19.500094+08:00。下述检查均发生于 2026-10-16，时间为 +08:00；各命令的精确开始/结束及退出码见独占 run 中同名 JSON。本 reviewer 是新非作者，不参与实现，不修改业务、原测试、公共合同、progress、accepted 或 push；本轮仅写本报告和独占 run。

## 固定版本与权限范围

baseline `b502b7ea4a2ffdeca24b8edc7fa8a33cc0980457`，代码 `ed0e14a03a06ed104f23afd0be5407d873ed8edf`，材料/实际 HEAD `8c03ed305f8d40bfcaf4b090e95979e75fba7147`。独立工作树 `D:/wt/r12-production-review1` / `codex/r12-production-review1` 从材料 SHA 新建，初始 tracked status 干净。实际导入与 MIGRATIONS_DIR 已用断言核为本树 `backend/src` 和 `backend/migrations`；解释器只复用 `D:/dianzi/backend/.venv/Scripts/python.exe`。

相对 baseline 的 delta 只有 `backend/migrations/versions/0020_hybrid_retrieval.py`、`backend/tests/integration/test_r12_production_schema.py`、`backend/tests/integration/test_r12_production_indexing.py`、`docs/decisions/CR-R12_production_hybrid_migration.md`。旧 R05、已有 retrieval 服务/写入器、认证、配置、依赖、指标分母和盲测材料均未改变。

已读 AGENTS、00、R12 proposal、T30、03/04/05/06、固定 progress/handoff、CR、作者任务报告和 Ponytail Review 5.2.0。已有 hybrid 的 code `ba1548d591d2b341e61a230f1cdd5bd387f3235b` / material `d3f55300c34760bd97d9a85c710fc23b4a480b66` 及 recheck 报告仅用于理解此前限定边界；报告 raw SHA256 `fdd7e85122b79c02cd4afc4b0f9a44fbec51322e7761d783920930d9dfb066d8` 本轮 before/after 相同，副本保存于 run。它没有 review commit，不能把报告哈希充作 Git SHA。本结论来自当前固定树的独立重验。

## 连通代码与业务边界

`0020_hybrid_retrieval.py:17` 的 upgrade 只新增四表，没有旧事实回写或旧表删除。`:20` 用事务局部 search_path 解析 public.vector，沿用 0014 的方式；迁移 URL 的 schema 顺序仍决定四表及其外键的真实落点。`:43` 六个外键保证 evidence/revision/document/source/event/claim 的身份存在；`:89` 和 `:102` 分别绑定 outbox。独立负例证实，不存在身份导致真实 PG IntegrityError、事务回滚；这些独立外键不替代正确父链和 ACL 校验。

四表列、可空性、主键、unique index_name、scope 索引、384 维向量及原约束与 `hybrid_schema.py` 源码逐项核对，原生产反射测试也通过。非法 state/dimension、scope XOR、负 epoch、非法 offset、实际 SQL 的 vector383 均拒绝。新探针还反射七个 chunk 外键及四表实际 namespace，全部属于本例自身 schema，不能从 public 回退冒充迁移成功。

`test_r12_production_indexing.py:40/43` 将 runtime 的 `{schema},public` 与迁移的精确 `{schema}` 分开；`:54/56/60` 实际迁移后检查版本、current_schema 和四表落点；`:47/50` 禁止 MetaData.create_all。原 T30 所有函数和业务断言原样导入。独立资源副本只把第 33 行原作者 DB 守卫改成 reviewer 自有 DB，原 bytes 和单行 unified diff 留存，没有改输入、预期、时间预算或计数。

追踪原 `HybridIndexer.refresh_scope`：PG transaction 内按 generation/scope advisory lock 序列化；核对 knowledge-change outbox 与 PG change 的 scope/epoch；乱序完整快照不退水位，receipt 复投返回 replay。OS upsert、refresh、旧 scope 删除和第二次 refresh 成功，且范围版本锁定重读不变后，才写 PG chunks/watermark/receipt。原真实并发/重放、模型维度、权限/可用时间、当前事实/撤回和 epoch 竞态断言均通过。新增 upsert、remove_older_scope、第二次 refresh 故障保持旧 chunks、receipt 和 epoch1 水位，未把 OS 的部分变化算作 PG 已索引成功。

原最终返回围栏仍按当前父事实/关系、永久证据及 epoch 在同一 PG 事务持锁构建。新增六种“身份存在但父关系错误”的投影都在重排之前过滤，不能因 FK 存在就返回证据。错 model_version 的向量行被向量分支排除；合法 BM25 仍可以从 PG 当前证据得出命中，这不等于混用向量。真正错误的 embedding model_version 写入在 384 维仍明确报 ModelContractError，没有前进水位。

## 独立实跑与新增输入

入口 `reports/runs/recovery_r12_production_review1_20261016/review_checks.py` 用 subprocess capture、环境注入和写前实值脱敏。所有 pytest cwd 为本 WT/backend，`-o addopts=` 用于按指定切片运行而非冒充全仓覆盖率；数量从新 JUnit 提取，没有累加同一输入的重复迭代。

| label / 实际参数概要 | +08 起止 | exit / 结果 |
| --- | --- | --- |
| production：`-m pytest <resource_copy>/test_r12_production_schema.py <resource_copy>/test_r12_production_indexing.py -o addopts= -q --tb=short --junitxml=<run>/production.xml` | 07:25:53.998988–07:26:52.983109 | 0；30 passed，0 failed/error/skip，pytest57.16s；8个 DDL/history + 原22个 T30 实例 |
| related：`-m pytest tests/unit/test_r12_hybrid.py tests/contract/test_r12_hybrid_contracts.py tests/security/test_r12_retrieval_boundaries.py tests/unit/test_r05_grounded_answer.py tests/contract/test_r05_grounded_answer_contract.py -o addopts= -q --junitxml=<run>/related.xml` | 07:27:16.453217–07:27:22.933532 | 0；143 passed，0 failed/error/skip |
| negatives 首轮：`-m pytest <resource_copy>/test_independent_negative.py ... --junitxml=<run>/negatives.xml` | 07:27:06.157949–07:27:38.654628 | 1；15 passed/6 failed/0error/skip，原红及原探针 bytes 留存，分类见下文 |
| negatives_v2：同探针，保持原生产断言与业务不变，另加 model_version 与实际容量输入 | 07:28:25.237088–07:28:59.624989 | 0；23 passed，0 failed/error/skip，pytest32.66s |
| legacy_history：`-m pytest <resource_copy>/test_legacy_history.py ... --junitxml=<run>/legacy_history.xml` | 07:29:34.787376–07:29:37.186802 | 0；1 passed，0 failed/error/skip |
| ddl_boundaries：`-m pytest <resource_copy>/test_ddl_boundary.py ... --junitxml=<run>/ddl_boundaries.xml` | 07:30:21.835656–07:30:28.613631 | 0；4 passed，0 failed/error/skip |
| mypy：`-m mypy --cache-dir D:/wt/r12-production-review1-mypy-cache src` | 07:27:25.596143–07:27:38.239457 | 0；130 source files 无错误 |
| ruff / format：`-m ruff check` / `-m ruff format --check`，0020 与两 adapter | 07:28:35.168148–07:28:35.312674 / 07:28:35.794820–07:28:35.926550 | 各0；3代码文件通过，无新增 ignore |

新增实际输入：六个 UUID 孤儿外键、四种非法 derived scope、六种有效身份但错误父链、三个 OS 故障阶段、错向量模型元数据、384 维但错误 embedding model、实际10001个合法事件/证据/claim组合行超10000查询容量、三个 epoch/offset 非法值和 PostgreSQL 原生 vector383 更新。超容量没有调低常量，没有做 paid 模型调用或往 OS 写10001个投影；indexer 在查询容量边界处显式失败且 PG 投影/水位/receipt 保持0。

新 history 输入在0019自有 schema 填入真实数据库中的合成 source/document/revision/span/claim、change/job/outbox、user、旧 `retrieval_chunks` vector(384) 和 `grounded_answers` JSON 后，复用原历史测试不变的所有旧表逐行 `to_jsonb` 比较与 create_all 禁止断言，0020后全部行值不变。原生产 history 测试也独立通过；不把旧 R05 空表比较充作已有向量数据保留证据。

首轮新增 probe 的5个父关系红例是 reviewer 预期原因码错：实际已经空 hit/partial/零重排，返回 `index_projection_changed`，原 probe 机械预期 `stale_candidates_filtered`。第6红误把正常 BM25 的当前事实命中当作必须无 hit；源码及后续 vector_count=0/BM25_count=1 实证推翻这个假设。保留 `independent_negative_v1.py.txt`、negatives.log/XML，v2明确细分行为并增加独立 wrong-model 写入输入。没有为消红修改被审业务或任何原测试/金标。

初期 source_trace 命令因 cwd 下相对脚本路径错而 exit2，下一次外层0但一条 rg 对错误 events/persistence 路径 exit2；两层错误日志保留。纠正为真实 knowledge/event_linking 路径后的 catalog_publication_v3 exit0，未包装为业务测试红。早期只读探索没有逐条 run receipt，按工具原记录保留，不补造起止时间。

## 独立 CBM 与真实 caller

新 project `dianzi-r12-production-review1-20261016` 仅索引本 WT/backend/src。实际命令前缀 `wsl.exe -d Ubuntu-22.04 --exec /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json`；index_repository 使用精确 `/mnt/d/wt/r12-production-review1/backend/src`、fast、persistence=false。07:26:02.901011–07:26:08.856434 完成，1639 nodes/8621 edges，not_indexed/skipped/parse_partial/parse_unusable均0；schema、retrieval architecture、refresh_scope inbound/outbound、migration inbound、build_question_service outbound、consume_job outbound、catalog outbound 共9条命令均 exit0，07:26:34.236150结束。工具摘要 excluded assets/cache，不能据此签资产能力。

CBM indexer inbound0不是无业务调用的充分证据，本轮另外全 src rg 并读真实入口。question_routes.py:55仍构建 `GroundedQuestionService(... EventEvidenceRetriever ...)`；workers/runtime.py 的 EXECUTION_HANDLERS 只有来源处理等现有 handler，没有 hybrid/knowledge_change 索引消费注册；catalog_documents.py:287仅事务内 bump public epoch，没有与此四表的 outbox reconciliation。原服务只有定义/测试调用，API/worker/catalog 未接线缺口与 CR 明确限制一致，不能因DDL、静态图或模型单例签完整产品链。

## 材料、历史失败与资源

作者 manifest raw SHA256 `bf5aaa6bddc37a70d3a279b58546fd31e2c107775b9d3ab65ac6ff4c700b261d`，72 members 在固定8c Git blob逐项 bytes/SHA核验0失败；4个源码 raw/LF/代码blob单独保存证明。新WT raw材料71项直接一致；任务报告 checkout 自动CRLF导致1项 raw差异，LF归一后与固定 Git blob精确相等。未改这份原报告；将其精确固定blob另存 `fixed_material_task_report.md.txt`，`checkout_byte_observation.json`保留原raw hash/CRLF数量。这是 checkout 字节表现，不能将原raw错报为72项全一致，也不影响已冻结blob结论。

历史 initial68 manifest、ScopeMismatch1/7 errors、首次production10failed/20passed、初始lint失败、原 raw CRLF material_check.log均在固定72清单中逐blob核对，未覆盖、删题、改skip或取未提交修订作背书。作者30/143绿只帮助选测试，本轮有自己的真实命令与JUnit。此前首次commit helper覆盖历史日志的问题以8c固定blob为权威，未读作者继续工作的目录来决定通过。

专用 `test_dianzi_r12_prod_review1_20261016` / DIANZI_TEST_RUN_ID=`r12_prod_review1_20261016`。资源reference经pwsh7 DPAPI在 subprocess capture内存读取，只验证原loopback127.0.0.1:25432/test_账号/原test_dianzi_r01_20261014身份后创建自有DB；不打印秘密、不入argv/提示/报告。明确加载共享 tests/conftest 的 failure hook，并为每例注册真实 DSN/密码 SecretStr；stdout/XML写前再脱敏。PG实际16.14、vector0.8.2。OpenSearch仅29200的自有随机 `dianzi_test_r12_*` index，schemas仅自有DB的 `test_r12_production_*` / `test_r12_history_*`；没有source采集库、Redis15、他人schema/index或用户文件操作。

所有 corpus teardown 都断言精确自身 index DELETE200/404及 DropSchema成功。最终独立PG查询剩余自有test_r12 schemas=0；没有请求共享OS全局索引列表，故不宣称全球索引残留0。自有DB保留用于复现，不删除public的自有负例generation行。实际secret值扫描结果见 actual_secret_scan.json，仅归档文本，排除pyc/cache/holdout/秘密reference；最终0匹配。

回滚仅审源码：0020 downgrade按 receipt/watermark/chunks/generation顺序只删四张可重建派生表。CR要求先停消费者、导出水位/收据并保留历史，优先回退应用读取路径；本轮没有 destructive downgrade、生产数据恢复或灾备实跑，不计rollback live通过。

## 未验范围与交接

unit/contract/security及上述生产PG/OS integration通过限本切片。只有原C02的三条合成中英文档实际复用已核本地 E5/reranker 与PG余弦；其余语义为显式 fixture。未新增下载、付费调用、来源抓取、扫描、利用、PoC、holdout或人工标注；无正式准确率、召回率、时效、冷/热并发性能、完整问答≤5秒或持续运行时长结论。

不签默认API/worker注册、catalog无outbox路径补偿、多轮、多跳、graph生产候选、资产四态、回答发布最后认证/事实围栏、前端/browser、生成模型live、人工金标和整R12/T30/T35/G-D。F3/P3/E1只获得生产可迁移与已审检索适配的局部证据；没有官方评分档位。当前任务状态仍由主控按本独立审查登记，作者awaiting_review事实保留，reviewer未改accepted。

下一任务建议：单独冻结并审查0020的 worker/outbox/API 接线与 catalog epoch reconciliation，按原前置补正式graph/资产/多轮问答、完整回答时延和真实来源评测。本review按本有界切片停止。

**Verdict: Ship — 仅上述四文件切片。Not checked：生产downgrade/恢复、API/worker/catalog接线、前端、多轮多跳/graph、真人gold、完整QA/SLA与整R12/G-D。**
