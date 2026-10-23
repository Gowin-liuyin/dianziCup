# Root · 批次19可运行装配验收与入档

文档首次创建时间：2026-10-24T01:30:38+08:00
本次写作开始时间：2026-10-24T01:30:38+08:00
最后更新时间：2026-10-24T01:30:38+08:00
任务状态：awaiting_review；实现 complete（离线范围）；整 G-C 未过门，6 小时窗口未启动。
工作分支：codex/full-delivery-recovery；导入前 Root SHA ae6f623d1a2add4e7804df31c862e1478326e3d7

本批验收 2026-10-19 至 2026-10-23 期间已完成但未提交的"默认装配可运行化"工作并补齐证据链：`scripts/migrate.py`（迁移入口，退出码合同 0/1/2）、`scripts/load_main_path_story.py`（主路径故事夹具加载，重复执行返回 already-present）、`backend/src/ai_intel/fixtures/main_path_story.py`、三个新后端单测（story mode / story range / investigation queue binding）、前端 tasks 工作区（`App.tsx` 挂载 `#tasks`）、`event-enrichment-action.tsx` + `enrichment-client.ts`（富化动作）、`knowledge_contracts.py`/`knowledge_read_service.py`（`business_version`、`data_mode` 进读取 DTO）、compose `investigation` profile 与 README 重写。本批不改变任何整卡或阶段状态。

10-23 的既有运行证据 `reports/runs/story_fixture_20261023/`（migrate_exit=0、story_exit=0、verify 全部断言通过、rerun 返回 already-present）随本批入档并在此引用；该证据为当日真实执行产物，本批未重复冒充为新结果。临时库口令经 `pg.env` 外部注入，仓库内无口令字面量，已核查。

## 本批修复记录

前端 6 个失败测试的根因均为本批有意变更后测试夹具/断言未跟上，处置为更新测试期望，未删除测试、未弱化断言、未改组件行为：`App.test.tsx` 中 `#tasks` 已挂载真实 TaskWorkspace，原占位文案断言（/页面不会通过动画递增进度/）更新为断言真实工作区标题与空态描述，并保留对该占位文案 `toBeNull` 的不伪造进度保证；`event-workspace.test.tsx` 的本地 `detailFixture` 缺少本批契约新增的必填 `business_version` 字段导致 5 个测试的详情请求被 DTO 校验拒绝（502 invalid_response），补 `business_version: 1` 对齐共享夹具。

ruff 0.16.9（`>=0.8,<1.0` 浮动解析）对 7 个历史未改测试文件新报 I001。其中 `tests/unit/test_r12_conversation_boundary_fix1.py` 直接完成导入排序（79 例定向单测含它全过）；6 个 r07/r12 PG 测试文件的导入顺序承重（先导入兄弟测试模块才使跨目录裸导入可解析），机械排序会破坏收集，故在 `backend/pyproject.toml` 按既有 RUF001-003 豁免先例做定点 per-file-ignores I001 并注明原因，文件内容保持 HEAD 原样。I001 初次 `--fix` 曾破坏 6 个 PG 文件收集，已当场回退重做，最终 `ruff check .` 全绿。

恢复 `backend/tests/r07_input_audit_helpers.py`（162 行）：该文件由未合并入本分支的切片提交 136359106 添加（`git merge-base --is-ancestor` 确认非祖先），而其 6 个导入者已在本分支，缺文件导致这些测试自始无法收集。自历史提交恢复属证据驱动修复；恢复后 `tests/integration/test_r07_input_audit_legacy_pg.py` 可收集 7 例。`tests/security/test_r07_input_audit_security_pg.py` 等仍因跨目录裸导入 `test_r07_input_audit_receipts_pg`（依赖 tests/integration 先收集的 sys.path 副作用）在 unit+contract+security 范围内不可收集——历史遗留，不属本批新引入，保留待后续批次处理。

另记录：定向单测首跑因子集覆盖率 26.94% 触发 `--cov-fail-under=60` 整体退出 1（73 例全过），复跑加 `--no-cov` 取得退出码 0；全量覆盖率门在批次 20 全量运行时照常执行，本批未放宽任何门。

## 验证

| 验证 | 时间（+08） | 退出码 | 实际结果 |
| --- | --- | --- | --- |
| uv run pytest 5 个目标文件 -q（含覆盖率门） | 2026-10-24T01:1x | 1 | 73 passed；子集覆盖率 26.94% 未达 60% 门 |
| 同上 + test_r12_conversation_boundary_fix1 + --no-cov | 2026-10-24T01:2x | 0 | 79 passed |
| uv run ruff check . / format --check . / mypy src | 2026-10-24T01:2x | 0 / 0 / 0 | 全绿（I001 处置后） |
| 恢复 helper 后 ruff check 全仓 | 2026-10-24T01:4x | 0 | All checks passed |
| npm run typecheck | 2026-10-24T01:4x | 0 | tsc --noEmit 干净 |
| npm run test | 2026-10-24T01:4x | 0 | 64 文件 799 测试全过（修复前 6 failed） |
| npm run build | 2026-10-24T01:4x | 0 | 92 模块，dist/ 生成 |
| npm run test 抽查两修复文件 | 2026-10-24T01:5x | 0 | 24/24 passed |

集成、安全、E2E、live、manual 均未运行（not_run），批次 20 全量离线基线另行记录。`frontend/tsconfig.tsbuildinfo` 全程未入暂存区；`.zcode/` 为会话配置目录，保留未跟踪不提交。

本次写作结束时间：2026-10-24T01:30:38+08:00；本批为有界验收与 checkpoint，不是阶段验收或 push。
