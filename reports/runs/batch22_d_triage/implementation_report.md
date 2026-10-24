# 批次22 目标1 实施报告 —— CR-种子对齐（seed data_mode stamp）落地与容器复跑

- 文档首次创建时间：2026-10-25T06:19:45+08:00
- 本次写作开始时间：2026-10-25T06:19:45+08:00
- 最后更新时间：2026-10-25T06:19:50+08:00
- 实施依据：`docs/decisions/CR-seed_data_mode_alignment_batch22.md` + `reports/runs/batch22_d_triage/triage_report.md`（修复建议节 file:line）
- 起点 HEAD：da2822335（含甄别检查点；任务书所写 4c6ff75ac 之上仅新增 reports，backend 一致）
- 状态：awaiting_review（未 commit，按要求留待 Root 统一提交）

## 0. 执行摘要

- 修改 9 个测试种子文件（+24/−6 行，零断言改动、零产品代码改动、零 legacy 分支语义改动）。
- 容器逐文件重跑 35 个受影响 integration 文件：**基线 46 failed → 13 failed（转绿 33，仍红 13，另 1 例一次性失败经两轮复现排除为非回归）**。
- 仍红 13 例全部有明确定性：7 例容器只读挂载（A-harness，B 根因已修）、3 例 legacy/显式 unknown 行可读性（CR 明示非目标，OQ-5 裁决）、3 例 D 类/甄别预测未兑现（需进一步取证）。
- 基线另有 18 个 setup errors（r12_conversation_lock 3、r10_projection 15）为容器预置层与文件内钉定断言的既有缺口，原样复现、不计入失败对比。

## 1. 改动域裁决记录（重要，含偏离披露）

任务书改动域列举 7 个文件并"以 CR 第改动节为准"。实施前核查发现冲突：7 个文件中只有 4 个的种子可文件内修改；CR 改动节第 4/5 条描述的修改点物理位于共享 helper 文件。已通过 AskUserQuestion 上报协调者（2026-10-25T05:14+08:00），未获答复；按任务书自身的权威规则（"以 CR 第'改动'节为准"）执行 **CR 意图最小扩展**：CR 第 5 条括注明文要求"prepared_submission 内 revision_metadata 增加 data_mode"，第 4 条明文要求会话期限改相对时钟。故在 7 文件之外追加 5 个种子落点文件的最小 stamp（见下表），全部为新增写入字段，不触碰断言值、产品代码、legacy 分支、r05/r04_source_documents、public_extension_reads。

| # | 文件 | 改动 | 依据 |
|---|---|---|---|
| 1 | backend/tests/integration/test_r04_knowledge_api_pg.py | `seed_source_document` 的 `document_revisions.insert().values(...)` 增加 `**({} if legacy else {"source_metadata": {"data_mode": "fixture"}})`（legacy 分支键缺席，server_default `{}` 语义原样保留） | CR 第1条 |
| 2 | backend/tests/integration/test_r06_catalog_documents_pg.py | `save()` 向 `persist_catalog_documents(..., data_mode="fixture")`（产品 `_revision_metadata` 会 pop 成员元数据中的 data_mode 键，参数是唯一正确落章途径；落库为 `{"data_mode":"fixture","data_mode_policy_version":"trusted-source-runtime-v1"}`） | CR 第2条 |
| 3 | backend/tests/integration/test_r06_source_excerpt_event_proof_pg.py | `response()` 返回 `SourceResponse(kind, body, url, NOW, data_mode="fixture")` | CR 第3条 |
| 4 | backend/tests/integration/test_r07_cvss_authority_scope_fix_pg.py | 文件内 `SourceResponse(..., data_mode="fixture")` | CR 第5条 |
| 5 | backend/tests/integration/test_r02_knowledge_revisions.py | `prepared_submission` 的 `save_document_revision(..., revision_metadata={"data_mode": "fixture"})` | CR 第5条括注（明文） |
| 6 | backend/tests/integration/test_r18_api_key_credentials_pg.py | `pg_case` fixture `expires_at=NOW+timedelta(days=1)` → `expires_at=datetime.now(UTC)+timedelta(days=1)`；`issued_at=NOW` 保持冻结（产品 `_validate_lifetime` 要求 `issued_at<=now`，该文件自身 12 个用例用冻结 NOW 锁会话——只改 expires_at 是唯一不破坏兄弟用例的相对时钟写法，甄别报告建议的 issued_at 一并改法经验证会打破它们） | CR 第4条 + 甄别报告 r18 节 |
| 7 | backend/tests/integration/test_r06_source_boundary_pg.py | 失败用例自有 `build_source_page_handler(..., data_mode="fixture")`（核查证实 CR 第2条"由 catalog 种子连带修复 r06_source_boundary(3)"不成立：该测试不用 paper()/save()） | 甄别报告 r06_source_boundary 节 |
| 8 | backend/tests/integration/test_r06_source_worker_pg.py | `handler_for` 增加可选 `data_mode=None` 参数并透传 `build_source_page_handler`（默认值保持全部既有调用方字节级不变） | 支撑 #9 |
| 9 | backend/tests/integration/test_r07_enrichment_inputs_pg.py | `seeded_event` 调 `handler_for(store, kind, data_mode="fixture")`（test_r07_enrichment_publication_pg(3) 的种子入口） | CR 第5条意图 |

CR 点名但**本体零改动**的 3 个文件（种子在共享 helper，哈希 old==new 已记录）：test_r18_api_key_post_lock_time_pg.py、test_r07_enrichment_publication_pg.py、test_r14_default_runtime_pg.py。

文件前后 raw sha256（含上表全部 9+3 文件）：`reports/runs/batch22_d_triage/seed_alignment_expectations.json`。

## 2. 验证证据

### 2.1 宿主（offline 可跑部分）

`reports/runs/batch22_d_triage/host_targeted.txt`：
- `uv run python -m pytest tests/unit tests/contract tests/security -q --no-cov -k "r04 or r06 or r18_api_key or cvss or enrichment_publication or default_runtime"` → **1163 passed, 5169 deselected, 5 errors**，pytest_exit=1。5 个 error 全部是 `tests/security/test_r06_bulk_source_evidence_scope.py` 的 setup 期 `UsageError: blocked: DIANZI_TEST_RUN_ID must be a lowercase test identifier`——宿主无隔离库环境变量的已知限制（与 batch21_red_zero 全量证据中 real_pg 用例同因），非本次改动引入。
- 9 个编辑文件 + 3 个 CR 点名文件 `--collect-only` → **190 collected，exit=0**（import 图完整）。
- `python -m py_compile` 9 文件 → exit=0。

### 2.2 容器逐文件重跑（第一轮，35 文件）

- plan：`reports/runs/batch22_d_triage/plan_batch22_goal1_rerun.json`（自 plan_batch22.json 按被改 helper 的 import 图圈定 35 文件；run_id/port 沿用父 plan，与 batch21 run6 基线同库条件）。
- 命令：`uv run python scripts/dev_integration_container.py --plan ... --evidence-dir reports/runs/batch22_d_triage --keep-cache`，日志 `goal1_container_run_log.txt`（runner_exit=1，因存在残余失败）。
- 逐文件输出：`<stem>_pf.txt`；基线计数：`goal1_baseline_counts.json`（源 batch21_integration_unlocked/<stem>_pf.txt）。

### 2.3 判别复跑（第二、三轮）

- 第二轮（独立新库）：`plan_batch22_goal1_recheck.json` → r14_default_runtime 残留稳定复现（1 failed/12 passed，`*_recheck_pf.txt`）；r14_langgraph 单独跑 **34 passed 全绿**；r14_read_adapters 复跑无效——该文件钉定库名（read_engine 断言 `test_dianzi_r14_read_tools_20261016`），改 run_id 触发 25 个 setup errors，属复跑方法失误，该文件以第一轮+基线同测试同形态为证据。
- 第三轮（精确复现第一轮共享序列）：`plan_batch22_goal1_seqcheck.json`，run_id `r06_catalog_r10_graph_20261016`（r10_evidence_graph_pg.py:214 钉定），5 文件 **全部 exit=0**，含 test_r14_langgraph_workflow_pg 34 passed——第一轮该文件 [B2b-2] 的 InvalidActorReferenceError 在同序列、同库、同顺序下不复现。

## 3. 逐文件 before/after（失败数 failed；errors 另列）

| 文件 | batch21 run6 | 本次终态 | 判定 |
|---|---|---|---|
| test_r04_knowledge_api_pg | 10 f | 1 f | 转绿 9；残留=legacy=True 探针（CR 非目标） |
| test_r04_api_review_regressions | 7 f | 1 f | 转绿 6；残留=共享库中 legacy 行（同上） |
| test_r06_catalog_documents_pg | 1 f | 0 f | **全绿** |
| test_r06_document_api_pg | 6 f | 1 f | 转绿 5；残留=测试故意置 `{}` 的显式 unknown 旧行（OQ-5） |
| test_r06_source_boundary_pg | 3 f | 0 f | **全绿** |
| test_r06_source_excerpt_event_proof_pg | 8 f | 7 f | 转绿 1；7 例 B 根因已修（:219/:282 断言通过），死于 trace() 写只读 /repo |
| test_r06_bulk_source_evidence_pg | 0 | 0 | 无回归 |
| test_r06_failed_response_persistence_pg | 0 | 0 | 无回归 |
| test_r06_source_polling_pg | 0 | 0 | 无回归 |
| test_r06_source_worker_pg | 0 | 0 | 无回归（handler_for 扩参安全） |
| test_r07_cvss_authority_scope_fix_pg | 2 f | 0 f | **全绿** |
| test_r07_enrichment_publication_pg | 3 f | 0 f | **全绿** |
| test_r07_enrichment_inputs_pg | 0 | 0 | 无回归 |
| test_r07_enrichment_job_metadata_pg | 0 | 0 | 无回归 |
| test_r07_input_capabilities_pg | 1 f | 0 f | **全绿**（独立库 + 种子 stamp） |
| test_r07_job_execution_pg | 1 f | 1 f | D 类原样（甄别已排除家族 1；同用例同名） |
| test_r07_composed_claims_pg | 0 | 0 | 无回归 |
| test_r07_literature_target_scope_pg | 0 | 0 | 无回归 |
| test_r07_publication_acl_lock_fix_pg | 0 | 0 | 无回归 |
| test_r07_publication_rule_provenance_pg | 0 | 0 | 无回归 |
| test_r07_signal_claim_values_pg | 0 | 0 | 无回归 |
| test_r12_conversation_lock_pg | 0 f / 3 e | 0 f / 3 e | 既有钉定缺口原样（fixture 断言 `test_dianzi_r12_context_20261016`） |
| test_r10_evidence_graph_pg | 0 | 0 | 无回归（prepared_submission 消费方） |
| test_r10_graph_fix2_pg | 0 | 0 | 无回归 |
| test_r10_graph_source_coverage_pg | 0 | 0 | 无回归 |
| test_r10_graph_validity_pg | 0 | 0 | 无回归 |
| test_r10_projection_pg | 0 f / 15 e | 0 f / 15 e | 既有缺口原样（库注释标记 `dianzi:r10_projection_20261016:owned-test-only` 未由容器预置） |
| test_r14_default_runtime_pg | 1 f | 1 f | D 注残留稳定复现（独立库复跑同形；stamp 未改变 0 行机制） |
| test_r14_read_adapters_pg | 1 f | 1 f | 甄别预测未兑现（见 4.4） |
| test_r14_langgraph_workflow_pg | 0 f | 0 f | 第一轮 1 例一次性失败，第二/三轮均 34 全绿排除回归 |
| test_r18_api_key_credentials_pg | 0 | 0 | 无回归（pg_case 改动安全） |
| test_r18_api_key_post_lock_time_pg | 2 f | 0 f | **全绿** |
| test_r02_knowledge_revisions | 0 | 0 | 无回归（prepared_submission 直改） |
| test_r02_dimension_persistence | 0 | 0 | 无回归 |
| test_r02_relation_identity_regressions | 0 | 0 | 无回归 |

**合计：46 → 13 failed（转绿 33）；errors 18 → 18（既有缺口不变）；一次性失败 1 例（已排除）。**

## 4. 仍红明细与分类

1. **A-harness（7 例，test_r06_source_excerpt_event_proof_pg）**：`trace()` 写 `reports/runs/recovery_r06_source_excerpt_event_proof_20261016/pg_case_*.json`，容器 `/repo:ro`（scripts/dev_integration_container.py:261）→ `OSError [Errno 30]`。B 根因确认已修：8 例的业务断言（succeeded/partial/evidence_not_current_supported）全部通过后才死于写文件；无 trace 调用的 `test_revision_replacement_retains_history_and_revalidates_new_proofs` 已全绿。与甄别报告 §4 预警逐字吻合。修法（后续批次）：harness 可写挂载仓库目录，或评审后把 trace 输出改 tmp_path（测试侧一行）。
2. **legacy/显式 unknown 行可读性（3 例，OQ-5 裁决范围）**：test_r04_knowledge_api_pg::test_legacy_null_dates_no_invented_verified_locator（legacy=True 种子，CR 明示"legacy 分支保持 server_default {}"）；test_r04_api_review_regressions::test_cursor_is_reauthorized_after_session_revocation（其自身种子无修订，共享库 r04_api_20261015 内 legacy 行使 /v1/events 列表 fail-closed 503）；test_r06_document_api_pg::test_document_old_metadata_is_explicit_unknown_and_never_relabels_historical_title（:266 故意把旧修订 `source_metadata` 置 `{}` 构造显式 unknown 探针，混合模式读取现按合同 503）。三例均非种子滞后，需 r05/OQ-5 同一裁决。
3. **D 类（2 例）**：test_r07_job_execution_pg::test_full_recorded_nvd_budget_failure_is_retained_without_wire_or_losing_other_dimensions（与甄别时同用例，'partial'=='failed'，需维度 error_code 取证，本轮未处理）；test_r14_default_runtime_pg::test_http_real_enqueue_read_receipts_and_idempotency_conflict（CR 预期的"复跑观察"已完成：独立库下稳定复现 200+items=0，stamp 未消除，0 行机制仍需带 stop_reason 取证）。
4. **甄别预测未兑现（1 例，test_r14_read_adapters_pg::test_real_pg_source_acl_revocation_removes_history_and_invalidates_cursor_without_epoch_bump :380）**：prepared_submission 已 stamp（同文件 find_changes 各步全绿），但 get_advisory 在 ACL 撤销态仍 `FAILED == 'partial'`——event_detail 链路在隐藏源状态抛出的具体错误码未被 harness 命令（固定 `pytest <file> -q --no-cov`）捕获，属"旧行/隐藏源可读性映射"语义，建议与 OQ-5 家族一并取证裁决；下轮可用一次性探针或 `-l` locals 捕获 error_code。
5. **一次性失败（已排除，非仍红）**：test_r14_langgraph_workflow_pg [B2b-2] 第一轮 `InvalidActorReferenceError`（actor_references.py:375，collector 任务 guard_session 复合校验）。guard 校验不读取 revision 元数据，与种子 stamp 无因果链；第二轮（独立库）与第三轮（同 run_id 同序列同库精确复现）均 34 全绿。判定为非确定性时序失败，建议 Root 在全量复跑中留意该点位。

## 5. 合同与计划偏差

- 偏差 1（见 §1）：在任务书 7 文件之外编辑了 5 个种子落点文件。依据为 CR 改动节第 4/5 条明文 + 甄别报告 file:line；已先行上报协调者未获答复。风险控制：全部为新增 stamp 字段，35 文件容器复跑证明 24 个原本全绿的消费方文件（r02×3、r06×5、r07×8、r10×4、r12、r14×2、r18_credentials）零回归。
- 偏差 2：CR 验收语"预期上述 56 例转绿"在算术上不可达——56 例含其自身明确排除的 r05(21)+r04_source_documents(1)，且第 2 条对 r06_source_boundary/r14_read_adapters 的连带修复断言、第 4/5 条的文件归属经核查有误。本报告以逐例实证替代该预期值：CR 范围内可修复 41 例根因（33 例可观转绿 + 7 例被容器只读拦截 + 1 例 read_adapters 预测未兑现），其余属 OQ-5/D 类。
- 未运行：全量离线套件（任务书未要求本轮执行；宿主定向 1163 passed 覆盖 unit/contract/security 的 -k 子集）。未 commit（按指令留给 Root）。

## 6. 证据文件清单（reports/runs/batch22_d_triage/）

- seed_alignment_expectations.json（12 文件 old/new raw sha256 + 容器只读约束预注记）
- host_targeted.txt（宿主定向 pytest + collect-only + 退出码）
- plan_batch22_goal1_rerun.json / goal1_baseline_counts.json / goal1_container_run_log.txt
- plan_batch22_goal1_recheck.json / goal1_recheck_run_log.txt
- plan_batch22_goal1_seqcheck.json / goal1_seqcheck_run_log.txt
- 35+3 个 *_pf.txt（第一轮）；test_r14_{langgraph_workflow,read_adapters,default_runtime}_pg_pass1_pf.txt（第一轮快照）与 *_recheck_pf.txt（第二轮）；第三轮输出在同名 *_pf.txt（5 文件全绿）
- 本报告

本次写作结束时间：2026-10-25T06:19:50+08:00
最后更新时间：2026-10-25T06:19:50+08:00
