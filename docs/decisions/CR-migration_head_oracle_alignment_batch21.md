# CR-迁移head · forward head 期望对齐 0031 批次21（0019/0026 → 0031）

文档首次创建时间：2026-10-24T23:45:00+08:00
本次写作开始时间：2026-10-24T23:45:00+08:00
状态：awaiting_independent_review；授权依据：批次21 有界批处理指令 C3.3（oracle 对齐须确认当前 head 迁移文件为已审集成），范围仅限测试期望更新，迁移文件与生产代码零改动。

## 已审证据

迁移链当前唯一 forward head 为 `0031_public_task_bindings`（batch20 红清单 Section B2：两测共同根因是期望停留在 0019/0026 的机械性滞后）。`0031` 是已审集成结果，证据链（独立证据检索复核，报告 `reports/runs/batch21_red_zero/research/oracle_evidence_research.md`）：

1. 提交 `0291d1975`（2026-10-17T10:32:38+08:00）引入 `0031_public_task_bindings`；
2. `reports/reviews/recovery/G-E-R18-typed-task-binding-review-1-recheck-batch17-7acd9ea9.md`（第 17、55 行）非作者独审复查：真实 PG migration child 升至 0031 exit 0、0031 blob 未变；
3. 维护先例：`reports/tasks/Root-batch17-integration.md` 同批将 7 个 integration 测试的 head 期望 0030→0031 跟进，精确前后哈希存于 `reports/runs/recovery_reviewed_integration_20261016/root_batch17_forward_head_expectations.json`——本 CR 沿用同一证据格式与"仅测试期望替换"边界。

## 改动（两条合同测试，三个断言位置）

1. `backend/tests/contract/test_r11_r08_forward_migrations.py::test_production_chain_has_single_forward_head`
   - `get_heads()` 期望 `["0019_aggregate_observations"]` → `["0031_public_task_bindings"]`；
   - `iterate_revisions("head", "0016")` 期望清单 0019..0017 → 0031..0017（15 项，显式枚举）。只改 heads 断言会把红挪到该迭代清单，故一并更新。
2. `backend/tests/contract/test_recovery_forward_migrations_0023_0026.py::test_complete_alembic_chain_has_one_head_and_no_revision_gap`
   - `get_heads()` 期望 `[REVISIONS[-1][0]]`（0026）→ `["0031_public_task_bindings"]`；
   - 无缺口断言 `range(26, 0, -1)` → `range(31, 0, -1)`（0001..0031 完整链）；
   - `iterate_revisions("head", REVISIONS[0][1])` 期望 0026..0023 → 0031..0023（9 项）。

文件前后哈希记录于 `reports/runs/batch21_red_zero/oracle_alignment_expectations.json`。

## 明确不放宽的内容

- 两个文件的 REVISIONS 冻结元组（0018/0019 父链接冻结、0023..0026 冻结 DDL 逐条比对）全部不动，参数化覆盖不缩减。
- `test_entire_chain_compiles_offline_through_0026` 等 head 无关断言不动。
- 迁移文件、alembic 配置、生产代码零改动；`DROP TABLE`/业务导入禁令断言保持。

## C2 追加（2026-10-24T23:5x+08:00，同一 oracle 对齐类）

C2 盘点证实 `backend/tests/integration/test_r11_r08_migration_head_regression.py` 的 `inventory_engine` fixture 守卫断言 alembic 版本 `0019_aggregate_observations`（第 26 行；该文件自述"仅适配原修订守卫"，守卫当初按 0019 head 写定，与当前 head 0031 同源滞后）。按本 CR 证据链更新为 `0031_public_task_bindings`，一行改动。`backend/tests/r11_forward_fixtures.py` 经核实其 `run_migrations(url, target)` 的版本断言是动态的（`HEAD if target == "head" else target`），无滞后，不改。

## 验收与复跑

`cd backend && uv run python -m pytest tests/contract/test_r11_r08_forward_migrations.py tests/contract/test_recovery_forward_migrations_0023_0026.py -q --no-cov` 预期全绿；C3.4 全量确认无挪红。

本次写作结束时间：2026-10-24T23:45:00+08:00
最后更新时间：2026-10-24T23:45:00+08:00
