# CR-public_read_projection_error_mapping_batch23

- 文档首次创建时间：2026-10-25T09:40:00+08:00
- 本次写作开始时间：2026-10-25T09:40:00+08:00
- 最后更新时间：2026-10-25T09:40:00+08:00
- 状态：awaiting_review（裁决执行件，依据 progress/DECISIONS_pending.md 裁决③建议项；GOAL 指令授权方式B）
- 关联：`48f96b5ba`（G-C/G-D revision mode 并入，本 CR 修正其公网读错误归类副作用）；`reports/runs/batch22_d_triage/triage_report.md` 家族2（其根因推断经执行时核实需修正，见下）

## 裁决（引用简报证据）

存储知识的来源模式无法按当前政策分类（`KnowledgeProjectionError`，`knowledge_read_service.py:61`，ValueError 子类）在公网读路由应归类为**配置态** `not_configured`（503，retryable=False），而非基础设施态 `public_read_unavailable`（503，retryable=True）。

- 失败证据：5 例、3 文件（`reports/runs/batch21_integration_unlocked/test_r18_public_read_producer_pg_pf.txt`、`test_r18_public_producer_fix1_pg_pf.txt`、`test_r18_public_producer_fix2_pg_pf.txt` 的 FAILED 行与 `'public_read_unavailable' == 'not_configured'` 断言差异）。
- 根因（执行时核实，修正 triage 推断）：`classify_revision_mode` 包装器（`public_extension_reads.py:117-122`）已把 `RevisionModeUnavailableError` 正确转为 `PublicReadUnavailable`；真实逃逸点是 4 个 `self.knowledge.*` 投影调用点抛出的 `KnowledgeProjectionError` 落入路由 `(SQLAlchemyError, ValueError)` 桶。
- 语义依据：数据修正前该状态恒定存在（配置态），retryable=True 会引发无意义重试；两个错误码均为 503 且不泄露数据（fail-closed 保持）；冻结独立评审探针（`reports/runs/r18_qualified_root_integration_20261017/original/test_independent_pg.py`，被 fix1/fix2 文件原样 import 断言）零改动。

## 改动

1. `backend/src/ai_intel/api/public_extension_reads.py`：新增模块级 `public_knowledge_projection` 包装（与既有 `classify_revision_mode` 同构），4 个公网读投影调用点（`read_evidence` citations、3 处 `event_detail`）经其调用，`KnowledgeProjectionError` → `PublicReadUnavailable`。
2. `backend/tests/integration/test_r18_public_producer_fix1_pg.py`：探针命名空间的 `seed_source_document` 引用换为"仅清空 source_metadata"的包装——冻结探针的 missing-mode 场景被批次22 共共 seeder 默认 stamp 波及（`probe` 经 importlib 冻结不可改；fix2 的探针再拷贝 fix1 的测试函数，`__globals__` 指向 fix1 模块字典，故此一处包装同时恢复 fix1/fix2 两文件的探针前置）。首次尝试 `partial(..., legacy=True)` 被实测否决：legacy 分支连带 `parse_status="legacy_unverified"`/`canonical_uri=None`，破坏 fix1:147 的 dimension 用例（`reports/runs/batch23_decisions/run2/`）。
3. 不改：路由映射表、`KnowledgeReadService` 内部语义（内部读路径仍抛 `KnowledgeProjectionError` 供内部处理）、任何测试断言值、任何冻结材料。

## 明确不做

- 不把普通 `ValueError`（参数校验类）改判为配置态——它们继续走 `public_read_unavailable`。
- 不动 `SQLAlchemyError` → `public_read_unavailable`（基础设施态）映射。
- 不触碰金标/阈值/分母与任何冻结评审材料。

## 验证

- 宿主定向：`uv run python -m pytest tests/unit tests/contract -q --no-cov -k "public"`（公网读离线合同全绿）。
- 容器逐文件：`test_r18_public_read_producer_pg.py`、`test_r18_public_producer_fix1_pg.py`、`test_r18_public_producer_fix2_pg.py`（钉定 run_id 同 batch21 plan）——5 例从失败清单消失。
- 全量回归：backend 离线全量 failed 仍为 0。

本次写作结束时间：2026-10-25T09:40:00+08:00
