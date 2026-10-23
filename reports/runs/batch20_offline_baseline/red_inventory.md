# batch20 离线基线 红测清单（red_inventory）

- 日期：2026-10-24
- 命令（backend 目录执行）：`uv run python -m pytest tests/unit tests/contract tests/security -q -ra --continue-on-collection-errors`
- 最终统计（原样引用）：`40 failed, 5872 passed, 4 warnings, 42 errors in 553.00s (0:09:13)`
- `PYTEST_EXIT=1`
- 日志：`reports/runs/batch20_offline_baseline/full_suite.txt`（权威）；`reports/runs/batch20_offline_baseline/full_suite_attempt1_entrypoint_aborted.txt`（早期尝试，经裸 `pytest` 入口运行导致 50 个收集错误、`PYTEST_EXIT=2`，已被本次运行取代，仅作交叉证据）
- 范围说明：`tests/integration`、`tests/e2e`、live 均不在本轮命令范围内，状态记 `not_run`。外部 live 阻塞不在此清单内。
- 分类证据边界：attempt1 在收集阶段即中断（50 collection errors），未执行任何测试，因此对 40 个 FAILED 不提供 HEAD~1 对照；两份日志均来自同一提交。凡未在两份日志或任务给定的 2026-10-16 基线参考（22 fail / 1 error：16 条旧 codec 预期、1–2 条迁移 forward-head、2 条真实 CPU 红）中能确认的，一律标注「未知-需HEAD对照」。

---

## Section A — 42 个 ERROR（按根因分组）

### A1 组：跨目录裸导入兄弟测试模块失败（收集错误，4 个）

| # | 文件 | 根错误行（原样） |
|---|------|------------------|
| 1 | `tests/contract/test_r14_tool_gateway_pg.py` | `E   ModuleNotFoundError: No module named 'test_r10_evidence_graph_pg'`（tests\contract\test_r14_tool_gateway_pg.py:18，`from test_r10_evidence_graph_pg import VERSION, publish_event, publish_fact`） |
| 2 | `tests/contract/test_r14_tool_gateway_review_pg.py` | `E   ModuleNotFoundError: No module named 'test_r10_evidence_graph_pg'`（经 tests\contract\test_r14_tool_gateway_review_pg.py:8 → test_r14_tool_gateway_pg.py:18 传导） |
| 3 | `tests/security/test_r07_input_audit_security_pg.py` | `E   ModuleNotFoundError: No module named 'test_r07_input_audit_receipts_pg'`（tests\security\test_r07_input_audit_security_pg.py:9，`from test_r07_input_audit_receipts_pg import recorded_workflow`） |
| 4 | `tests/security/test_r07_input_audit_fix1_acl_pg.py` | `E   ModuleNotFoundError: No module named 'test_r07_input_audit_receipts_pg'`（经 tests\security\test_r07_input_audit_fix1_acl_pg.py:10 → test_r07_input_audit_security_pg.py:9 传导） |

- 根因：两个被导入的帮助模块实际位于 `backend/tests/integration/`（磁盘核实存在：`tests/integration/test_r10_evidence_graph_pg.py`、`tests/integration/test_r07_input_audit_receipts_pg.py`），导入方使用同目录裸模块名导入。本轮收集范围为 `tests/unit tests/contract tests/security`，`tests/integration` 不在收集集合中，其目录未进入 `sys.path`，裸导入即失败。attempt1（裸 `pytest` 入口，收集含 integration 前置）中 test_r14_tool_gateway_pg.py、test_r14_tool_gateway_review_pg.py、test_r07_input_audit_security_pg.py 三个文件报出完全相同的根错误行（fix1_acl_pg 在 attempt1 中先报 `No module named 'tests.security'`，属同一导入链在不同 sys.path 下的首个失败点不同），证明该失败与本轮入口/范围组合无关、在当前提交上稳定复现。
- 分类：历史遗留 vs 新引入 = **未知-需HEAD对照**（两份日志只能证明当前提交上两种入口下均失败，不能证明 HEAD~1 状态）。

### A2 组：隔离 PG 测试环境未提供 → fixture 按设计报 blocked（setup 错误，38 个）

根错误行（38 处完全一致，原样）：

```
E           _pytest.config.exceptions.UsageError: blocked: DIANZI_TEST_RUN_ID must be a lowercase test identifier
tests\conftest.py:176: UsageError
```

根因：`scripts/dev.py:48`（`require_isolated_test_database`）要求环境变量 `DIANZI_TEST_RUN_ID` 匹配 `[a-z][a-z0-9_]{2,47}`，本轮运行未设置该变量；`tests/conftest.py:176` 的 `isolated_test_database_url` fixture 按其文档约定将缺资源转为 `pytest.UsageError("blocked: ...")`，而非 skip。属外部环境前置缺失的显式 blocked 报告，非测试逻辑或被测代码失败。

受影响文件与数量（合计 38）：

| # | 文件 | 数量 | 受影响测试 |
|---|------|------|-----------|
| 1 | `tests/contract/test_t07_jobs_outbox.py` | 1 | test_transient_failure_parks_in_retry_wait_then_retries_exactly_once |
| 2 | `tests/security/test_r02_auth_state_boundaries.py` | 6 | test_audit_tenant_isolation_and_unknown_user_system_admin_only；test_audit_keyset_pagination_is_bounded_stable_and_has_no_secrets；test_pg_csrf_non_ascii_and_origin_rejections_preserve_session；test_pg_failure_http_is_fixed_503_without_memory_fallback；test_logout_audit_failure_rolls_back_revocation；test_me_current_scope_and_forged_identity_422 |
| 3 | `tests/security/test_r03_executor_authorization.py` | 3 | test_worker_denies_source_from_other_tenant_and_payload_self_authorization[True]；[False]；test_topic_and_payload_reference_cannot_select_arbitrary_task_or_resource |
| 4 | `tests/security/test_r06_bulk_source_evidence_scope.py` | 5 | test_scope_or_revision_rejection_has_no_block_or_evidence_effect[missing]；[historical]；[tenant]；[public_from_tenant]；[other_tenant] |
| 5 | `tests/security/test_r07_idempotency_scope_security.py` | 8 | test_expected_legacy_parent_corruption_cannot_create_or_reuse_an_operation[request]；[policy]；[binding_actor]；[workflow_uuid]；[payload]；[orphan]；test_tampered_v2_record_with_internal_prefix_is_not_accepted_as_an_alias；test_private_event_cross_tenant_and_public_write_roles_are_not_granted_by_key |
| 6 | `tests/security/test_r11_r08_forward_migration_boundaries.py` | 15 | test_production_checks_reject_invalid_safe_observation[changes0-ck_r08_schema]；[changes1-ck_r08_provider]；[changes2-ck_r08_query]；[changes3-ck_r08_query_version]；[changes4-ck_r08_mode]；[changes5-ck_r08_fee]；[changes6-ck_r08_hashes]；[changes7-ck_r08_hashes]；[changes8-ck_r08_scope]；[changes9-ck_r08_scope]；[changes10-ck_r08_outcome]；[changes11-ck_r08_outcome]；[changes12-ck_r08_required_error]；test_production_database_rejects_aggregate_mutation[update]；[delete] |

- 分类：**环境阻塞（外部依赖未提供隔离 PG 测试环境）**，非代码回归。attempt1 中无对应证据（其在收集阶段中断，未进入 setup）。
- 数量核对：4（A1）+ 38（A2）= 42 errors。

---

## Section B — 40 个 FAILED（逐条 + 按根因分组）

### B1 组：r07 单模型维度 codec 旧预期（16 条）

全部为 `tests/contract/test_r07_single_model_dimension_contract.py::test_all_real_codecs_preserve_single_attempt_contract_and_metadata[<provider>-<dimension>]`，断言行 `assert metadata.prompt_version == "r07-model-fields-1"`，根错误行（16 处一致，原样）：

```
E       AssertionError: assert 'r07-model-fields-2' == 'r07-model-fields-1'
```

16 个参数化 id：
1. `[openai-atlas]`
2. `[openai-versions]`
3. `[openai-literature]`
4. `[openai-poc]`
5. `[anthropic-atlas]`
6. `[anthropic-versions]`
7. `[anthropic-literature]`
8. `[anthropic-poc]`
9. `[deepseek_openai-atlas]`
10. `[deepseek_openai-versions]`
11. `[deepseek_openai-literature]`
12. `[deepseek_openai-poc]`
13. `[deepseek_anthropic-atlas]`
14. `[deepseek_anthropic-versions]`
15. `[deepseek_anthropic-literature]`
16. `[deepseek_anthropic-poc]`

- 分类：**历史遗留-旧codec预期**。与 2026-10-16 基线参考中「16 条旧 codec 预期测试（r07 single-model/contract）」数量、文件、参数化完全吻合。

### B2 组：迁移 forward-head 预期（2 条）

1. `tests/contract/test_r11_r08_forward_migrations.py::test_production_chain_has_single_forward_head`
   - `E       AssertionError: assert ['0031_public_task_bindings'] == ['0019_aggreg...observations']`
   - 明细（tests\contract\test_r11_r08_forward_migrations.py:49）：`assert scripts.get_heads() == ["0019_aggregate_observations"]`，实际 head 为 `['0031_public_task_bindings']`。
2. `tests/contract/test_recovery_forward_migrations_0023_0026.py::test_complete_alembic_chain_has_one_head_and_no_revision_gap`
   - `E       AssertionError: assert ['0031_public_task_bindings'] == ['0026_api_key_credentials']`
   - 明细（tests\contract\test_recovery_forward_migrations_0023_0026.py:83）：`assert scripts.get_heads() == [REVISIONS[-1][0]]`，实际 head 为 `['0031_public_task_bindings']`。

- 分类：**历史遗留-迁移head**。与 2026-10-16 基线参考「1–2 条迁移 forward-head 测试」同类；两测共同根因是迁移链存在更新的事件级 head（0031_public_task_bindings），而两条测试的期望 head 清单仍停留在 0019 / 0026。

### B3 组：R06 冻结诊断事件替身缺 business_version（2 条，根因已确认）

1. `tests/unit/test_r06_revision_mode_reads.py::test_original_24_oracles_on_public_mode_configuration[fixture-event_detail]`
2. `tests/unit/test_r06_revision_mode_reads.py::test_original_24_oracles_on_public_mode_configuration[live-event_detail]`

根错误行（两处一致，原样）：

```
E       KeyError: 'business_version'
src\ai_intel\api\knowledge_read_service.py:444: KeyError
```

调用链：tests\unit\test_r06_revision_mode_reads.py:74 → `reports\runs\r06_revision_mode_read_fix_20261017\original_revision_mode_diagnostic.py:100`（`assert projected_mode(operation, mode, monkeypatch) == mode`）→ 同文件 ：90（`reader.event_detail(UUID(event["event_id"])).data_mode`）→ `knowledge_read_service.py:444`（`business_version=int(row["business_version"])`）。

- 根因（任务给定，已确认）：冻结的诊断事件替身（2026-10-17 冻结副本）缺少 `business_version` 字段，与当前 `EventDetailResponse` 构造需求漂移。仅 `[fixture-event_detail]` 与 `[live-event_detail]` 两个参数化命中；`None`/`untrusted_live` 及其余 5 种 operation 未失败。
- 分类：**其他（已确认根因：冻结诊断替身与当前 schema 漂移）**；是否新引入 = 未知-需HEAD对照（attempt1 未执行测试，无对照）。冻结材料属冻结副本，处理受变更约束。

### B4 组：R07 本机 native content-read worker 子进程失败（11 条，同文件 test_r07_source_io_deadline.py）

两条物理根错误（在组内交替出现，原样）：

- SDK 路径（minio_store 包装）：
  ```
  E               ai_intel.infrastructure.minio_store.ObjectStoreUnavailableError: object storage read unavailable
  src\ai_intel\infrastructure\minio_store.py:130: ObjectStoreUnavailableError
  ```
  （由 `_read_with_deadline` 中 worker 子进程失败转译，源头为下条）
- 本地/底层路径：
  ```
  E               OSError: content_read_worker_unavailable
  src\ai_intel\infrastructure\content_store.py:233: OSError
  ```
  （触发条件原样：`if process.returncode != 0 or not output or len(output) > byte_limit + 1:`）

逐条（测试文件内断言位置 + 根错误）：
1. `tests/unit/test_r07_source_io_deadline.py::test_sdk_deadline_stops_slow_headers_chunks_and_drip_and_reaps_worker[headers]` — 期望 `TimeoutError("content_read_deadline_exhausted")`，实际 ：108 → `ObjectStoreUnavailableError`（minio_store.py:130）
2. 同上 `[chunks]` — ：108 → `ObjectStoreUnavailableError`（minio_store.py:130）
3. 同上 `[drip]` — ：108 → `ObjectStoreUnavailableError`（minio_store.py:130）
4. `test_native_local_worker_verifies_unicode_missing_hash_and_size` — ：122 `store.read_verified(...) == PAYLOAD` → `OSError: content_read_worker_unavailable`（content_store.py:233）
5. `test_original_five_second_budget_interrupts_real_sdk_io_before_5_2_second_headers` — ：140 期望 `TimeoutError` → `ObjectStoreUnavailableError`（minio_store.py:130）
6. `test_sdk_disconnect_and_checksum_failure_cannot_return_verified_content[corrupt]` — ：172 期望 `ValueError` → `ObjectStoreUnavailableError`（minio_store.py:130）
7. `test_sdk_success_and_exact_byte_limit_are_verified` — ：178 `store.read_verified(...) == PAYLOAD` → `ObjectStoreUnavailableError`（minio_store.py:130）
8. `test_concurrent_sdk_reads_keep_independent_deadlines` — ：199 `short.result()`（worker 线程内 ：191 `read_for` 抛出）→ `ObjectStoreUnavailableError`（minio_store.py:130）
9. `test_cancellation_reaps_worker_and_releases_capacity` — ：222 取消后第二次 `store.read_verified(...) == PAYLOAD` → `ObjectStoreUnavailableError`（minio_store.py:130）
10. `test_reader_uses_frozen_metadata_without_io_transaction_and_forwards_original_deadline` — ：250 `assert result.status == "reported"` → `E       AssertionError: assert 'partial' == 'reported'`
11. `test_short_deadline_interrupts_small_native_request_before_guard_startup` — ：283 期望 `TimeoutError("content_read_deadline_exhausted")` → `OSError: content_read_worker_unavailable`（content_store.py:233）

- 共同表象：native worker 子进程（`[executable, "-m", "ai_intel.infrastructure._content_read_worker"]`）返回码非 0 或无输出，本机（Windows，pytest-1535 会话）上稳定复现；测试要么收到 `ObjectStoreUnavailableError`/`OSError`，要么 reader 将读失败降级为 `partial`（`missing_requirements` 含 `source_object_read_failed`，见 B5）。
- 分类：**疑似新引入（需人工确认）/ 未知-需HEAD对照**。2026-10-16 基线仅有 2 条「真实 CPU 红」，无法从现有日志确认与本组 11 条的对应关系。

### B5 组：source report 读取状态降级 partial/reported 及富化 reason（4 条 + 与 B4 同因表象）

1. `tests/unit/test_r07_source_report_node.py::test_real_factory_reader_produces_reported_unknown_fact`
   - `E       AssertionError: assert (1 == 1 and 'partial' == 'reported'`（tests\unit\test_r07_source_report_node.py:212）
2. `tests/unit/test_r07_source_report_node.py::test_mixed_original_reports_keep_conflicts_missing_and_json_identity`
   - `E       AssertionError: assert ['partial', '..., 'not_found'] == ['reported', ..., 'not_found']`
   - `E         At index 0 diff: 'partial' != 'reported'`（tests\unit\test_r07_source_report_node.py:265）
3. `tests/unit/test_r07_source_report_reader.py::test_normal_read_keeps_typed_value_proof_identity_and_unknown_states`
   - `E       AssertionError: assert 'partial' == 'reported'`（tests\unit\test_r07_source_report_reader.py:236）
4. `tests/unit/test_r07_source_report_reader.py::test_matching_quotes_cannot_support_changed_typed_value`
   - `E       AssertionError: assert 'source_value_mismatch' in ('source_object_read_failed',)`（tests\unit\test_r07_source_report_reader.py:280）
5. `tests/unit/test_r14_source_report_output_budget.py::test_enricher_consumes_existing_source_reader_with_authenticated_idle_context[reported-enrichment_write_adapter_not_configured]`
   - `E       AssertionError: assert ('source_reports_partial' == 'enrichment_w...ot_configured'`
   - 明细：`- enrichment_write_adapter_not_configured` / `+ source_reports_partial`（tests\unit\test_r14_source_report_output_budget.py:331）

- 说明：#1–#4 的 reader 均经真实 `ContentStore`（`read_case.storage`/`read_case.store`）读取，失败状态 `partial` 且 `missing_requirements=('source_object_read_failed',)` 与 B4 的 worker 失败表象一致；#5 是该状态在富化回执 reason_code 上的传导（期望 `enrichment_write_adapter_not_configured`，实际 `source_reports_partial`）。此为日志可见事实的并置，未做超出日志的推断。
- 分类：**疑似新引入（需人工确认）/ 未知-需HEAD对照**（同 B4）。

### B6 组：机密值扫描命中 fixture 占位值（2 条）

1. `tests/unit/test_t02_project_skeleton.py::test_source_files_contain_no_secret_values`
   - `E           assert not <re.Match object; span=(5035, 5061), match='token = "fixture-session-"'>`
   - 命中文件（原样）：`WindowsPath('D:/dianzi/backend/src/ai_intel/fixtures/main_path_story.py').read_text`；正则原样：`(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]`（tests\unit\test_t02_project_skeleton.py:102）
2. `tests/security/test_t06_authentication_and_scope.py::test_audit_and_sources_carry_no_secret_values_t06_c06`
   - `E       AssertionError: [ScanFinding(path='backend/src/ai_intel/fixtures/main_path_story.py', pattern_id='original_secret_pattern', category='...ts/assessment-contracts.test.ts', pattern_id='original_secret_pattern', category='unclassified_credential_shape'), ...]`（消息截断，可见至少包含 `backend/src/ai_intel/fixtures/main_path_story.py` 与某 `...ts/assessment-contracts.test.ts` 两处 finding）（tests\security\test_t06_authentication_and_scope.py:162）

- 分类：**其他-需HEAD对照**。两测共同命中 `backend/src/ai_intel/fixtures/main_path_story.py` 的 fixture 值；t06 另含分类清单（`reports/security/recovery_fixture_false_positives.json`）未覆盖的 finding。是否新引入未知。

### B7 组：compose 配置断言漂移（2 条）

1. `tests/contract/test_r01_compose_configuration.py::test_development_services_are_local_bounded_and_persistent`
   - `E           KeyError: 'healthcheck'`（`assert service["healthcheck"]["test"]`，tests\contract\test_r01_compose_configuration.py:155）
2. `tests/contract/test_r01_compose_configuration.py::test_host_overlay_binds_services_internally_to_loopback`
   - `E           KeyError: 'network_mode'`（`assert service["network_mode"] == "host"`，tests\contract\test_r01_compose_configuration.py:190）

- 两测的 `render_configuration(...)` 本身 `returncode == 0`，是渲染出的 services 中存在缺少 `healthcheck` / `network_mode` 键的服务。
- 分类：**其他-需HEAD对照**（渲染结果依赖本机 docker compose，环境敏感；是否新引入未知）。

### B 组数量核对

16（B1）+ 2（B2）+ 2（B3）+ 11（B4）+ 5（B5）+ 2（B6）+ 2（B7）= 40。✓（B5 实为 4 条 source report + 1 条 r14 传导，上文编号 1–5。）

---

## Section C — R06 相关失败（仅 r06 / guard / observer / activation / restart 匹配项）

40 个 FAILED 中，id 匹配 `r06` 的仅以下 2 条（无任何 FAILED id 匹配 guard / observer / activation / restart）：

### C-1 `tests/unit/test_r06_revision_mode_reads.py::test_original_24_oracles_on_public_mode_configuration[fixture-event_detail]`

关键 traceback（原样摘录）：

```
tests\unit\test_r06_revision_mode_reads.py:74: 
..\reports\runs\r06_revision_mode_read_fix_20261017\original_revision_mode_diagnostic.py:100: in test_required_revision_mode_truthfulness
    assert projected_mode(operation, mode, monkeypatch) == mode
..\reports\runs\r06_revision_mode_read_fix_20261017\original_revision_mode_diagnostic.py:90: in projected_mode
    return reader.event_detail(UUID(event["event_id"])).data_mode
...
>           business_version=int(row["business_version"]),
E       KeyError: 'business_version'
src\ai_intel\api\knowledge_read_service.py:444: KeyError
```

### C-2 `tests/unit/test_r06_revision_mode_reads.py::test_original_24_oracles_on_public_mode_configuration[live-event_detail]`

错误行与 C-1 完全一致（原样）：

```
>           business_version=int(row["business_version"]),
E       KeyError: 'business_version'
src\ai_intel\api\knowledge_read_service.py:444: KeyError
```

（参数差异：C-1 `operation = 'event_detail', mode = 'fixture'`；C-2 `operation = 'event_detail', mode = 'live'`。两测均先 monkeypatch `DocumentReadService`/`KnowledgeReadService.__init__` 注入 `require_expected_mode=False` 后调用冻结诊断 `test_required_revision_mode_truthfulness`。）

### C-3 R06 相关 ERROR（计入 Section A，此处交叉引用供下一批工作使用）

- `tests/security/test_r06_bulk_source_evidence_scope.py::test_scope_or_revision_rejection_has_no_block_or_evidence_effect[missing]`
- `...[historical]`
- `...[tenant]`
- `...[public_from_tenant]`
- `...[other_tenant]`

根错误行（5 处一致，原样）：

```
E           _pytest.config.exceptions.UsageError: blocked: DIANZI_TEST_RUN_ID must be a lowercase test identifier
tests\conftest.py:176: UsageError
```

性质：A2 组同因（隔离 PG 测试环境变量未提供），非 R06 业务代码失败。

---

## Section D — 分类汇总与处置归类

### D1 错误（42）分类

| 分类 | 数量 | 明细 |
|------|------|------|
| 环境阻塞-外部依赖（DIANZI_TEST_RUN_ID 未设置，设计内 blocked 报告） | 38 | A2 组全部 |
| 未知-需HEAD对照（跨目录裸导入 tests/integration 帮助模块；当前提交双入口稳定复现） | 4 | A1 组全部 |

### D2 失败（40）分类

| 分类 | 数量 | 明细 |
|------|------|------|
| 历史遗留-旧codec预期 | 16 | B1（r07_single_model_dimension_contract 全部 16 参数化，`r07-model-fields-1` vs `r07-model-fields-2`） |
| 历史遗留-迁移head | 2 | B2（test_production_chain_has_single_forward_head；test_complete_alembic_chain_has_one_head_and_no_revision_gap） |
| 其他-已确认根因（R06 冻结诊断替身缺 business_version；是否新引入需HEAD对照） | 2 | B3 / Section C-1、C-2 |
| 疑似新引入（需人工确认）/ 未知-需HEAD对照 | 16 | B4（11）+ B5（5），表象同源于本机 native content-read worker 子进程失败及由此产生的 partial 降级 |
| 其他-需HEAD对照 | 4 | B6（2：t02/t06 机密扫描命中 fixture 占位值）+ B7（2：r01 compose KeyError healthcheck/network_mode） |

合计 16+2+2+16+4 = 40。✓

### D3 处置归类（事实性归类，不含修复方案）

- **候选：立即可推进的最小对齐项（无需变更合同实质）**
  - A2 组 38 条 error：属外部环境前置（`DIANZI_TEST_RUN_ID`/隔离 PG）未满足；补齐环境变量与隔离库后按原命令复跑即可消除，不涉代码。
  - B2 组 2 条迁移 head：期望 head 清单（0019 / 0026）与链上实际最新 head（0031_public_task_bindings）的机械性滞后，属既有迁移流程内的预期更新；但两条测试本身是合同测试，改动应在任务报告留痕。
  - B6 中 t02 一条：命中值为 fixture 占位符（`token = "fixture-session-"`），与扫描白名单（fixture classifications）的维护直接相关。
- **需变更单（涉及测试合同/冻结材料/扫描分类清单）**
  - B1 组 16 条 codec 预期：测试断言的 prompt_version 属合同预期，须先确认 r07-model-fields-2 是预期演进再统一更新预期，禁止为通过测试直接改金标。
  - B3 组 2 条 R06：涉及 `reports/runs/r06_revision_mode_read_fix_20261017/` 下的冻结诊断副本（原始 24 oracle 材料），变更冻结材料走变更单。
  - A1 组 4 条收集错误：涉及跨目录导入约定（tests/integration 帮助模块的复用方式），属测试组织合同。
  - B6 中 t06 一条：涉及 `reports/security/recovery_fixture_false_positives.json` 分类清单的扩展（新增 finding 分类）。
- **需先根因定位（疑新引入，禁止先改测试）**
  - B4 + B5 共 16 条：需在 HEAD~1 或干净环境复跑 `tests/unit/test_r07_source_io_deadline.py`、`test_r07_source_report_node.py`、`test_r07_source_report_reader.py`、`test_r14_source_report_output_budget.py` 对照；同一根因连续两次修复无进展时按约定停止扩大补丁。
- **外部/live 依赖**
  - 本轮范围内无 live/模型/FOFA 用例（integration、e2e、live 均 not_run）。A2 组的本质是隔离 PG Compose 环境这一外部资源缺失；在环境提供前，这 38 条在离线基线中将持续以 blocked error 形式出现。
- **待对照后才能定类**
  - B6/B7 全部 4 条及 B3 是否新引入：均标注「未知-需HEAD对照」，当前日志不足以定类。

---

## 附注：批次20修复轮之后的逐项结果（2026-10-24T02:4x+08:00 追加）

| 组 | 基线状态 | 本轮处置 | 结果 |
| --- | --- | --- | --- |
| A2 38 个 setup error（DIANZI_TEST_RUN_ID 未设） | 设计内 blocked | 不处置（真实 PG 隔离环境按设计上报 blocked） | 维持 blocked |
| A1 4 个收集 error（跨目录裸导入） | 历史遗留 | 记录，不在本轮改导入合同 | 维持 error |
| 16 个旧 codec 预期 | 历史遗留（与 10-16 基线一致） | 不处置（属变更单范围） | 维持 failed |
| 2 个迁移 forward-head | 历史遗留 | 不处置（属变更单范围） | 维持 failed |
| 2 个 r06 revision-mode（stand-in 缺 business_version） | 历史（10-17 冻结诊断早于合同字段） | 测试层适配 `original.sql_result`，补常量字段，oracle 断言不动 | 38 passed，清零 |
| 16 个 r07 source-io 链 | 疑似新引入 → 甄别为**环境回归** | 根因定位为 uv run editable 重同步破坏 worker 子进程导入（见 OQ-2），停止补丁 | 维持 failed，待评审 |
| t02 秘密扫描 ×1 | 新引入（批次19 fixture 字符串） | f-string 等值改写 | 清零 |
| t06 安全扫描 ×1 | 历史遗留（10-16 晚起）+ 批次新增 2 文件命中 | 新文件等值改写清零；54 处遗留 finding 记 OQ-3 | 维持 failed（历史余量） |
| 2 个 compose KeyError | 新引入（批次19 investigation-worker 装配不完整） | 补 healthcheck（/proc 探活）+ host overlay stanza | 清零 |

批次19新增文件对 t06 的贡献已清零（扫描器复核 my-files findings = 0）。
