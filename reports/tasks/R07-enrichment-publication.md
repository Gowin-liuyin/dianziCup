# R07 · 受控载入、多来源证据与逐维PG发布

文档首次创建时间：2026-10-16T03:02:21+08:00
本次写作开始时间：2026-10-16T03:02:21+08:00
本次写作结束时间：2026-10-16T03:02:21+08:00
最后更新时间：2026-10-16T03:02:21+08:00
阶段：G-C；作者 /root；状态 awaiting_review，独立初审已确认问题待修。
代码：71e594cb958bd93d21fb7ed66574b3cba4cc47e1；工作树 D:/wt/r07-publication；分支 codex/r07-publication。
实现状态：partial。unit/contract 定向passed；PG integration定向passed；security所属完整pure结果见下，不能概括全绿；frontend/e2e/live/manual not_run。
材料提交：本报告封存后另提交；本批未push，不代表G-C放行。

## 用户行为与实现

当前服务从认证scope下的PG事件载入当前原文，逐件校hash/size与证据块，再将来源支持的结构字段或明确未验证模型候选保存到原PG知识账本。多来源ClaimSubmission只在schema3扩展additional_sources；空集合不改变旧payload指纹。实际event_detail读投影能返回属于每个声明来源的引用。未接worker/API提交、真实新模型调用或UI富化操作，不能把只有测试调用的写服务称为完成。

复用EventRepository、KnowledgeRepository、DimensionRepository、原对象存储、Pydantic、SQLAlchemy、PG事务/幂等/outbox、hashlib/uuid；没有新增依赖或数据库迁移。新增inputs和publication职责是对象IO前验证与候选发布，不能由旧单来源入口直接完整表达。源输入20修订/每件2MiB/合计JSON8MiB、块数与字符数有界；这不意味着所有模型输出或进程总内存被8MiB限制。

四个来源结构维度发布前重算；其他模型维度必须pending/model_hypothesis，不能凭引文存在提升事实。合法FAILED维度可与成功字段保存；非法候选让调用方事务整体回滚。当前函数docstring对每维rollback的描述不够准确，以CR和实际整体事务行为为准，待修复批更正。无证据不当作not_found，来源等级不消除冲突。

## 文件及调用范围

- backend/src/ai_intel/api/knowledge_read_service.py
- backend/src/ai_intel/enrichment/inputs.py
- backend/src/ai_intel/enrichment/publication.py
- backend/src/ai_intel/knowledge/persistence.py
- backend/tests/integration/test_r07_composed_claims_pg.py
- backend/tests/integration/test_r07_enrichment_inputs_pg.py
- backend/tests/integration/test_r07_enrichment_publication_pg.py
- docs/decisions/CR-R07_multisource_enrichment_publication.md

23f5186父版本已含独立审查过的A公开字段；从cb340978作diff还会包含这些连接代码，不把A原Ship视为本发布服务已审。代码图71独立index r07-publication-71e594c-src，backend/src范围，默认assets排除；8个命令全部exit0，qualified loader/publisher/KnowledgeRepository/event_detail与rg核对记录roster_fixed_cbm_commands.json。写服务目前仅测试调用，读API已有真实入口。

## 已复现问题及处理

- 来源集合遗漏：事件有两个current PG来源，只提交其中一个仍能保存FAILED模型维度。原source_subset_red真实1fail，71增加文档集合精确相等/去重保护；定向1+2及最终77PG通过。早期两个空/重复用例只触发不同错误类型，不能冒称已经证明允许写入，原revision_roster_red保留。
- 旧仪器错误：loader fixture reexport、误写event_detail方法名、宽查询one()、快照helper的observed_at默认None均已精确纠正；原log/xml未改。不是每个red都是产品缺陷。
- 新独立初审71已实际复现三个Must，尚未关闭：父sources/documents ACL撤权仍对象读取或空候选FAILED发布；source提交与发布scope/doc锁反序触发40P01；不同authority CVSS被误标conflict。原reviewer为r07_publication_first_independent_review，证据位于其冻结D:/wt/r07-pub-review1的independent_negatives_extended与concurrent_source_publication_outcomes。初审报告当时未封存，不能用作者日志替代。
- 两个独立实现者分别在D:/wt/r07-pub-fix修ACL/锁，在D:/wt/r07-cvss-scope修authority分组；不得修改71已审源码或原probe。旧不合合同的unit期望迁移须保留原红、数量、输入/期望差异和正式CR，金标/阈值/分母不动。修后新SHA再由原独立reviewer定向复核。
- 完整pure在71为1992pass/1fail/10deselected、coverage75.82%（原门60）；唯一失败是R20 PDF真实worker启动守卫用例。本树不含后来主分支535启动修复，不能用此结果推断8a主分支相同状态；主分支独立组合验证另进行。未降低CPU/覆盖门或重跑碰绿。

## 实际验证

下表cwd均为本工作树backend，helper的PG部分从本机私有连接文件仅读入env，使用自己的test_dianzi_r06_catalog_r07_publication_20261016及UUID schema，无开发库/旧GB库或downgrade；原日志不含连接参数。raw工具/编译命令不适用测试数量。无外部source/model/provider请求，无费用新增；产品费用本批0调用，未知历史费用仍unknown。

| 记录 | 开始/结束+08:00 | exit | JUnit实际数量 | 命令 |
|---|---|---:|---|---|
| composed_format_apply | 2026-10-16T00:41:12+08:00 / 2026-10-16T00:41:12+08:00 | 0 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m ruff format src/ai_intel/knowledge/persistence.py src/ai_intel/api/knowledge_read_service.py src/ai_intel/enrichment/inputs.py tests/integration/test_r07_enrichment_inputs_pg.py tests/integration/test_r07_composed_claims_pg.py` |
| composed_pg_initial | 2026-10-16T00:41:14+08:00 / 2026-10-16T00:41:52+08:00 | 1 | total=59, pass=47, fail=0, error=12, skip=0 | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r07_enrichment_inputs_pg.py tests/integration/test_r07_composed_claims_pg.py tests/integration/test_r07_signal_claim_values_pg.py tests/integration/test_r07_literature_target_scope_pg.py tests/integration/test_r06_catalog_documents_pg.py --no-cov -q --junitxml=D:\wt\r07-publication\reports\runs\recovery_r07_publication_20261015\composed_pg_initial.xml` |
| composed_pg_v2 | 2026-10-16T00:44:55+08:00 / 2026-10-16T00:45:39+08:00 | 1 | total=59, pass=47, fail=0, error=12, skip=0 | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r07_enrichment_inputs_pg.py tests/integration/test_r07_composed_claims_pg.py tests/integration/test_r07_signal_claim_values_pg.py tests/integration/test_r07_literature_target_scope_pg.py tests/integration/test_r06_catalog_documents_pg.py --no-cov -q --junitxml=D:\wt\r07-publication\reports\runs\recovery_r07_publication_20261015\composed_pg_v2.xml` |
| composed_pg_v3 | 2026-10-16T00:50:07+08:00 / 2026-10-16T00:50:51+08:00 | 0 | total=59, pass=59, fail=0, error=0, skip=0 | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r07_enrichment_inputs_pg.py tests/integration/test_r07_composed_claims_pg.py tests/integration/test_r07_signal_claim_values_pg.py tests/integration/test_r07_literature_target_scope_pg.py tests/integration/test_r06_catalog_documents_pg.py --no-cov -q --junitxml=D:\wt\r07-publication\reports\runs\recovery_r07_publication_20261015\composed_pg_v3.xml` |
| composed_ruff_apply | 2026-10-16T00:41:13+08:00 / 2026-10-16T00:41:13+08:00 | 0 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m ruff check --fix src/ai_intel/knowledge/persistence.py src/ai_intel/api/knowledge_read_service.py src/ai_intel/enrichment/inputs.py tests/integration/test_r07_enrichment_inputs_pg.py tests/integration/test_r07_composed_claims_pg.py` |
| frozen_format | 2026-10-16T01:44:58+08:00 / 2026-10-16T01:44:58+08:00 | 0 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m ruff format --check src tests` |
| frozen_mypy | 2026-10-16T01:44:58+08:00 / 2026-10-16T01:44:59+08:00 | 0 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m mypy src` |
| frozen_pg | 2026-10-16T01:44:58+08:00 / 2026-10-16T01:46:03+08:00 | 0 | total=74, pass=74, fail=0, error=0, skip=0 | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r07_enrichment_inputs_pg.py tests/integration/test_r07_composed_claims_pg.py tests/integration/test_r07_enrichment_publication_pg.py tests/integration/test_r07_signal_claim_values_pg.py tests/integration/test_r07_literature_target_scope_pg.py tests/integration/test_r06_catalog_documents_pg.py --no-cov -q --junitxml=D:\wt\r07-publication\reports\runs\recovery_r07_publication_20261015\frozen_pg.xml` |
| frozen_ruff | 2026-10-16T01:44:58+08:00 / 2026-10-16T01:44:58+08:00 | 0 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m ruff check src tests` |
| frozen_unit | 2026-10-16T01:44:58+08:00 / 2026-10-16T01:45:02+08:00 | 0 | total=202, pass=202, fail=0, error=0, skip=0 | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m pytest tests/contract/test_r07_signal_claim_values.py tests/contract/test_r02_value_contract.py tests/unit/test_r02_knowledge_publication_contract.py tests/unit/test_r07_enrichment_contracts.py tests/unit/test_r07_public_signals.py tests/contract/test_r07_public_signal_sources.py tests/unit/test_r07_public_signals_fix1.py tests/contract/test_r07_public_signals_fix1_cwe.py --no-cov -q --junitxml=D:\wt\r07-publication\reports\runs\recovery_r07_publication_20261015\frozen_unit.xml` |
| loader_initial | 2026-10-15T23:42:37+08:00 / 2026-10-15T23:42:49+08:00 | 1 | total=9, pass=8, fail=1, error=0, skip=0 | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r07_enrichment_inputs_pg.py --no-cov -q --junitxml=D:\wt\r07-publication\reports\runs\recovery_r07_publication_20261015\loader_initial.xml` |
| loader_mypy | 2026-10-15T23:48:22+08:00 / 2026-10-15T23:48:33+08:00 | 1 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m mypy src` |
| loader_mypy_v2 | 2026-10-15T23:50:47+08:00 / 2026-10-15T23:50:48+08:00 | 0 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m mypy src` |
| loader_red | 2026-10-15T23:41:26+08:00 / 2026-10-15T23:41:30+08:00 | 2 | total=1, pass=0, fail=0, error=1, skip=0 | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r07_enrichment_inputs_pg.py --no-cov -q --junitxml=D:\wt\r07-publication\reports\runs\recovery_r07_publication_20261015\loader_red.xml` |
| loader_ruff_v2 | 2026-10-15T23:50:49+08:00 / 2026-10-15T23:50:49+08:00 | 0 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m ruff check src tests` |
| loader_v2 | 2026-10-15T23:48:06+08:00 / 2026-10-15T23:48:21+08:00 | 0 | total=9, pass=9, fail=0, error=0, skip=0 | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r07_enrichment_inputs_pg.py --no-cov -q --junitxml=D:\wt\r07-publication\reports\runs\recovery_r07_publication_20261015\loader_v2.xml` |
| prefreeze_format | 2026-10-16T01:41:33+08:00 / 2026-10-16T01:41:33+08:00 | 0 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m ruff format --check src tests` |
| prefreeze_mypy | 2026-10-16T01:41:33+08:00 / 2026-10-16T01:41:35+08:00 | 0 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m mypy src` |
| prefreeze_ruff | 2026-10-16T01:41:33+08:00 / 2026-10-16T01:41:33+08:00 | 0 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m ruff check src tests` |
| publication_format_apply | 2026-10-16T00:52:53+08:00 / 2026-10-16T00:52:53+08:00 | 0 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m ruff format src/ai_intel/knowledge/persistence.py src/ai_intel/api/knowledge_read_service.py src/ai_intel/enrichment/inputs.py src/ai_intel/enrichment/publication.py tests/integration/test_r07_enrichment_inputs_pg.py tests/integration/test_r07_composed_claims_pg.py` |
| publication_format_apply_v2 | 2026-10-16T01:36:43+08:00 / 2026-10-16T01:36:43+08:00 | 0 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m ruff format src/ai_intel/knowledge/persistence.py src/ai_intel/api/knowledge_read_service.py src/ai_intel/enrichment/inputs.py src/ai_intel/enrichment/publication.py tests/integration/test_r07_enrichment_inputs_pg.py tests/integration/test_r07_composed_claims_pg.py tests/integration/test_r07_enrichment_publication_pg.py` |
| publication_mypy_initial | 2026-10-16T00:51:50+08:00 / 2026-10-16T00:51:52+08:00 | 1 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m mypy src` |
| publication_mypy_v2 | 2026-10-16T00:52:54+08:00 / 2026-10-16T00:52:54+08:00 | 0 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m mypy src` |
| publication_ruff_apply | 2026-10-16T00:52:53+08:00 / 2026-10-16T00:52:53+08:00 | 0 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m ruff check --fix src/ai_intel/knowledge/persistence.py src/ai_intel/api/knowledge_read_service.py src/ai_intel/enrichment/inputs.py src/ai_intel/enrichment/publication.py tests/integration/test_r07_enrichment_inputs_pg.py tests/integration/test_r07_composed_claims_pg.py` |
| publication_ruff_apply_v2 | 2026-10-16T01:35:23+08:00 / 2026-10-16T01:35:23+08:00 | 0 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m ruff check --fix src/ai_intel/knowledge/persistence.py src/ai_intel/api/knowledge_read_service.py src/ai_intel/enrichment/inputs.py src/ai_intel/enrichment/publication.py tests/integration/test_r07_enrichment_inputs_pg.py tests/integration/test_r07_composed_claims_pg.py tests/integration/test_r07_enrichment_publication_pg.py` |
| publication_ruff_initial | 2026-10-16T00:51:50+08:00 / 2026-10-16T00:51:50+08:00 | 1 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m ruff check src tests` |
| publisher_pg_initial | 2026-10-16T01:07:38+08:00 / 2026-10-16T01:08:42+08:00 | 1 | total=65, pass=62, fail=3, error=0, skip=0 | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r07_enrichment_inputs_pg.py tests/integration/test_r07_composed_claims_pg.py tests/integration/test_r07_enrichment_publication_pg.py tests/integration/test_r07_signal_claim_values_pg.py tests/integration/test_r07_literature_target_scope_pg.py tests/integration/test_r06_catalog_documents_pg.py --no-cov -q --junitxml=D:\wt\r07-publication\reports\runs\recovery_r07_publication_20261015\publisher_pg_initial.xml` |
| publisher_pg_v2 | 2026-10-16T01:14:43+08:00 / 2026-10-16T01:15:37+08:00 | 0 | total=65, pass=65, fail=0, error=0, skip=0 | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r07_enrichment_inputs_pg.py tests/integration/test_r07_composed_claims_pg.py tests/integration/test_r07_enrichment_publication_pg.py tests/integration/test_r07_signal_claim_values_pg.py tests/integration/test_r07_literature_target_scope_pg.py tests/integration/test_r06_catalog_documents_pg.py --no-cov -q --junitxml=D:\wt\r07-publication\reports\runs\recovery_r07_publication_20261015\publisher_pg_v2.xml` |
| revision_roster_red | 2026-10-16T01:52:48+08:00 / 2026-10-16T01:53:00+08:00 | 1 | total=2, pass=0, fail=2, error=0, skip=0 | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r07_enrichment_publication_pg.py -k snapshot_revision_roster --no-cov -q --junitxml=D:\wt\r07-publication\reports\runs\recovery_r07_publication_20261015\revision_roster_red.xml` |
| roster_fixed_format | 2026-10-16T02:45:49+08:00 / 2026-10-16T02:45:50+08:00 | 0 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m ruff format --check src tests` |
| roster_fixed_mypy | 2026-10-16T02:45:49+08:00 / 2026-10-16T02:45:50+08:00 | 0 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m mypy src` |
| roster_fixed_pg | 2026-10-16T02:45:23+08:00 / 2026-10-16T02:46:50+08:00 | 0 | total=77, pass=77, fail=0, error=0, skip=0 | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r07_enrichment_inputs_pg.py tests/integration/test_r07_composed_claims_pg.py tests/integration/test_r07_enrichment_publication_pg.py tests/integration/test_r07_signal_claim_values_pg.py tests/integration/test_r07_literature_target_scope_pg.py tests/integration/test_r06_catalog_documents_pg.py --no-cov -q --junitxml=D:\wt\r07-publication\reports\runs\recovery_r07_publication_20261015\roster_fixed_pg.xml` |
| roster_fixed_pure | 2026-10-16T02:46:06+08:00 / 2026-10-16T02:48:18+08:00 | 1 | total=1993, pass=1992, fail=1, error=0, skip=0 | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m pytest tests/unit tests/contract tests/security -m not real_pg -q --junitxml=D:\wt\r07-publication\reports\runs\recovery_r07_publication_20261015\roster_fixed_pure.xml` |
| roster_fixed_ruff | 2026-10-16T02:45:49+08:00 / 2026-10-16T02:45:50+08:00 | 0 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m ruff check src tests` |
| roster_fixed_unit | 2026-10-16T02:45:22+08:00 / 2026-10-16T02:45:26+08:00 | 0 | total=202, pass=202, fail=0, error=0, skip=0 | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m pytest tests/contract/test_r07_signal_claim_values.py tests/contract/test_r02_value_contract.py tests/unit/test_r02_knowledge_publication_contract.py tests/unit/test_r07_enrichment_contracts.py tests/unit/test_r07_public_signals.py tests/contract/test_r07_public_signal_sources.py tests/unit/test_r07_public_signals_fix1.py tests/contract/test_r07_public_signals_fix1_cwe.py --no-cov -q --junitxml=D:\wt\r07-publication\reports\runs\recovery_r07_publication_20261015\roster_fixed_unit.xml` |
| roster_guard_format_apply | 2026-10-16T02:21:49+08:00 / 2026-10-16T02:21:49+08:00 | 0 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m ruff format src/ai_intel/knowledge/persistence.py src/ai_intel/api/knowledge_read_service.py src/ai_intel/enrichment/inputs.py src/ai_intel/enrichment/publication.py tests/integration/test_r07_enrichment_inputs_pg.py tests/integration/test_r07_composed_claims_pg.py tests/integration/test_r07_enrichment_publication_pg.py` |
| roster_guard_green | 2026-10-16T02:24:24+08:00 / 2026-10-16T02:24:28+08:00 | 0 | total=2, pass=2, fail=0, error=0, skip=0 | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r07_enrichment_publication_pg.py -k snapshot_revision_roster --no-cov -q --junitxml=D:\wt\r07-publication\reports\runs\recovery_r07_publication_20261015\roster_guard_green.xml` |
| roster_guard_ruff_after_format | 2026-10-16T02:23:23+08:00 / 2026-10-16T02:23:23+08:00 | 0 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m ruff check src tests` |
| roster_guard_ruff_apply | 2026-10-16T02:21:43+08:00 / 2026-10-16T02:21:43+08:00 | 1 | not applicable | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m ruff check --fix src/ai_intel/knowledge/persistence.py src/ai_intel/api/knowledge_read_service.py src/ai_intel/enrichment/inputs.py src/ai_intel/enrichment/publication.py tests/integration/test_r07_enrichment_inputs_pg.py tests/integration/test_r07_composed_claims_pg.py tests/integration/test_r07_enrichment_publication_pg.py` |
| snapshot_pg_v1 | 2026-10-16T01:28:38+08:00 / 2026-10-16T01:29:46+08:00 | 1 | total=74, pass=73, fail=1, error=0, skip=0 | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r07_enrichment_inputs_pg.py tests/integration/test_r07_composed_claims_pg.py tests/integration/test_r07_enrichment_publication_pg.py tests/integration/test_r07_signal_claim_values_pg.py tests/integration/test_r07_literature_target_scope_pg.py tests/integration/test_r06_catalog_documents_pg.py --no-cov -q --junitxml=D:\wt\r07-publication\reports\runs\recovery_r07_publication_20261015\snapshot_pg_v1.xml` |
| snapshot_pg_v2 | 2026-10-16T01:32:22+08:00 / 2026-10-16T01:33:29+08:00 | 0 | total=74, pass=74, fail=0, error=0, skip=0 | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r07_enrichment_inputs_pg.py tests/integration/test_r07_composed_claims_pg.py tests/integration/test_r07_enrichment_publication_pg.py tests/integration/test_r07_signal_claim_values_pg.py tests/integration/test_r07_literature_target_scope_pg.py tests/integration/test_r06_catalog_documents_pg.py --no-cov -q --junitxml=D:\wt\r07-publication\reports\runs\recovery_r07_publication_20261015\snapshot_pg_v2.xml` |
| source_subset_green | 2026-10-16T02:02:43+08:00 / 2026-10-16T02:02:46+08:00 | 0 | total=1, pass=1, fail=0, error=0, skip=0 | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r07_enrichment_publication_pg.py -k drop_one_of_two --no-cov -q --junitxml=D:\wt\r07-publication\reports\runs\recovery_r07_publication_20261015\source_subset_green.xml` |
| source_subset_red | 2026-10-16T01:57:50+08:00 / 2026-10-16T01:57:54+08:00 | 1 | total=1, pass=0, fail=1, error=0, skip=0 | `D:\wt\r07-publication\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r07_enrichment_publication_pg.py -k drop_one_of_two --no-cov -q --junitxml=D:\wt\r07-publication\reports\runs\recovery_r07_publication_20261015\source_subset_red.xml` |

最终定向：roster_fixed_unit 202pass、roster_fixed_pg 77pass、Ruff/format exit0、mypy99源文件exit0。前置202与77内已包含其他子集合，不与重复跑数相加计成功量。合成来源输入只计真实PG integration，不计source/model live。

## 合同、证据与下一步

CR-R07_multisource_enrichment_publication记录schema3兼容、无迁移、历史回执、拒绝变更输入、失败语义和回滚。13官方要求和U场景尚无此片完整评分；它仅支持F2与后续问答证据，R07/T19/T20/T21/T22/T23及G-C均未整体验收。

原始JSON/log/XML与脚本完整保全。下一步先关闭独立三Must、复跑旧77/202和新增真实并发/ACL/机构对照，后与主控runtime/单维模型接口接成有界durable jobs；随后真实来源/模型/API/UI回归。手工金标和授权资产阻塞不阻止这些代码工作，但不能据此声称live已通过。

## 修订

2026-10-16T03:02:21+08:00 /root首次写作。历史代码编写起止未完整记录；各次测试时刻以上述实际receipts为准，不根据mtime推测。写报告用时不等于持续运行窗口。
