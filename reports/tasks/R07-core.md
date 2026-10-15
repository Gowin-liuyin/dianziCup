# R07 · 类型化候选与版本化账本切片

文档首次创建时间：2026-10-15T23:26:03+08:00
本次写作开始时间：2026-10-15T23:26:03+08:00
本次写作结束时间：2026-10-15T23:26:03+08:00
最后更新时间：2026-10-15T23:26:03+08:00
主控/实现：/root；阶段G-C；状态awaiting_review；实现partial。
基线：main 1a52e17ffe327fb8a0c1d4f97372948a699910e3（产品同1156）。工作分支codex/r07-core，WT D:/wt/r07-core。
候选接口代码SHA：098502991f617a5fa9fdfb9c3da91e54aee7ff06。
最终已测代码SHA：74d8e9ba8b49360ca90ade390f7b6c00cd40b815。
已审SHA：尚未独立初审；未集成、未push。本报告不签R07或原T整卡accepted。

## 输入、输出和实际范围

事件上下文/固定版本与块→九类结构候选/逐维尝试；已授权发布者可通过既有知识账本保存显式v3结构。九维字段、缺失/冲突/失败/未知语义与CVSS机构一致性均受限。候选没有可自填supports_claim/human_confirmed字段，结构验证不是语义支持。模型假设在真实PG测试中仍unverified/unknown，不能被作为已证实事实。

复用现有Pydantic、受限联合、SQLAlchemy/PG事务、知识发布收据、JSONB/历史/权限。新增domain/enrichment_values及enrichment/contracts承载实际九维差异；两个原API/PG维度Literal合并到唯一领域定义，旧两个DTO JSON Schema逐字相同，证据existing_schema_compatibility.json。未引入依赖或迁移。

后续Claim v3限定九个谓词与值，v1/v2/default2保留；旧HTTP schema2不变。过长v3仅显示摘要明确截断至4000Unicode字符，完整object_json原样保存并可由账本重读；不会把截断串解析为事实。合同与回滚见CR-R07_enrichment_candidate_seam、CR-R07_typed_signal_claim_v3：出现v3后回滚必须保留读取层，不能回退旧binary后删数据。

本批尚无自动富化作业、来源loader、语义支持验证/发布流水线、真实模型新调用或新UI接线。四公开信号由独立实现包消费098接口；它不能自动获得写事实权限。R07:T13/T19/T20/T22/T23/T41只是内部切片，不代表全映射完成。R08/R09/R10等原验收不缩减。

## 文件和调用链

098包含domain/enrichment_values.py、enrichment/contracts.py、api/knowledge_contracts.py、enrichment/persistence.py、直接unit及接口变更单。74d包含domain/enrichment_values.py/records.py、knowledge/persistence.py、schema_bundle、直接contract/PG测试及v3变更单。

真实既有链：source_documents._publish_cvss→KnowledgeRepository.publish→claims/claim_evidence/assertions/receipt/outbox→DimensionRepository.publish→enrichment_results→KnowledgeReadService→原工作台九维。新类型通过账本PG测试进入claims，但尚无生产调用；不能将只存在测试的路径当新产品能力。

CBM初索引存在过程偏差：最早两个候选类型文件写入后才对该WT初次index，初图明确含这两个untracked文件，不能称纯1156图。现以74d刷新backend/src独立索引r07-core-74d8e9b-src（排除reports/holdout/秘密），index/schema/architecture/Claim入向均实际0。首个简写KnowledgeRepository.publish查询function-not-found/exit1保留；search_graph找到完整限定名后两个publish出向trace成功。图与rg/源码及真实测试交叉核对，有边不是业务正确证明。

## 实际检查

原60%覆盖门没有改。本批focused以--no-cov表示定向检查，不冒称完整覆盖/全仓回归。最终固定74d：77unit/contract与34真实PG均通过，PG其中13新v3及21原catalog；自有92包venv，专用test_dianzi_r06_catalog_worker_20261015内每例UUID schema，迁移0015并只清理自己schema，未运行原R02含硬编码库的整套用例。导入其构造helper不使用其数据库fixture。

unit/contract=passed（限定本切片）；integration/security=passed（限定真实PG重放/权限/机构冲突与类型边界）；frontend/e2e/live/manual=not_run。API DTO仅兼容快照，未跑HTTP浏览器或真实模型，不能由此给整R07八层passed。

| 检查 | Asia/Shanghai开始→结束 | exit | 数量 | 实际argv（cwd backend，CBM在WT root） |
|---|---|---|---|---|
| format_apply | 2026-10-15T22:45:34+08:00 → 2026-10-15T22:45:34+08:00 | 0 | not_test | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m ruff format src/ai_intel/domain/enrichment_values.py src/ai_intel/enrichment/contracts.py tests/unit/test_r07_enrichment_contracts.py |
| initial_mypy | 2026-10-15T22:45:34+08:00 → 2026-10-15T22:45:46+08:00 | 0 | not_test | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m mypy src |
| initial_ruff | 2026-10-15T22:45:34+08:00 → 2026-10-15T22:45:34+08:00 | 1 | not_test | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m ruff check src/ai_intel/domain/enrichment_values.py src/ai_intel/enrichment/contracts.py tests/unit/test_r07_enrichment_contracts.py |
| initial_unit | 2026-10-15T22:45:28+08:00 → 2026-10-15T22:45:34+08:00 | 0 | not_test | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m pytest tests/unit/test_r07_enrichment_contracts.py tests/contract/test_r02_value_contract.py tests/unit/test_r02_dimension_publication_contract.py --no-cov -q |
| seam_format | 2026-10-15T22:49:26+08:00 → 2026-10-15T22:49:26+08:00 | 0 | not_test | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m ruff format --check src tests |
| seam_mypy | 2026-10-15T22:49:26+08:00 → 2026-10-15T22:49:28+08:00 | 0 | not_test | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m mypy src |
| seam_ruff | 2026-10-15T22:49:26+08:00 → 2026-10-15T22:49:26+08:00 | 0 | not_test | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m ruff check src tests |
| seam_unit | 2026-10-15T22:49:23+08:00 → 2026-10-15T22:49:26+08:00 | 0 | not_test | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m pytest tests/unit/test_r07_enrichment_contracts.py tests/contract/test_r02_value_contract.py tests/unit/test_r02_dimension_publication_contract.py tests/contract/test_r04_workbench_projection.py --no-cov -q |
| signal_claim_final_format | 2026-10-15T23:21:28+08:00 → 2026-10-15T23:21:28+08:00 | 0 | not_test | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m ruff format --check src tests |
| signal_claim_final_mypy | 2026-10-15T23:21:29+08:00 → 2026-10-15T23:21:30+08:00 | 0 | not_test | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m mypy src |
| signal_claim_final_ruff | 2026-10-15T23:21:28+08:00 → 2026-10-15T23:21:28+08:00 | 0 | not_test | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m ruff check src tests |
| signal_claim_format_apply | 2026-10-15T23:06:24+08:00 → 2026-10-15T23:06:24+08:00 | 0 | not_test | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m ruff format src/ai_intel/domain/records.py src/ai_intel/domain/enrichment_values.py src/ai_intel/knowledge/persistence.py tests/contract/test_r07_signal_claim_values.py |
| signal_claim_frozen_pg | 2026-10-15T23:22:07+08:00 → 2026-10-15T23:22:34+08:00 | 0 | tests=34, failures=0, errors=0, skipped=0 | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r07_signal_claim_values_pg.py tests/integration/test_r06_catalog_documents_pg.py --no-cov -q --junitxml=D:\wt\r07-core\reports\runs\recovery_r07_core_20261015\signal_claim_frozen_pg.xml |
| signal_claim_frozen_unit | 2026-10-15T23:22:03+08:00 → 2026-10-15T23:22:06+08:00 | 0 | tests=77, failures=0, errors=0, skipped=0 | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m pytest tests/contract/test_r07_signal_claim_values.py tests/contract/test_r02_value_contract.py tests/unit/test_r02_knowledge_publication_contract.py tests/unit/test_r07_enrichment_contracts.py --no-cov -q --junitxml=D:\wt\r07-core\reports\runs\recovery_r07_core_20261015\signal_claim_frozen_unit.xml |
| signal_claim_mypy_initial | 2026-10-15T23:06:24+08:00 → 2026-10-15T23:06:26+08:00 | 0 | not_test | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m mypy src |
| signal_claim_mypy_v2 | 2026-10-15T23:08:42+08:00 → 2026-10-15T23:08:43+08:00 | 0 | not_test | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m mypy src |
| signal_claim_pg_format_apply | 2026-10-15T23:20:18+08:00 → 2026-10-15T23:20:18+08:00 | 0 | not_test | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m ruff format src/ai_intel/knowledge/persistence.py tests/integration/test_r07_signal_claim_values_pg.py |
| signal_claim_pg_initial | 2026-10-15T23:20:20+08:00 → 2026-10-15T23:20:45+08:00 | 0 | tests=34, failures=0, errors=0, skipped=0 | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r07_signal_claim_values_pg.py tests/integration/test_r06_catalog_documents_pg.py --no-cov -q --junitxml=D:\wt\r07-core\reports\runs\recovery_r07_core_20261015\signal_claim_pg_initial.xml |
| signal_claim_pg_ruff_apply | 2026-10-15T23:20:18+08:00 → 2026-10-15T23:20:19+08:00 | 1 | not_test | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m ruff check --fix tests/integration/test_r07_signal_claim_values_pg.py |
| signal_claim_ruff_initial | 2026-10-15T23:06:24+08:00 → 2026-10-15T23:06:24+08:00 | 1 | not_test | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m ruff check src tests |
| signal_claim_static_v2 | 2026-10-15T23:08:42+08:00 → 2026-10-15T23:08:42+08:00 | 0 | not_test | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m ruff check src tests |
| signal_claim_unit_initial | 2026-10-15T23:06:19+08:00 → 2026-10-15T23:06:24+08:00 | 1 | not_test | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m pytest tests/contract/test_r07_signal_claim_values.py tests/contract/test_r02_value_contract.py tests/unit/test_r02_knowledge_publication_contract.py tests/unit/test_r07_enrichment_contracts.py --no-cov -q |
| signal_claim_unit_v2 | 2026-10-15T23:08:39+08:00 → 2026-10-15T23:08:42+08:00 | 0 | not_test | D:\wt\r07-core\backend\.venv\Scripts\python.exe -m pytest tests/contract/test_r07_signal_claim_values.py tests/contract/test_r02_value_contract.py tests/unit/test_r02_knowledge_publication_contract.py tests/unit/test_r07_enrichment_contracts.py --no-cov -q |

全部raw路径：reports/runs/recovery_r07_core_20261015/；frozen_cbm*命令与范围单列JSON/log。费用unknown；本切片0模型/0测绘/0外部来源请求。

## 具体问题与修复

1. 新v3 JSON Schema初稿内联子model schema，VersionInterval嵌套$defs未进入Pydantic根引用表，导致导出KeyError、15failed/62passed。原signal_claim_unit_initial保留。根因是手工拼带本地引用的子schema；改为在根联合已验证结构上限定kind/谓词，不重复嵌入schema。v2复验77pass，最终74d同77pass；未改测试期待或门槛。
2. 新PG测试最初Ruff有import排序及SIM117，--fix只修import、仍exit1日志保留。用并列context修复SIM117，最终Ruff/format/mypy95均0；PG首次34pass，固定74d重跑34pass。
3. 大结构可以合法超过旧ClaimSummary4000字符，若沿用原全JSON显示会使工作台投影校验失败。修复为仅v3显示摘要显式截断、完整JSONB不变。真实PG大版本限制负载验证账本重读等于原结构且显示满足旧合同；旧v1/v2输出不变。
4. 没有把这些修复视为语义验证完成；伪造块身份/跨版本/模型与引文语义不符、更新失效与源选择真实性仍须后续服务检查，当前限制公开保留。

## 审查与后续

本批作者仅登记awaiting_review，需全新未参与实现Agent固定74d独立复跑类型/JSON Schema、PG/权限/实际大字段负例及调用方；reviewer不得改业务代码。通过后主控才能集成限定切片。下一步固定输入loader、永久块/语义验证、逐维事务发布和真实有界worker/API/UI；R06兼容及A公开信号可并行，不将其未验收live传导为通过。

## 修订记录

2026-10-15T23:26:03+08:00 /root 首次真实创建；原失败与初图顺序偏差均保留。首次创建时间以后不改。
