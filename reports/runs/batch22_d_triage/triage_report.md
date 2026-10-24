# batch22 (d) 类失败甄别报告 —— 19 个 integration 测试文件 / 单容器逐文件执行

- 文档首次创建时间：2026-10-25T04:54:42+08:00
- 本次写作开始时间：2026-10-25T04:54:42+08:00
- 最后更新时间：2026-10-25T04:54:42+08:00
- 甄别对象 HEAD：fb0b97c7a（工作区核查 HEAD=4c6ff75ac，该提交只新增 reports 文件，backend 业务代码与 fb0b97c7a 一致，`git show --stat 4c6ff75ac`）
- 输入：`reports/runs/batch21_integration_unlocked/<file>_pf.txt`（逐文件容器输出）
- 只读甄别：未修改业务文件、未运行 pytest、未运行容器。

## 0. 输入核查与数字修正

- 19 个 _pf.txt 实际合计 **72 failed**（任务书写的 74 与文件不符）：7+10+1+19+3+1+6+3+8+2+3+1+1+1+1+2+2+1+0 = 72。
- `test_t05_persistence_and_raw_store_pf.txt` 为 **15 passed, exit=0，无失败**（文件第 5、12-13 行）。
- 重要背景修正："这些测试在宿主 Windows 全量（6080/6253 passed）为绿"的前提**不成立于 real_pg 集成测试**：`reports/runs/batch21_red_zero/full_suite_after_c3.txt` 第 98-101 行显示全部 real_pg 用例在 setup 阶段抛 `UsageError: blocked: DIANZI_TEST_RUN_ID must be a lowercase test identifier`（6080 passed 不含这些用例，83 errors 即它们）。因此不能以"宿主绿"反推"容器内红大概率 A 类"；本报告按 traceback+源码逐例定性。
- 宿主历史绿证据缺失的根因：多数失败由 2026-10-17 提交 `48f96b5ba`（G-C/G-D：revision mode 并入读路径，`backend/src/ai_intel/knowledge/revision_mode.py` 全新引入）引入，而这批 R04-R07 时代的测试及其种子写于 10-15/10-16，之后 real_pg 用例再无成功执行过的宿主全量证据。

## 1. 三条根因家族（覆盖 66/72）

### 家族 1（B，56 例）：revision-mode fail-closed 合同 vs 旧种子无 `data_mode`

- 产品侧（**故意的、有 CR 的变更**）：`48f96b5ba`（2026-10-17）把 `classify_stored_revision_mode` 并入读路径。`backend/src/ai_intel/knowledge/revision_mode.py:13-26`：`source_metadata` 缺 `data_mode` 字符串即抛 `RevisionModeUnavailableError`；`backend/src/ai_intel/api/knowledge_read_service.py:161-171`（`_revision_mode`）、`:371`（event_detail）、`:608`（_evidence_projection）与 `backend/src/ai_intel/api/document_read_service.py:157,284` 全部 fail-closed；HTTP 层 `backend/src/ai_intel/api/knowledge_routes.py:84-87` 把 ValueError 映射为 503 `knowledge_unavailable`。
- 测试侧：R04/R06/R07 时代的 `seed_source_document` / `prepared_submission`（`backend/tests/integration/test_r04_knowledge_api_pg.py:130-148`、`backend/tests/integration/test_r02_knowledge_revisions.py:243`）插入 `document_revisions` 不带 `source_metadata`，落库即 `{}`（列定义 `backend/src/ai_intel/knowledge/models.py:88` server_default `{}`）。而同期之后的新测试（如 `test_r18_current_risk_summary_pg.py:99`）都显式 stamp `{"data_mode": "fixture", ...}`，反证这是种子资产滞后而非环境差异。
- 这不是容器特有：任何 fresh PG 上按当前代码跑这些文件都会同样红；容器只是第一个真正执行它们的环境。
- traceback 直接证据（同一条链）：`test_r07_cvss_authority_scope_fix_pg_pf.txt:29-41`（`metadata = {}` → `stored_source_mode_unavailable`）；`test_r05_vector_persistence_pf.txt:42-51`；`test_r06_catalog_documents_pg_pf.txt:29-38`；`test_r07_enrichment_publication_pg_pf.txt:29-38`。

### 家族 2（B，5 例）：revision-mode 分类失败在公网读路由被映射成 `public_read_unavailable`，冻结语义要求 `not_configured`

- 路由映射：`backend/src/ai_intel/api/public_extension_routes.py:135-138`——`PublicReadUnavailable`→503 `not_configured`（retryable=False）；`(SQLAlchemyError, ValueError)`→503 `public_read_unavailable`（retryable=True）。
- `48f96b5ba` 同时改了 `public_extension_reads.py`（+15 行），`backend/src/ai_intel/api/public_extension_reads.py:228` 对每行 revision 调 `classify_revision_mode(row["source_metadata"], ...)`，未分类模式抛 `RevisionModeUnavailableError`（ValueError 子类，`revision_mode.py:9`），被路由 137 行捕获 → 错码从冻结的 `not_configured` 变成 `public_read_unavailable`。
- 失败：`test_r18_public_read_producer_pg_pf.txt:13-18`（`'public_read_unavailable' == 'not_configured'` 失败，test 文件 `:219-223`）；`test_r18_public_producer_fix1_pg_pf.txt:13-18`、`:31-35`（fix1 文件 import 冻结评审探针 `reports/runs/r18_qualified_root_integration_20261017/original/test_independent_pg.py` 并原样断言，见 `test_r18_public_producer_fix1_pg.py:15-52`）。
- 语义问题（需评审）：存量的"无法分类的已存模式"应属配置态（not_configured，不可重试）还是基础设施态（public_read_unavailable，可重试）？最小产品改法：`public_extension_reads.py:228` 包一层 `try: classify_revision_mode(...) except RevisionModeUnavailableError as error: raise PublicReadUnavailable(...) from error`，即恢复冻结语义；或按变更单更新冻结探针断言。注意 fix1 的探针文件属于盲测/评审材料，改动需走变更记录。

### 家族 3（B，5 例）：种子/驱动未传 `data_mode`，经工具网关变成 `FAILED`，冻结语义要求 `partial`/成功流

- `backend/tests/integration/test_r06_source_excerpt_event_proof_pg.py:74-83`：`SourceResponse(kind, body, url, NOW)` 不传 `data_mode`（默认 None），`persist_source_response`（`source_documents.py:426` + `source_data_mode_metadata` `:82-93`）落库 `source_metadata={}`；Reader 工具读 evidence 时 `tool_gateway.py:608-611` 把 `KnowledgeProjectionError` 映射为 `ToolStatus.FAILED/"tool_output_invalid"`，而业务性 partial（`evidence_not_current_supported`）在 `:731-736`。8 个失败全部是 `'failed' == 'succeeded'/'partial'`（pf :15-20、:57-62、:111-117）。
- `test_r14_read_adapters_pg`：`get_advisory`（`read_adapters.py:436-453`）调 `reader.event_detail` → 家族 1 的异常 → FAILED；冻结语义是 ACL 撤销后 `partial` 且空 revisions（test `:380-383`，pf :13-18）。同文件 `find_changes` 各步（pf 内 first/later/hidden 断言）不经过 event_detail，因此通过——这精确解释了"只有第 380 行的 advisory 断言红"。

## 2. 逐文件结论

### test_r04_api_review_regressions（7 failed / 10 passed）— B（家族 1）
- 证据：pf :14-17、:35-38、:45-48、:55-58、:66-71、:79-84，全部 `503 == 200`，断言点 `test_r04_api_review_regressions.py:81,106,124,143,182`；读路径经 `default_pg_client`（test :27-58）→ `knowledge_routes.py:84-87` 503。
- 佐证"同根因"：同文件 `test_corrupt_saved_reference_member_is_fixed_problem`（期望 503）现因本根因"pass for the wrong reason"（pf 点位 9-11 为 `...`）。
- 修复建议（需评审，测试侧）：`test_r04_knowledge_api_pg.py:seed_source_document`（:130-148）的 `document_revisions.insert().values(...)` 增加 `source_metadata={"data_mode": "fixture"}`（与该文件 `NOW` 常量同级定义即可）；不改任何断言值。

### test_r04_knowledge_api_pg（10 failed / 14 passed）— B（家族 1）
- 证据：pf :13-16（503==200，test :326）、:23-25/:41-44/:51-53/:60-62（`KeyError: 'items'/'revisions'`——响应体是 problem JSON，同一 503 根因的次生形态，test :351,406,430,461,483,683）、:78-81（test :609）、:88-91（test :654）。
- 同文件反证：`test_database_failure_not_empty_success`（monkeypatch 注入 DB 故障期望 503）与 `test_corrupt_verified_evidence_fails_closed`（期望 503）通过——503 机制本身工作正常，红的只是"种子必须带 data_mode"这一新合同。
- 修复建议：同上种子修复（该文件的 `seed_source_document` 同时被 `test_r04_api_review_regressions.py:10-12` import，一处修复清两文件 17 例）。

### test_r04_source_documents（1 failed / 24 passed）— B（独立：产品演化 vs 冻结计数）
- 证据：pf :13-26，`assert 4 == 2`，断言 `test_r04_source_documents.py:254-261`（revision 1 的 evidence 计数）。revision 去重正常（:249-253 的 [1,2,3] 断言通过）。
- 根因：测试冻结于 `df214c664`（2026-10-15）。`git show df214c664:backend/src/ai_intel/ingestion/source_documents.py` 当时 CVSS qualifier evidence 已存在但后续提交（`cb868896c`、`8d48c95ec`、`f3c2e41e3`，10-16/10-17）扩展了 CVSS 事实的 qualifier 链（authority+vectorString，现 `source_documents.py:697-733` 每个_score 事实 1+2 条 evidence）。当前对 vendor fixture（含 cvss，`fixtures/recorded/vllm_vendor_20261015_public.json`）落库 revision 1 = affected_product 1 条 + score 1 条 + 2 条 qualifier = 4 条，确定性、与环境无关。
- 修复建议（需评审，测试侧）：确认现行"CVSS authority/vectorString qualifier 均需独立 evidence 行"合同后，把该断言由 2 更新为 4（或按 locator 维度断言），走变更记录；不是环境问题。

### test_r05_question_api_pg（19 failed / 5 passed）— B（家族 1，经 r05 冻结 legacy 种子）
- 证据：pf 全部 19 条失败为两类——`503 question_processing_failed`（:12-16、:22-26、:30-35、:126-130、:135-140、:155-159、:174-178、:193-197、:203-207、:212-216、:222-226）与 barrier 未到达（`Event.wait(10)` False，:40-45、:231-235、:242-247、:254-258）及错误码错位（:59-64、:78-83、:97-102、:116-121）。
- 根因链：问题管线取证 `retrieval/service.py:211 → read_evidence → _evidence_projection → _revision_mode`（pf :61-71 的同链 traceback 出现在兄弟文件）抛 `stored_source_mode_unavailable`；`answering/service.py:546-549` 把非预期异常统一为 `question_processing_failed`；生成 wire 未被触达，故 barrier 超时、401/403/404 复检类断言全部连锁红。
- 数据源：`question_api` fixture（test :95-161）import `test_r05_vector_persistence` 的 `vector_database` + `public_event_id`；该 fixture 加载**哈希锁定的 0013 时代 legacy 种子**（`test_r05_vector_persistence.py:56-123`，种子 JSON 断言 `source_metadata == {}`，:217），并显式断言 alembic 停在 `0015_catalog_document_metadata`（:222-224）。即：该文件族冻结的语义就是"0013 时代无模式标注的存量行升级后仍可读"，与 48f96b5ba 的 fail-closed 合同**直接冲突**。
- 修复建议（需评审，二选一，不可静默）：(a) 产品侧为 legacy 行定义读取规则（如按迁移纪元回填/降级读），需新 CR；(b) 变更单更新该文件族：种子 stamp `data_mode` 并放宽 `:217` 的 `{}` 断言——但这会改变"legacy 保真"测试目的，必须评审裁决。链上 19 例同源，一次裁决全清。

### test_r05_vector_persistence（3 failed / 8 passed）— A(1) + B(2)
- A：pf :12-18 `assert '0.8.7' == '0.8.2'`（test `:218-221` 查 `pg_extension.extversion`）。容器预装 pgvector 0.8.7，测试冻结 0.8.2。最小适配（fix-harness）：容器镜像/预置层安装 vector 0.8.2（`CREATE EXTENSION vector VERSION '0.8.2'` 需镜像内有该版本 so），或 harness 层提供版本对齐；不允许改断言消化。
- B：pf :20-91、:91-161 两条完整 traceback，`read_evidence → _evidence_projection → stored_source_mode_unavailable`（test :302、:354 经 `retrieval/service.py:211`）。同家族 1 的 legacy-0013 种子冲突（该文件断言 `source_metadata == {}`，:217），与 r05_question 同一裁决。

### test_r06_catalog_documents_pg（1 failed / 20 passed）— B（家族 1）
- 证据：pf :9-38（`metadata = {'canonical_uri': ..., 'full_text_fetched': False, ...}`——catalog 种子写了丰富元数据但无 `data_mode` 键），`read_evidence`，test :118。
- 修复建议：`test_r06_catalog_documents_pg.py` 的 save/paper 种子为 `source_metadata` 增加 `"data_mode": "fixture"`（该文件种子函数被 r06_source_boundary、r07_job_execution synthetic_bounded_paper 等复用，一处修复多文件受益）。

### test_r06_document_api_pg（6 failed / 14 passed）— B（家族 1）
- 证据：pf :26-35（document_detail，`document_read_service.py:284`）、:57-66（list_documents，`:261`）、:88-97、:105-108（503==200，test :188）、:128-137（`metadata = {}`）、:159-168。六例同一根因（catalog 种子缺 data_mode / 显式旧元数据 `{}`）。
- 注意：`test_document_old_metadata_is_explicit_unknown...`（pf :109-137）冻结语义是"旧元数据显式 unknown 不改写历史标题"，在 fail-closed 合同下这类读取现在**必然** 503——该用例的语义需与家族 1 一并评审（旧行可读性）。

### test_r06_source_boundary_pg（3 failed / 3 passed）— B（家族 1）
- 证据：pf :15-38、:47-70、:79-102，三个时间戳参数同一 OSV 种子（`metadata = {'aliases': [...], 'canonical_uri': 'https://api.osv.dev/...', ...}` 无 data_mode），`document_detail`，test :81。
- 修复建议：该文件种子（复用 r06 catalog save/paper 或自有 OSV 种子）stamp `data_mode`。

### test_r06_source_excerpt_event_proof_pg（8 failed / 4 passed）— B（家族 3）+ A（次要，修复后必须处理）
- B：`response()` 不传 data_mode → 落库 `{}` → Reader/Graph 工具读路径 FAILED（pf :15-20、:29-34、:43-48、:57-62、:71-76、:85-90、:99-104、:111-117；断言 test :219、:282、:300）。最小修复（测试侧，需评审）：`response()` 增加 `data_mode="fixture"`（test :74-83，一行）；partial 用例的 `evidence_not_current_supported` 路径（`tool_gateway.py:731-736`）随即恢复。
- A（修复 B 后必现）：`test:38` `RUN = reports/runs/recovery_r06_source_excerpt_event_proof_20261016`，`test:182` `write_text` 直接写仓库树；容器内 `/repo` 只读（所有 pf 的 pytest cache 警告 `[Errno 30] Read-only file system`）。harness 需把 `reports/` 以可写方式挂载，或评审后把 trace 输出改写到 tmp_path（测试侧一行）。

### test_r07_cvss_authority_scope_fix_pg（2 failed / 0 passed）— B（家族 1）
- 证据：pf :9-41、:76-140——完整 traceback，`event_detail → _revision_mode → classify_stored_revision_mode({}) → stored_source_mode_unavailable`，test :87。该文件全部用例都是读 detail，故 2/2 全红（9.67s）。
- 修复建议：其 catalog 种子 stamp `data_mode`。

### test_r07_enrichment_publication_pg（3 failed / 15 passed）— B（家族 1）
- 证据：pf :9-38、:73-70、:139-202，三例均 `event_detail`（test :82、:135、:253），`metadata = {}`。
- 修复建议：同家族种子修复。

### test_r07_input_capabilities_pg（1 failed / 11 passed）— A（共享库串扰：无 schema 隔离 + 无范围选行）
- 证据：pf :9（engine URL 为 `test_dianzi_batch21_c2_free`，**无 search_path options** → public schema 共享库）；traceback `enrichment/inputs.py:269` `EnrichmentInputError("enrichment_source_input_invalid")`，且 `from None` 掩盖原始码（`inputs.py:266-269` 的 `except (OSError, ValidationError, ValueError)`）。
- 根因：单容器逐文件执行中，所有使用 `migrated_engine`（`tests/conftest.py:179-208`，无 schema 隔离）且 run_id=batch21_c2_free 的文件（pytest-1..24 的 r01/r02/r03/r08/r16/t07 等，见 `g_free_integration.txt:2` 组清单）共用同一库；`test_r07_enrichment_inputs_pg.py:21-27 seeded_event` 内 `select(events.c.event_id)` **不带任何范围**取"当前事件"（:25-26），取到的是先前文件遗留的事件；其 revision（经 `prepared_submission` 链创建，`canonical_uri` 为 NULL）触发 `_require_document_row`（`inputs.py:183-191` `source_uri_unavailable`，ValueError）→ 被掩码为 `enrichment_source_input_invalid`。旁证：同逻辑的 `test_r07_enrichment_inputs_pg` 用 schema 隔离的 `catalog_engine`，自跑 12 passed（其 pf 尾部）。
- 修复建议（fix-harness 优先）：(1) harness 为每个 migrated_engine 文件分配独立 run_id/数据库（与其它文件一致），这是最小改动且不影响断言；可选 (2) 测试侧让 `seeded_event` 返回本次 job 精确产出的 event_id（经 event_documents 关联本次 revision），消除对"库内唯一事件"的隐含假设。

### test_r07_job_execution_pg（1 failed / 20 passed）— D（证据不足）
- 证据：pf :13-19，`assert 'partial' == 'failed'`，test :526-528——对 atlas/versions/literature/poc 维度 job 期望 `field_input_budget_exhausted` 型 failed（pf 未给出是哪个维度、未给出 `enrichment_job_steps.error_code`）。父 workflow succeeded（test :519）与 `block_count > 50`（:521-523）均通过，输入冻结正常。
- 已排除：非家族 1（enrichment 输入路径 `inputs.py:144-191` 不检查 data_mode）；引擎为 schema 隔离（pf :9 有 search_path）；预算比较用 UTF-8 字节长（`evidence_selection.py:159-176,230-234`），静态内容确定性。
- 需要的额外证据：单独复跑该文件并打印各维度 `enrichment_job_steps.error_code`/`model_attempts`（或在 :528 前输出 `row["dimension"]` 与 outcome），即可定位是哪条路径把 FAILED 变成了 NOT_FOUND/CONFLICT/PENDING（`job_service.py:352-363` 的映射）。在取得该证据前不给出修复方向，禁止凭猜测改断言。

### test_r14_default_runtime_pg（1 failed / 12 passed）— B（家族 1，附 D 注）
- 证据：pf :12-17，`assert (200 == 200 and 0 == 1)`，test :421-422——`GET /v1/investigations/{job}/tool-runs` 返回 200 但 `items` 为空；同 job `execute_investigation_job == "partial"` 已通过（:411-416）。
- 分析：`evidence_request`（`test_r14_langgraph_workflow_pg.py:118-134`）经 `publish_fact → prepared_submission`（`test_r02_knowledge_revisions.py:226-299`）种子，`save_document_revision` 无 `revision_metadata` → revision 无 data_mode；工作流 TRIAGE 的 `read_evidence` 工具（`workflow_service.py:1279-1298` → `tool_gateway.py:608-611`）在现合同下必然 FAILED，测试冻结时该读是成功的。`investigation_routes.py:316-338` 的 listing 不筛选 status，items=0 说明**没有任何 operation 行落库**（含 reserved），即工作流在首个 reserve 之前终止——精确机制（actor 校验/租约/检查点子进程哪一步）需一次带 stop_reason 的复跑确认（D 注），但种子违约是确定存在的 B 面修复点。
- 修复建议：先做家族 1 的共享种子修复（`prepared_submission` 内 `save_document_revision(..., revision_metadata={"data_mode": "fixture"})`），复跑观察；若仍 0 行，按 D 注取证。

### test_r14_read_adapters_pg（1 failed / 24 passed）— B（家族 1/3）
- 证据：pf :13-18，`ToolStatus.FAILED == 'partial'`，test :380-383（**advisory** 断言，非 find_changes）。`_advisory`（`read_adapters.py:436-453`）调 `reader.event_detail` → 家族 1 异常 → `tool_gateway.py:608-611` FAILED；冻结语义为 ACL 撤销后 partial+空 revisions（`:446-452` 的 incomplete 分支）。同测试的 first/later/hidden 断言不经过 event_detail，全部通过——与点位完全吻合。
- 修复建议：共享种子修复（`public_fact` 链）后，advisory 走 incomplete 分支恢复 partial。

### test_r18_api_key_post_lock_time_pg（2 failed / 2 passed）— A（时间炸弹：绝对期限 vs 墙钟）
- 证据：pf :25-45、:64-84——`issue_key`（test :48-51、:81-84）内部 `lock_authenticated_principal(connection, credential, now)`，`now = datetime(2026,10,24,18:55,...)`（真实墙钟，pf :27、:66）→ `lock_session_scope`（`auth_state.py:93`）→ `actor_references.py:210` `SessionExpiredError`。
- 根因：`pg_case` fixture（`test_r18_api_key_credentials_pg.py:156-164`）写入 `issued_at=NOW`、`expires_at=NOW+1day`，而 `NOW = datetime(2026,10,16,1,0,12 UTC)`（:42，冻结时刻）。会话已于 **2026-10-17 01:00 UTC 过期**；容器跑在 2026-10-24 → 用真实墙钟锁会话必炸。通过的两个用例（:127-127、:176-176）显式传 pinned `NOW`/`server_now` 作假时钟，不触发真实期限校验——与红绿分布完全一致。
- 修复建议（fix-test/harness，一行，不改断言）：`pg_case` 里 session 的 `issued_at/expires_at` 改为相对真实时钟（`now = datetime.now(UTC); expires_at=now+timedelta(days=1)`），与 `test_r14_langgraph_workflow_pg.py:112`（`now+10min`）的正确写法对齐。此类"冻结绝对时间戳"模式建议在本仓库一并盘点（其它以 NOW 派生 expires_at 且用真实墙钟校验的用例都会在同一天集体爆）。

### test_r18_public_producer_fix1_pg（2 failed / 26 passed）— B（家族 2）
- 证据：pf :13-18（`'public_read_unavailable' == 'not_configured'`，回溯指向冻结探针 `test_r18_public_read_producer_pg.py:223`）、:24-35（同错码断言，回溯指向 `reports/runs/r18_qualified_root_integration_20261017/original/test_independent_pg.py:102`；fix1 文件 import 该探针，`test_r18_public_producer_fix1_pg.py:15-52`）。
- 根因与修复（需评审，产品侧一行或探针变更单）：见家族 2。若走产品修复：`public_extension_reads.py:228` 将 `RevisionModeUnavailableError` 包装为 `PublicReadUnavailable`，恢复 `not_configured`（retryable=False）语义；若走测试修复：属盲测/评审材料变更，必须走变更记录并统一重测对照。

### test_r18_public_read_producer_pg（1 failed / 8 passed）— B（家族 2，含裸 live 模式子例）
- 证据：pf :13-18，test :218-223。`seed_intelligence(mode="live")`（test :130-140）stamp 的是 `{"data_mode": "live"}` **无** `data_mode_policy_version`——按现行分类器（`revision_mode.py:20-26`）live 必须带 `TRUSTED_SOURCE_MODE_POLICY` 才可信，故抛未分类异常 → 错码偏差，同家族 2。
- 修复建议：同家族 2 裁决；若产品侧修复则两个文件三例同时恢复。

### test_t05_persistence_and_raw_store（0 failed，15 passed，exit=0）— 无需处理
- 证据：pf :5、:12-13。唯一注意点：它也用 `migrated_engine`（共享库），绿的原因是不做"库内唯一行"假设且不走 event_detail——提示共享库模式本身可行，问题只在隐含假设。

## 3. 汇总表

| 文件 | 失败数 | 分类分布 | 建议动作 |
|---|---|---|---|
| test_r04_api_review_regressions | 7 | B×7 | fix-test 需评审（种子 stamp data_mode，与 r04_knowledge 共用 helper） |
| test_r04_knowledge_api_pg | 10 | B×10 | fix-test 需评审（seed_source_document +data_mode） |
| test_r04_source_documents | 1 | B×1 | fix-test 需评审（evidence 计数 2→4，产品合同演化） |
| test_r05_question_api_pg | 19 | B×19 | 需评审裁决（legacy-0013 可读性 vs fail-closed，二选一，禁静默） |
| test_r05_vector_persistence | 3 | A×1 + B×2 | fix-harness（pgvector 钉 0.8.2）+ 与 r05 同一裁决 |
| test_r06_catalog_documents_pg | 1 | B×1 | fix-test 需评审（catalog 种子 +data_mode） |
| test_r06_document_api_pg | 6 | B×6 | fix-test 需评审（同上） |
| test_r06_source_boundary_pg | 3 | B×3 | fix-test 需评审（OSV 种子 +data_mode） |
| test_r06_source_excerpt_event_proof_pg | 8 | B×8（+A 次要） | fix-test 需评审（response() +data_mode）+ harness（reports 可写或 trace 改 tmp） |
| test_r07_cvss_authority_scope_fix_pg | 2 | B×2 | fix-test 需评审（种子 +data_mode） |
| test_r07_enrichment_publication_pg | 3 | B×3 | fix-test 需评审（种子 +data_mode） |
| test_r07_input_capabilities_pg | 1 | A×1 | fix-harness（migrated_engine 文件独立库）或 fix-test（事件范围选择） |
| test_r07_job_execution_pg | 1 | D×1 | 不确定——需维度 error_code 复跑取证后再定 |
| test_r14_default_runtime_pg | 1 | B×1（D 注） | fix-test 需评审（prepared_submission +data_mode）；0 行机制需复跑确认 |
| test_r14_read_adapters_pg | 1 | B×1 | fix-test 需评审（public_fact 链种子 +data_mode） |
| test_r18_api_key_post_lock_time_pg | 2 | A×2 | fix-test/harness（session 期限改相对真实时钟，一行） |
| test_r18_public_producer_fix1_pg | 2 | B×2 | fix-product 需评审（public_extension_reads.py:228 包装为 PublicReadUnavailable）或探针变更单 |
| test_r18_public_read_producer_pg | 1 | B×1 | 同上（与 fix1 同一裁决） |
| test_t05_persistence_and_raw_store | 0 | — | 无（绿） |
| **合计** | **72** | A×4，B×66，D×2 | |

## 4. 修复路径与预计可直接修复数

1. **一个系统性测试侧修复（种子 stamp `data_mode:"fixture"`）**，覆盖家族 1+3 的 14 个文件、59 例：`test_r04_knowledge_api_pg.seed_source_document`、`test_r02_knowledge_revisions.prepared_submission`、`test_r06_catalog_documents_pg` 种子、`test_r06_source_excerpt_event_proof_pg.response()`。均为新增写入字段，不改任何断言值；但触及冻结测试语义，按 AGENTS 需评审/变更记录后统一重测。
2. **一个产品侧一行候选（需评审）**：`public_extension_reads.py:228` 包装 `RevisionModeUnavailableError` → 恢复 3 例（家族 2）冻结语义。
3. **两个 harness/测试侧独立修复（不改语义）**：pgvector 钉 0.8.2（1 例）+ r18 session 相对时限（2 例）= 3 例；`migrated_engine` 文件独立库或事件范围修复（1 例）。
4. **需评审裁决**：r05 legacy-0013 可读性（21 例随裁决方案落地清零）；r04_source_documents 计数（1 例）。
5. **证据不足**：r07_job_execution（1 例）+ r14_default_runtime 的 0 行机制 D 注。

预计可直接修复（1+2+3 项落地并通过复跑）：**66 例**；剩余 6 例中 5 例随 r05/r04_source_documents 评审裁决可清，1 例（r07_job_execution）需先取证。另一个执行层事实：即便全部修复，`test_r06_source_excerpt_event_proof_pg` 的 `trace()` 写 `reports/` 仍会被只读容器拦截，需 harness 同步把仓库目录以可写挂载（或评审改为 tmp_path），否则该文件修复后会以 A 类再红。
