# 批次21 C2：integration 真实执行运行清单（只读盘点）

- 盘点范围：`backend/tests/integration/` 全部 128 个 `*.py` 文件 + 隔离 PG 合同（`D:/dianzi/scripts/dev.py` 的 `require_isolated_test_database`、`D:/dianzi/backend/tests/conftest.py` 的 `isolated_test_database_url` / `migrated_engine`）+ 裸导入涉及文件。
- 盘点方式：只读（grep/Read/ls），未运行 pytest，未改动任何文件与 git 状态。
- 统计口径：测试数为文件内 `def test_*`（含方法缩进）的函数级粗数；wrapper 文件复制原模块测试函数，按"复制自 X（约 N 个）"计。

- 文档首次创建时间：2026-10-24T23:14:22+0800
- 最后更新时间：2026-10-24T23:14:22+0800

---

## ① 逐文件需求表

图例：标记列 `pg`=`pytest.mark.real_pg`；`svc`=`real_services`；`tls`=`real_search_tls`；`-`=无 pytestmark。run_id 列中"显式"=文件直接断言 `DIANZI_TEST_RUN_ID`；"隐含"=文件断言 `test_dianzi_<run_id>` 数据库名（经 `isolated_test_database_url` 合同 `db名必须==test_dianzi_<run_id>` 反推 run_id）；"无"=无文件级 run_id 约束（仅需满足全局合同）。

### A. 有显式 `DIANZI_TEST_RUN_ID` 断言的文件（12 个）

| 文件 | 测试数 | 标记 | run_id 断言（原样引用） | 额外资源 | 结论 |
|---|---|---|---|---|---|
| test_r06_source_excerpt_event_proof_pg.py | 6 | pg | L55 `assert os.environ["DIANZI_TEST_RUN_ID"] == "r06_source_event_proof_20261016"`（L54 db 名断言同值；用 isolated_test_database_url） | 无 | 仅 PG 可跑 |
| test_r11_assessment_http_pg.py | 9 | pg | L47 `assert os.environ["DIANZI_TEST_RUN_ID"] == RUN_ID`；L37 `RUN_ID = "r11_assessment_http_20261016"`；L48 端口/库名断言 `("127.0.0.1", 25432, DATABASE)`（直连 TEST_DATABASE_URL，不经 conftest fixture） | 无（HTTP 为 in-process TestClient） | 仅 PG 可跑，强制端口 25432 |
| test_r11_pg_assessments.py | 28 | pg | L55 `assert os.environ["DIANZI_TEST_RUN_ID"] == "r11_assessment_20261016"`；L53 db 名 `test_dianzi_r11_assessment_20261016`；L58 `current_schema().startswith("r11_assessment_")`；端口 25432 | 无 | 仅 PG 可跑，强制端口 25432 |
| test_r11_sbom_inventory_postgres.py | 15 | pg | L43 `assert os.environ.get("DIANZI_TEST_RUN_ID", "").startswith("r11_sbom_inventory_")`；L41 db 名 startswith `test_dianzi_r11_sbom_inventory_`；L42 端口 25432 | 无 | 仅 PG 可跑，强制端口 25432，run_id 前缀匹配 |
| test_r15_http_recommendations_pg.py | 14 | pg | L45-47 presence+模式：`run_id = os.environ.get("DIANZI_TEST_RUN_ID", "")` / 空或不匹配 `[a-zA-Z0-9_-]{1,80}` 则 `raise pytest.UsageError("blocked: standard TEST_DATABASE_URL/DIANZI_TEST_RUN_ID required")`；L49 db 名 startswith `test_`；L56 `current_schema()` startswith `test_` 且非 public；L58-59 断言 alembic `== "0029_recommendation_receipts"` | 无（HTTP 为 in-process） | 仅 PG 可跑；需 runner 预置 `test_*` 非 public schema 且已迁移到 0029 |
| test_r14_langgraph_workflow_pg.py | 15 | pg | L57-59 presence-only：`run_id = os.environ.get(...)`，空则 `raise pytest.UsageError("blocked: DIANZI_TEST_RUN_ID required")`；用 isolated_test_database_url，自建 schema | 无 | 仅 PG 可跑（可并入通用组） |
| test_r15_persistent_subscriptions_pg.py | 14 | pg | L57-60 presence+模式（同 r15_http 的 `[a-zA-Z0-9_-]{1,80}`）；L62 db 名 startswith `test_`；L69 schema startswith `test_` 非 public | 无 | 仅 PG 可跑；需预置 `test_*` 非 public schema |
| test_r16_assessment_candidates_pg.py | 11 | pg | L38 `assert os.environ["DIANZI_TEST_RUN_ID"] == RUN_ID`；L28 `RUN_ID = "r16_candidates_20261016"`；L35 db 名 `test_dianzi_` + RUN_ID；端口 25432 | 无 | 仅 PG 可跑，强制端口 25432 |
| test_r16_revalidation_runtime_pg.py | 18 | pg | L51 `assert os.environ["DIANZI_TEST_RUN_ID"] == RUN_ID`；L41 `RUN_ID = "r16_runtime_20261016"`；L48 db 名 `test_dianzi_` + RUN_ID；端口 25432 | 无 | 仅 PG 可跑，强制端口 25432 |
| test_r18_current_risk_summary_pg.py | 11 | pg | L50-51 `run_id = os.environ["DIANZI_TEST_RUN_ID"]` + `assert re.fullmatch(r"r18_current_risk_[a-z0-9_]{8,80}", run_id)`；L55 `(host,port,database)==("127.0.0.1",25432,"test_dianzi_"+run_id)`；L61 schema startswith `test_r18_risk_`；L79-80 断言 alembic `== "0030_revalidation_actor_bindings"` | 无 | 仅 PG 可跑，强制端口 25432；注意 alembic 头断言为 0030（runner 需提供该版本库或自行核对） |
| test_r18_public_component_selector_pg.py | 6 | pg | L34-35 `run_id = os.environ["DIANZI_TEST_RUN_ID"]` + `assert re.fullmatch(r"r18_component_selector_[a-z0-9_]{8,80}", run_id)`；L38 端口/库名 25432；L38 行首 `HEAD = "0031_public_task_bindings"`（L57 断言） | 无 | 仅 PG 可跑，强制端口 25432，run_id 前缀匹配 |
| test_t24_asset_inventory.py | 33 | pg | L44 `assert os.environ.get("DIANZI_TEST_RUN_ID", "").startswith("r11_inventory_")`；L42 db 名 startswith `test_dianzi_r11_inventory_`；L43 端口 25432 | 无 | 仅 PG 可跑，强制端口 25432，run_id 前缀匹配 |

另有一个显式断言位于共享 helper：`backend/tests/r11_forward_fixtures.py` L29 `assert os.environ["DIANZI_TEST_RUN_ID"] == RUN_ID`，L24-25 `RUN_ID = "r11_forward_rules_sbom_20261016"`、`DATABASE = "test_dianzi_" + RUN_ID`，L27 `HEAD = "0022_sbom_sidecars"`，`owned_url()` 同时断言端口 25432。使用该 helper 的文件见 B 组第 5 行。

### B. 由数据库名断言隐含 run_id 的文件（经 isolated_test_database_url 合同，15 个）

| 文件 | 测试数 | 标记 | db 名断言（原样引用）→ 隐含 run_id | 额外资源 | 结论 |
|---|---|---|---|---|---|
| test_detached_job_executor_pg.py | 9 | pg | L46 `assert url.database == "test_dianzi_detached_worker_20261016"` → `detached_worker_20261016` | 无 | 仅 PG 可跑 |
| test_r04_source_documents.py | 20 | pg | L64 `assert url.database == "test_dianzi_r04_source_documents_20261015"` → `r04_source_documents_20261015` | 无 | 仅 PG 可跑 |
| test_r04_knowledge_api_pg.py | 16 | pg | L48 `connection.scalar(text("SELECT current_database()")) == "test_dianzi_r04_api_20261015"` → `r04_api_20261015` | 无 | 仅 PG 可跑 |
| test_r05_vector_persistence.py | 9 | pg | L129 `assert url.database == "test_dianzi_r05_pgvector_20261015"` → `r05_pgvector_20261015`；L78 断言其自有 schema 的 alembic `== "0013_revision_source_metadata"`（加载冻结 legacy 种子，自带迁移逻辑） | 无 | 仅 PG 可跑 |
| test_r06_source_data_mode_pg.py | 4 | pg | L56 `assert url.database == "test_dianzi_r06_source_data_mode_20261016"` → `r06_source_data_mode_20261016`；L69-70 断言 `== "0031_public_task_bindings"` | 无 | 仅 PG 可跑 |
| test_r07_structured_fact_proofs_pg.py | 20 | pg | L73 `DATABASE = "test_dianzi_r07_structured_fact_proof_fix1_20261016"` → `r07_structured_fact_proof_fix1_20261016` | 无 | 仅 PG 可跑 |
| test_r10_evidence_graph_pg.py | 10 | pg | L214 `assert url.database == "test_dianzi_r06_catalog_r10_graph_20261016"` → `r06_catalog_r10_graph_20261016` | 无 | 仅 PG 可跑（也是 contract 裸导入的被依赖方） |
| test_r10_projection_pg.py | 13 | pg | L51 `assert url.database == "test_dianzi_r10_projection_20261016"` → `r10_projection_20261016` | 无 | 仅 PG 可跑 |
| test_r14_read_adapters_pg.py | 11 | pg | L47 `assert url.database == "test_dianzi_r14_read_tools_20261016"` → `r14_read_tools_20261016` | 无 | 仅 PG 可跑 |
| test_r18_public_producer_fix1_pg.py | 2 | pg | L56 `assert original.database == "test_dianzi_r18_public_producer_fix1_20261016"` → `r18_public_producer_fix1_20261016` | 无 | 仅 PG 可跑 |
| test_r18_public_producer_fix2_pg.py | 1 | pg | L36 `assert original.database == "test_dianzi_r18_public_producer_fix2_20261016"` → `r18_public_producer_fix2_20261016`；L54-55 断言 `== "0031_public_task_bindings"` | 无 | 仅 PG 可跑 |
| test_r18_public_read_producer_pg.py | 9 | pg | L47 `assert original.database == "test_dianzi_r18_public_read_20261016"` → `r18_public_read_20261016` | 无 | 仅 PG 可跑 |
| test_r07_enrichment_api_pg.py | 6 | pg | L29-30 入口库 `assert url.database.startswith("test_dianzi_r07_execution_api_")` → run_id 前缀 `r07_execution_api_`；随后 L31 `database = "test_dianzi_r07_api_" + uuid4().hex` 并 `CREATE DATABASE`（L36） | 需 CREATEDB 权限；Redis 仅为 monkeypatch.setenv 假配置（L160 `monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:26379/15")`，"no broker publish"），CONTENT_STORE_BACKEND=local | 仅 PG 可跑（需 CREATEDB） |
| test_r06_revision_mode_read_pg.py | 5 | pg | L45-46 `url.username != "test_dianzi_r01"` / `re.fullmatch(r"test_dianzi_r06_mode_[a-f0-9]{12,16}", url.database)`；L47-51 另要求 env `R06_MODE_DATABASE_OID`（全数字）与 `R06_MODE_DATABASE_COMMENT_SHA256`（64hex）；端口 25432 → run_id=`r06_mode_<hex12-16>`（控制器预置） | 控制器预置库+OID/COMMENT 证据 env；专用用户 test_dianzi_r01 | 仅 PG 可跑（特殊预置） |
| test_r10_projection_fix2_empty_reads.py | 2 | pg+svc | L15 `pytestmark = [pytest.mark.real_pg, pytest.mark.real_services]`；L10 裸导入 `from test_r10_projection_pg import PUBLIC, capture, manifest_for, published_fixture`（同目录，可解析） | Compose 附属服务 | **排除**（real_services） |

### C. 直连 TEST_DATABASE_URL、库名固定但 run_id 无约束（经核对不使用 conftest fixture）的文件（5 个）

| 文件 | 测试数 | 标记 | 库要求（原样引用） | 额外资源 | 结论 |
|---|---|---|---|---|---|
| test_r01_migration_engine_disposal_pg.py | 2 | pg | L69-70 `url.database != "test_dianzi_r01_20261014"` / `url.username != "test_dianzi_r01"`，L68 端口 25432 | PowerShell 解密私有资源 `D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi`（L58-61） | 仅 PG 可跑（依赖 dianzi-private 本地资源） |
| test_r03_cursor_review_negative.py | 3 | - | L40 `== "test_dianzi_r03_cursor_fix_20261015"`；L44-45 断言 alembic `== "0012_source_page_fingerprint"` | 需预迁移到 0012 的同名库 | 仅 PG 可跑（预置库） |
| test_r11_r08_forward_migration_schema.py | 4 | pg | L43-45 db ∈ {`test_dianzi_r11_r08_forward_migrations_20261016_empty`, `..._fresh2`}，L46 端口 25432，L50 断言 alembic `== HEAD`（`0019_aggregate_observations`） | 需两个预置同名库 @0019 | 仅 PG 可跑（预置库） |
| test_r20_backup_restore_pg.py | 2 | pg | L211-213 `R20_REHEARSAL_AUTHORIZED` 不为 "1" 则 `pytest.fail("blocked_integration: guarded R20 resource launcher required")`；L212 父库 `test_dianzi_r01_20261014` @25432；L220 自建 `test_dianzi_r20_backup_src_/dst_<id>` | R20_REHEARSAL_AUTHORIZED=1、CREATEDB、写 `D:/dianzi-private/r20-backup-rehearsal/`、pg_dump/restore 链路 | 仅 PG 可跑（特殊授权预置） |
| test_recovery_forward_migrations_0023_0026_pg.py | 25 | pg | L77-101 经 DPAPI 资源取连接串（同 r01 的 dpapi 文件），端口 25432、db startswith `test_`；L268 `CREATE DATABASE "test_forward26_<hex12>"` | DPAPI 私有资源 + CREATEDB | 仅 PG 可跑（依赖 dianzi-private 本地资源） |

### D. 通用组：无文件级 run_id/db 名约束（83 个文件，472 个测试函数）

以下文件仅依赖 `isolated_test_database_url`/`migrated_engine`（db==`test_dianzi_<run_id>`，任意合法 run_id）或自建 schema，可共用一次环境变量设置。均为"仅 PG 可跑"。

test_detached_job_executor_pg.py 已单列；本组清单（83）：
test_public_ask_route_pg.py(10), test_r01_runtime_observations.py(2), test_r02_auth_state.py(11), test_r02_default_application.py(1), test_r02_dimension_migration.py(1), test_r02_dimension_persistence.py(9), test_r02_knowledge_revisions.py(21), test_r02_relation_identity_regressions.py(3), test_r02_schema_migration.py(2), test_r03_cursor_persistence.py(15), test_r03_cursor_review_fixes.py(10), test_r03_jobs_pg.py(14), test_r03_schema_migration.py(1), test_r04_api_review_regressions.py(9), test_r04_review_regressions.py(6), test_r04_revision_metadata.py(3), test_r04_source_http_idempotency_pg.py(5), test_r04_source_jobs_pg.py(10), test_r05_generation_http.py(3), test_r05_question_api_pg.py(15), test_r06_bulk_source_evidence_pg.py(4), test_r06_catalog_documents_pg.py(9), test_r06_document_api_pg.py(13), test_r06_failed_response_persistence_pg.py(19), test_r06_source_boundary_pg.py(2), test_r06_source_polling_pg.py(9), test_r06_source_worker_api_pg.py(6), test_r06_source_worker_pg.py(8), test_r07_composed_claims_pg.py(6), test_r07_cvss_authority_scope_fix_pg.py(1), test_r07_enrichment_inputs_pg.py(10), test_r07_enrichment_job_metadata_pg.py(4), test_r07_enrichment_publication_pg.py(12), test_r07_idempotency_scope_api_pg.py(1), test_r07_idempotency_scope_pg.py(10), test_r07_input_audit_legacy_pg.py(4), test_r07_input_audit_pg.py(4), test_r07_input_audit_receipts_pg.py(10), test_r07_input_capabilities_pg.py(7), test_r07_job_execution_pg.py(13), test_r07_literature_target_scope_pg.py(3), test_r07_publication_acl_lock_fix_pg.py(6), test_r07_publication_rule_provenance_pg.py(1), test_r07_signal_claim_values_pg.py(5), test_r08_aggregate_persistence_pg.py(14), test_r08_cache_ttl_fix1_pg.py(5), test_r10_graph_fix2_pg.py(4), test_r10_graph_source_coverage_pg.py(1), test_r10_graph_validity_pg.py(11), test_r11_assessment_raw_rechecks_pg.py(9), test_r11_default_readers_pg.py(3), test_r11_forward_rules_sbom_schema.py(12)*, test_r11_r08_migration_head_regression.py(33,复制自t24)*, test_r12_conversation_assets_pg.py(2), test_r12_conversation_boundary_fix1_pg.py(9), test_r12_conversation_context_pg.py(13), test_r12_conversation_lock_pg.py(3), test_r12_conversation_process_pg.py(2), test_r12_final_snapshot_fence.py(4), test_r12_legal_publication_window.py(1), test_r12_production_schema.py(6), test_r14_default_runtime_pg.py(10), test_r14_langgraph_workflow_pg.py(15), test_r14_langgraph_workflow_fix1_pg.py(2), test_r14_preclaim_recovery_pg.py(9), test_r14_shared_read_consumers_pg.py(4), test_r14_source_report_output_budget_pg.py(7), test_r14_terminal_outbox_pg.py(8), test_r16_current_scope_paging_pg.py(4), test_r16_fan_in_pg.py(3), test_r18_actor_references_pg.py(8), test_r18_api_key_credentials_pg.py(11), test_r18_api_key_post_lock_time_pg.py(4), test_r18_public_task_binding_pg.py(11), test_r18_question_credential_pg.py(14), test_t05_persistence_and_raw_store.py(15), test_t07_jobs_and_outbox.py(6), test_t16_incremental_monitoring.py(6), test_t21_claims_entities_conflicts.py(8)。

注1：带 `*` 的两个文件实际有组级约束，见分组表 G5/G27 说明（r11_forward_rules_sbom_schema 走 r11_forward_fixtures → run_id 固定；r11_r08_migration_head_regression 走 migrated_engine 但断言库头 `0019_aggregate_observations`，与当前 head 0031 冲突，需复核，见"风险与偏差"）。
注2：test_r06_source_polling_pg.py(L12-14) 与 test_r11_assessment_raw_rechecks_pg.py(L10) 使用同目录裸导入 `from test_r06_catalog_documents_pg import ...` / `from test_r11_pg_assessments import pg_engine as pg_engine`，同目录运行可解析；raw_rechecks 因此归入 G3（其 pg_engine 来自 pg_assessments，run_id 跟随）。test_r11_sbom_inventory_uri_privacy.py 使用同目录 `sbom_engine` fixture 导入，归入 G4。
注3：test_r14_default_runtime_pg.py 与 test_r06_source_polling_pg.py 会 spawn 本地 Python 子进程（注入 PYTHONPATH=src+tests），无外部服务。

### E. 需要额外服务、本批排除的文件（10 个）

| 文件 | 测试数 | 标记 | 缺失的外部资源（证据） |
|---|---|---|---|
| test_r01_search_tls_live.py | 3 | tls | L44-50 要求 `TEST_SEARCH_TLS_URL/USERNAME/CA_FILE/WRONG_CA_FILE/RUN_ID/PROJECT/CONTAINER` + `TEST_SEARCH_TLS_PASSWORD`；L146 `DIANZI_DOCKER_COMMAND_JSON`；secure OpenSearch TLS 容器 |
| test_r02_minio_persistence.py | 7 | pg+svc | L35-42 要求 `TEST_MINIO_ENDPOINT`(必须 `127.0.0.1:29400`)/`TEST_MINIO_BUCKET`(前缀 `test-dianzi-r02-`)/`TEST_MINIO_ACCESS_KEY/SECRET_KEY`；`from minio import Minio`(L16) |
| test_r03_executor_celery.py | 2 | pg+svc | L38 `assert os.environ["APP_ENV"] == "test" and os.environ["DATA_MODE"] == "fixture"`；L49 `R03_QUEUE`；L68/117 `TEST_DATABASE_URL`/`TEST_REDIS_URL`；Celery worker + Redis broker |
| test_r10_neo4j_projection.py | 7 | pg+svc | L43 `pytestmark = [real_pg, real_services]`；L44/65 DPAPI 私有资源 `D:/dianzi-private/r10-neo4j-test-20261016.dpapi`；`from neo4j import GraphDatabase` |
| test_r10_projection_fix1_markers.py | 3 | 混合 | L45、L90-91 两个测试 `@pytest.mark.real_services`；L126-127 的 `test_missing_epoch_job_uses_fixed_state_code_without_side_effect` 仅 real_pg（走 isolated_test_database_url），可用 `-k` 单跑 |
| test_r10_projection_fix2_empty_reads.py | 2 | pg+svc | L15 `pytestmark = [pytest.mark.real_pg, pytest.mark.real_services]` |
| test_r11_forward_hybrid_regression.py | 0(复制自 t30 约16) | pg | L31 `search_url = os.environ["R12_OPENSEARCH_URL"]`；L42 OpenSearchCorpusClient |
| test_r12_production_indexing.py | 0(复制自 t30 约16) | pg | L68 `httpx.Client(base_url=os.environ["R12_OPENSEARCH_URL"])`；L33 db 名固定 `test_dianzi_r12_runtime_20261016` |
| test_t03_development_services.py | 6 | svc | L24 `pytestmark = pytest.mark.real_services`；L54/209 `os.environ["DIANZI_TEST_COMPOSE_PROJECT"]`（Compose 项目） |
| test_t30_hybrid_retrieval.py | 16 | pg | L68-70 缺 `R12_OPENSEARCH_URL` 则 `pytest.fail("blocked_integration: ...")`；L51 db 名固定 `test_dianzi_r12_hybrid_20261016` |

其余所有文件中出现的 `http://` 均为 in-process（TestClient / httpx ASGI / ORIGIN 常量），真实出网 HTTP 仅上表 3 个 OpenSearch 文件（test_r11_forward_hybrid_regression / test_r12_production_indexing / test_t30_hybrid_retrieval）。`test_t16_incremental_monitoring.py` 命中的 "redis" 只是测试函数名 `..._rediscovered_...`，非外部依赖。

---

## ② 分组运行表

约定：端口一律 25432（全部强制端口断言均为 25432；且 25432≠5432，无需 `DIANZI_TEST_ISOLATION`）。每组一个隔离库 `test_dianzi_<run_id>` + 专用用户 `test_<name>`（由 runner 预建；多数文件的 fixture/迁移逻辑假定空库起步，`migrated_engine` 组会自动迁移到当前 head 0031）。

| 组 | DIANZI_TEST_RUN_ID | 文件 | 测试数 | 特别前置 |
|---|---|---|---|---|
| G1 | `r06_source_event_proof_20261016` | test_r06_source_excerpt_event_proof_pg.py | 6 | — |
| G2 | `r11_assessment_http_20261016` | test_r11_assessment_http_pg.py | 9 | — |
| G3 | `r11_assessment_20261016` | test_r11_pg_assessments.py, test_r11_assessment_raw_rechecks_pg.py | 37 | — |
| G4 | `r11_sbom_inventory_20261016`（前缀匹配即可） | test_r11_sbom_inventory_postgres.py, test_r11_sbom_inventory_uri_privacy.py, test_r11_sbom_inventory_uri_privacy_followup.py | 23 | — |
| G5 | `r11_forward_rules_sbom_20261016` | test_r11_forward_rules_sbom_schema.py, test_r11_forward_assessment_regression.py | 49 | 风险：migrated_schema() 默认 target="head" 但断言 revision==`0022_sbom_sidecars`（r11_forward_fixtures.py L27/L81），当前 alembic head 为 0031，预期失败，需先复核（见§5） |
| G6 | `r11_inventory_20261016`（前缀匹配即可） | test_t24_asset_inventory.py | 33 | — |
| G7 | `r16_candidates_20261016` | test_r16_assessment_candidates_pg.py | 11 | — |
| G8 | `r16_runtime_20261016` | test_r16_revalidation_runtime_pg.py | 18 | — |
| G9 | `r18_current_risk_20261016a`（须匹配 `r18_current_risk_[a-z0-9_]{8,80}`） | test_r18_current_risk_summary_pg.py | 11 | 库头断言 0030，需核对 |
| G10 | `r18_component_selector_20261016a`（须匹配 `r18_component_selector_[a-z0-9_]{8,80}`） | test_r18_public_component_selector_pg.py | 6 | — |
| G11 | `detached_worker_20261016` | test_detached_job_executor_pg.py | 9 | — |
| G12 | `r04_source_documents_20261015` | test_r04_source_documents.py | 20 | — |
| G13 | `r04_api_20261015` | test_r04_knowledge_api_pg.py | 16 | — |
| G14 | `r05_pgvector_20261015` | test_r05_vector_persistence.py | 9 | 文件内部自迁移 schema 至 0013 |
| G15 | `r06_source_data_mode_20261016` | test_r06_source_data_mode_pg.py | 4 | — |
| G16 | `r07_structured_fact_proof_fix1_20261016` | test_r07_structured_fact_proofs_pg.py | 20 | — |
| G17 | `r06_catalog_r10_graph_20261016` | test_r10_evidence_graph_pg.py | 10 | — |
| G18 | `r10_projection_20261016` | test_r10_projection_pg.py | 13 | — |
| G19 | `r14_read_tools_20261016` | test_r14_read_adapters_pg.py | 11 | — |
| G20 | `r18_public_producer_fix1_20261016` | test_r18_public_producer_fix1_pg.py | 2 | — |
| G21 | `r18_public_producer_fix2_20261016` | test_r18_public_producer_fix2_pg.py | 1 | — |
| G22 | `r18_public_read_20261016` | test_r18_public_read_producer_pg.py | 9 | — |
| G23 | `r07_execution_api_20261016`（前缀 `r07_execution_api_` 即可） | test_r07_enrichment_api_pg.py | 6 | 入口库名须 startswith `test_dianzi_r07_execution_api_`；需 CREATEDB |
| G24 | `r06_mode_<12-16位hex>`（例 `r06_mode_a1b2c3d4e5f6`） | test_r06_revision_mode_read_pg.py | 5 | 控制器预置库+用户 test_dianzi_r01+`R06_MODE_DATABASE_OID`+`R06_MODE_DATABASE_COMMENT_SHA256` |
| G25 | 任意合法（例 `r15_receipts_20261016`） | test_r15_http_recommendations_pg.py, test_r15_persistent_subscriptions_pg.py | 28 | runner 预置 `test_*` 非 public schema；http_recommendations 断言该 schema alembic==`0029_recommendation_receipts` |
| G26 通用 | 任意合法（例 `batch21_c2_pg`） | §1-D 清单 83 文件（剔除两注后为 81 + test_r14_langgraph_workflow_pg） | ≈470 | 空库由 migrated_engine 自动迁移至 head |
| G27 自由 run_id 专属库 | 任意合法（各文件单独库） | test_r01_migration_engine_disposal_pg.py(`test_dianzi_r01_20261014`/用户`test_dianzi_r01`), test_r03_cursor_review_negative.py(`test_dianzi_r03_cursor_fix_20261015`@0012), test_r11_r08_forward_migration_schema.py(两个预置库@0019), test_r20_backup_restore_pg.py(`R20_REHEARSAL_AUTHORIZED=1`+父库), test_recovery_forward_migrations_0023_0026_pg.py(DPAPI+CREATEDB) | 36 | 均依赖 dianzi-private 本地资源或预置库 |
| 排除 | — | §1-E 10 文件 | 78 | 需 OpenSearch TLS/MinIO/Redis+Celery/Neo4j/Compose/OpenSearch，未授权不跑 |

组数：27 个可执行分组（G1–G27，其中 G26 一次覆盖 83 文件）+ 1 个排除组。文件合计 128；测试函数合计约 952。

---

## ③ 裸导入修复方案

### 现状证据

四个目录 `backend/tests/`、`backend/tests/integration/`、`backend/tests/contract/`、`backend/tests/security/` 均**不存在 `__init__.py`**（`ls` 逐一确认，仅 `__pycache__`）。`backend/pyproject.toml` 是唯一 pytest 配置载体：

```ini
[tool.pytest.ini_options]           # backend/pyproject.toml L94
testpaths = ["tests/unit"]          # L95
addopts = "--cov=ai_intel --cov-report=term-missing --cov-fail-under=60"   # L96
```

无 `pythonpath` ini 项、无 pytest.ini、根目录无 pyproject/pytest.ini → rootdir=`D:/dianzi/backend`，默认 prepend 导入模式：收集某目录测试模块时把该目录（无包则为其所在目录）插入 `sys.path[0]`。`scripts/dev.py` L162 以 `["uv","run","--locked","pytest", f"tests/{requested_scope}"]`、working_directory=BACKEND_DIR 调用，即按 scope 整目录收集。

`backend/tests/conftest.py` 的 sys.path 处理不在文件开头，而在 `pytest_configure`（启动即执行、先于收集）：

- L20 `PROJECT_ROOT = Path(__file__).resolve().parents[2]`（= `D:/dianzi/backend`）
- L154-156 `def pytest_configure(config): ...` / `sys.path.insert(0, str(PROJECT_ROOT))`

因此收集阶段 `backend/` 与 `backend/tests/`（conftest 自身被 prepend 导入时插入）都在 sys.path 上；`tests.*` 作为 PEP 420 命名空间包可导入（无需 `__init__.py`）——仓库内已有先例：`security/test_r07_input_audit_security_pg.py:10`、`security/test_r07_input_audit_fix1_acl_pg.py:10`、`integration/test_r11_sbom_inventory_uri_privacy_followup.py:9-12`、`integration/test_r11_forward_assessment_regression.py:11` 都用包路径导入且按 scope 运行可解析。

### 四个文件逐一结论

1. **`backend/tests/contract/test_r14_tool_gateway_pg.py` L18**
   `from test_r10_evidence_graph_pg import VERSION, publish_event, publish_fact`
   - contract/ 目录下无 `test_r10_evidence_graph_pg.py`（`ls` 确认）；该文件实际在 `integration/`（符号定义处：L51 `VERSION = {`、L238 `def publish_fact(...)`、L283 `def publish_event(...)`）。
   - 仅运行 `pytest tests/contract` 时 `backend/tests/integration` 不在 sys.path → `ModuleNotFoundError`。
   - **修复（最小正确写法）**：改为 `from tests.integration.test_r10_evidence_graph_pg import VERSION, publish_event, publish_fact`。

2. **`backend/tests/contract/test_r14_tool_gateway_review_pg.py` L8-9**
   `from test_r14_tool_gateway_pg import limits, seed_principal, source_call` / `from test_r14_tool_gateway_pg import r14_engine as r14_engine`
   - 同目录兄弟导入（contract/ 内存在该文件），prepend 模式下 `pytest tests/contract` 可解析，**无需修改**。

3. **`backend/tests/security/test_r07_input_audit_security_pg.py` L9**
   `from test_r07_input_audit_receipts_pg import recorded_workflow`
   - security/ 目录下无 receipts 文件（`ls` 确认）；实际在 `integration/test_r07_input_audit_receipts_pg.py` L29 `def recorded_workflow(engine, tmp_path, monkeypatch):`。
   - 仅运行 `pytest tests/security` 时裸名不可解析 → `ModuleNotFoundError`。
   - **修复**：改为 `from tests.integration.test_r07_input_audit_receipts_pg import recorded_workflow`。
   - 同文件 L10 `from tests.r07_idempotency_scope_helpers import create_actor`、L19-20 `from r07_input_audit_helpers import ...` 已经可解析（backend/、backend/tests/ 均在 sys.path），不动。

4. **`backend/tests/security/test_r07_input_audit_fix1_acl_pg.py` L10**
   `from tests.security.test_r07_input_audit_security_pg import private_recorded_workflow`
   - 已是包路径导入，本身可解析；L15 `from r07_input_audit_helpers import audit_engine as audit_engine` 亦可解析。**本文件无需修改**，但其导入链会触发第 3 条的裸导入——第 3 条修复后本文件随之解锁。

### 结论与注意点

- 需要改动的只有 2 行（contract L18、security L9），均改为 `tests.<子包>.<模块>` 包路径导入；依据：conftest `pytest_configure` 在收集前把 `backend/` 插入 sys.path（L154-156）+ PEP 420 命名空间包（四个目录均无 `__init__.py`）+ 仓库内 4 处既有包路径导入先例。
- 若同一次 pytest 会话中 integration 已被收集，裸名 `test_r10_evidence_graph_pg` 与包路径 `tests.integration.test_r10_evidence_graph_pg` 会产生两个模块实例；这些被导入符号（常量/纯函数/fixture 函数）无状态，双实例无害。如需身份一致，可仿照 `integration/test_r11_forward_assessment_regression.py:14` 的 `sys.modules.setdefault("test_r11_pg_assessments", original)` 做别名。
- 另一等效方案（不改代码）：运行 contract/security 时给 `PYTHONPATH` 追加 `D:/dianzi/backend/tests/integration`。不推荐为默认方案（把跨目录耦合藏进运行环境），仅作应急。

---

## ④ 环境变量设置模板

全局合同（scripts/dev.py L43-75，与任务描述一致）：`DIANZI_TEST_RUN_ID` 匹配 `[a-z][a-z0-9_]{2,47}`；`TEST_DATABASE_URL` 为 `postgresql://<user>:<pw>@127.0.0.1:<port>/<db>`、db 恰为 `test_dianzi_<run_id>`、用户匹配 `test_[a-z0-9_]+` 且密码非空；仅当端口==5432 时要求 `DIANZI_TEST_ISOLATION=container` 且用户名==库名。**统一用 25432 端口后无需设置 `DIANZI_TEST_ISOLATION`。**

conftest 侧确认（问题 4）：`isolated_test_database_url`（conftest L168-176）只调用 `require_isolated_test_database()`，除 `DIANZI_TEST_RUN_ID`、`TEST_DATABASE_URL` 外**不要求任何其他环境变量**；`DIANZI_TEST_ISOLATION` 的默认行为是"不设置"——只在端口 5432 分支（dev.py L71-74）被读取，25432 下完全不涉及。`migrated_engine`（L179-208）额外要求 PG 可连且迁移成功，无其他 env。

每条命令在 `D:/dianzi/backend` 目录下执行；`<pw>` 为占位符，替换为真实测试口令；每组先由 runner 建库建用户（G26 由 `migrated_engine` 自动迁移，其余组按表内"特别前置"）。

```bash
# G1
DIANZI_TEST_RUN_ID=r06_source_event_proof_20261016 \
TEST_DATABASE_URL='postgresql://test_batch21:<pw>@127.0.0.1:25432/test_dianzi_r06_source_event_proof_20261016' \
uv run --locked pytest tests/integration/test_r06_source_excerpt_event_proof_pg.py

# G3（同值两文件共用一次设置）
DIANZI_TEST_RUN_ID=r11_assessment_20261016 \
TEST_DATABASE_URL='postgresql://test_batch21:<pw>@127.0.0.1:25432/test_dianzi_r11_assessment_20261016' \
uv run --locked pytest tests/integration/test_r11_pg_assessments.py tests/integration/test_r11_assessment_raw_rechecks_pg.py

# G26 通用组（83 文件一次跑，排除 10 个需额外服务的文件）
DIANZI_TEST_RUN_ID=batch21_c2_pg \
TEST_DATABASE_URL='postgresql://test_batch21:<pw>@127.0.0.1:25432/test_dianzi_batch21_c2_pg' \
uv run --locked pytest tests/integration \
  --ignore=tests/integration/test_r01_search_tls_live.py \
  --ignore=tests/integration/test_r02_minio_persistence.py \
  --ignore=tests/integration/test_r03_executor_celery.py \
  --ignore=tests/integration/test_r10_neo4j_projection.py \
  --ignore=tests/integration/test_r10_projection_fix1_markers.py \
  --ignore=tests/integration/test_r10_projection_fix2_empty_reads.py \
  --ignore=tests/integration/test_r11_forward_hybrid_regression.py \
  --ignore=tests/integration/test_r12_production_indexing.py \
  --ignore=tests/integration/test_t03_development_services.py \
  --ignore=tests/integration/test_t30_hybrid_retrieval.py

# G24（控制器预置组，额外证据变量）
DIANZI_TEST_RUN_ID=r06_mode_a1b2c3d4e5f6 \
TEST_DATABASE_URL='postgresql://test_dianzi_r01:<pw>@127.0.0.1:25432/test_dianzi_r06_mode_a1b2c3d4e5f6' \
R06_MODE_DATABASE_OID=<控制器提供的OID> \
R06_MODE_DATABASE_COMMENT_SHA256=<64位hex> \
uv run --locked pytest tests/integration/test_r06_revision_mode_read_pg.py

# 单值固定组模板（G11 为例，G2/G7/G8/G12-G22 同型替换 run_id 与文件名）
DIANZI_TEST_RUN_ID=detached_worker_20261016 \
TEST_DATABASE_URL='postgresql://test_batch21:<pw>@127.0.0.1:25432/test_dianzi_detached_worker_20261016' \
uv run --locked pytest tests/integration/test_detached_job_executor_pg.py
```

G27 各文件使用各自固定的库名/用户（`test_dianzi_r01_20261014`+`test_dianzi_r01`、`test_dianzi_r03_cursor_fix_20261015`、两个 `test_dianzi_r11_r08_forward_migrations_20261016_*`、r20 父库+自建库、recovery 的 DPAPI 串），run_id 只需合法即可（例 `batch21_c2_special`），且 r20 需 `R20_REHEARSAL_AUTHORIZED=1`。

---

## ⑤ 风险与偏差（盘点中发现、需运行前复核）

1. **head 断言与当前迁移头不一致**：当前 alembic head 为 `0031_public_task_bindings`（migrations/versions 最新 0031，共 62 个 revision）。但 `tests/r11_forward_fixtures.py` L81 `assert revision == (HEAD if target == "head" else target)`（HEAD=`0022_sbom_sidecars`）在默认 target="head" 下会先迁到 0031 再断言 0022；同理 `test_r11_r08_migration_head_regression.py` L25-27 在 `migrated_engine`（迁移到 head）后断言 `0019_aggregate_observations`。G5 与该文件按现状预期失败——属于"已知回归修复范围"还是断言过期，需在运行时确认，不得为通过而放宽断言。
2. G9（`0030`）、G14（自有 schema `0013`）、G25（schema `0029`）的版本断言依赖 runner 按表内"特别前置"准备，不能与 G26 的 head 库混用。
3. DPAPI/私有资源文件（`test_r01_migration_engine_disposal_pg.py`、`test_recovery_forward_migrations_0023_0026_pg.py`、`test_r10_neo4j_projection.py`）依赖 `D:/dianzi-private/` 下加密资源，缺失时按文件内逻辑 UsageError/ Runtime blocked，属外部阻塞而非软件缺陷。
4. 全部 128 文件的导入与 collect-only 不访问外部资源（conftest L1 文档串声明）；隔离 fixture 在缺资源时抛 `pytest.UsageError("blocked: ...")`（错误/blocked，不是 skip），因此排除文件必须用 `--ignore`，不能放任其进运行列表。
