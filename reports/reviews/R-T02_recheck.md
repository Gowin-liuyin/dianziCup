# R-T02_recheck · T02 修复后定向复核（P-1/P-2/P-3 闭合确认）

- 性质：R-T02（needs_changes）修复后定向复核；审查者=原审查者 R-T02（非修复作者，修复者=主控工程 Agent）
- 时间：2026-09-30 23:42—23:47（本地时区）｜工作目录：`D:\dianzi`｜本文件为新增，未覆盖 [R-T02.md](R-T02.md)（原报告及其 [R-T02_runs.log](R-T02_runs.log) 保持原样，构成审计链）
- 范围：仅定向复核 ①T02.md/§9 附录与 task_state 一致性 ②Node 引擎守卫 ③C03 类型错误负例测试 ④uv sync --locked 补测记录 + 复跑 pytest/ruff/mypy/verify_plan；未重审其余深检项（沿用 R-T02.md 结论）
- 边界声明：`backend/src/ai_intel/domain/`、`contracts/schemas/`、`tests/unit/test_t04_domain_contracts.py` 为 T04 并行实施产物，**不计入 T02 违规**（`backend/src/ai_intel/infrastructure/settings.py` 经内容归属为 T03/T04 轨道产物，同此口径）。

## 1. 修复后文件版本绑定（SHA-256）

| 文件 | 字节 | SHA-256 | 与 R-T02.md §1 基线对比 |
|---|---|---|---|
| backend/tests/unit/test_t02_project_skeleton.py | 6027 | B56E096AF5F7774F0B924F4F385C0054E579DA9BC3A175CB970665CD7FFEBD28 | **变更**（+2 新测试，预期修复面） |
| frontend/package.json | 787 | 143051F567E94183D6015F570C3532301E83F68AD5D71B3701483BC848A6FA57 | **变更**（+engines，预期修复面） |
| frontend/.npmrc（新增） | 19 | 7151CF397DEF0C2CB0AB65643701D27D335A72C90F775675B5F826BC7005818A | 新增 |
| frontend/.nvmrc（新增） | 3 | 68CA3FBA3B7E864770CB61AEB306D4BD4354B68AB4DD38450860C5D823E42A53 | 新增 |
| reports/tasks/T02.md | 21853 | 7AD99FA5C5DC23BDA43161EFC3BF98C6D4880C74A7EFE122B9567FE7969D4E70 | **变更**（§9 附录+字节数更正，预期修复面） |
| progress/task_state.json | 12533 | 923BFE6D5A7F20CE31E9277AF7FDCA8A6DE9523CBBC7B201C883799A9CED2D88 | **变更**（implementation=complete，预期修复面） |
| backend/pyproject.toml | 1296 | EADFCE5B…FFF27 | 未变（与 R-T02 §1 一致） |
| backend/uv.lock | 47709 | 376092D3…B126D | 未变 |
| scripts/dev.py | 3202 | 63318A2D…6F1564 | 未变 |
| frontend/package-lock.json | 177770 | 2ADCF1CA…A9AFD | 未变 |
| frontend/tsconfig.json / App.tsx / App.test.tsx / app.py | — | 与 R-T02 §1 逐一相同 | 未变 |

**变更面=预期修复面，无意外漂移**；未变对象哈希与 R-T02.md §1 逐项一致。

## 2. P-1 报告与状态一致性 —— **闭合**

- `reports/tasks/T02.md` 全文 `package-lock.json` 字节数 4 处（§1.2/§2-C01/§4-18/§6.1）均为 **177770B**，与最终落盘锁实测一致，且与 CR-002 的 177770B 口径统一。
- §9 修复附录（189—200 行）逐项登记修复内容与验证，并**公开披露**「206324B → 177770B」的替换及其原因（vitest 升级后重生成的最终值）——原值仍可追溯（t02_frontend_checks.log 第 3 行、R-T02.md §1 均留有 206324B 记录），非静默改史。
- `progress/task_state.json` T02 `implementation: complete`、`status: awaiting_review`（未自批 accepted，纪律保持）。**P-1 关闭。**
- 遗留小建议（不阻断）：§4 命令表第 18 行为历史命令输出记录，现写 177770B 而该次运行当时打印的是 206324B；附录已披露替换故可接受，若能标注「中间值 206324B→最终 177770B」更严谨。

## 3. P-2 C02 Node 子项引擎守卫 —— **闭合（含行为级证明）**

- 三件套在位且内容正确：`package.json` `"engines": {"node": ">=24.0.0 <25.0.0"}`（24.13.1 满足、20/22/25 均拒绝）；`frontend/.npmrc` `engine-strict=true`；`frontend/.nvmrc` = `24`。
- 新测试 `test_wrong_node_version_is_rejected_by_engine_guard` 断言三件套在位（防回归漂移）。
- **行为级证明（本复核实测，非配置文本自证）**：临时目录放 `engines: {"node": ">=99.0.0 <100.0.0"}` + `engine-strict=true`，`npm install --dry-run` → **exit 1**，`npm error code EBADENGINE / Required: {"node":">=99.0.0 <100.0.0"} / Actual: {"node":"v24.13.1"}` —— engine-strict 机制对不匹配 Node 版本给出**明确拒绝与明确错误信息**，不静默运行、不绕过锁。配合 engines 收窄至 24.x，「错误 Node 版本→明确版本不兼容」成立。**P-2 关闭。**

## 4. P-3 C03 自动化负例 —— **闭合**

- 新测试 `test_mypy_rejects_injected_type_error_and_recovers`：向 `src/ai_intel/` 注入含 **arg-type** 类型错误（传 str 给 int 参数）的探针 → `python -m mypy src` 断言 **returncode != 0 且输出含 `arg-type`** → `finally` 删除探针 → 复跑断言 **exit 0**。
- 判定：断言精确锚定类型错误码（排除语法错误等假阴性/假阳性，正中 R-T02 P-3 与任务卡「故意加入类型错误」口径）；有清理与复原验证，不吞异常；探针为临时文件、finally 保证删除。**P-3 关闭。**
- 小建议（不阻断）：探针临时写入 `src/ai_intel/` 仓内（finally 清理），极端 kill 场景可能残留，可改临时目录+mypy 路径参数；非必需。

## 5. 复跑结果（修复后实测）

| # | 命令 | 工作目录 | 起止（23:4x:xx） | 退出码 | 结果 |
|---|---|---|---|---|---|
| 1 | `uv run pytest tests/unit -q` | backend | 43:33.630—43:38.634 | 0 | **24 passed / 0 failed / 0 skipped**（T02 文件 11 项含 2 新测试 + T04 文件 13 项）；覆盖率实测 **81.64%**（256 stmts，门槛 60% 达成） |
| 2 | `uv run ruff check .` | backend | 44:13.128—44:13.348 | 0 | All checks passed! |
| 3 | `uv run ruff format --check .` | backend | 44:13.350—44:13.468 | 0 | 12 files already formatted |
| 4 | `uv run mypy src` | backend | 44:13.469—44:13.862 | 0 | Success: no issues found in **10** source files |
| 5 | `verify_plan.py --root --baseline plan_baseline_t01.json` | 根 | 44:16.549— | 0 | PLAN_OK，**冻结文件仍未被触碰** |
| 6 | `reports/runs/t02_gap_closure.log` [A] 复核 | — | — | 记录 exit=0 | `uv sync --locked` 成功记录在案（Resolved/Audited 33 packages），R-T02 原审查亦独立复现同结果，双证一致 |

- 测试数与 §9 附录声明一致（24/24）；覆盖率实测 81.64% 与 §9 所记 96.31% 有差异——源于并行轨道文件集合变化（本复跑时 `infrastructure/settings.py` 39 stmts 0% 覆盖拉低总值），两者均 ≥60% 门槛、均非造假；**建议**（不阻断）在报告中标注覆盖率的测量时点与文件集合，避免并行开发期数字漂移被误读。
- mypy 报 10 source files（§9 写 9 文件）同因 T04 并行落盘，非缺陷。

## 6. 遗留条件与建议（承接 R-T02.md §4，不阻断本结论）

1. **P-4（条件）**：CR-002（vitest ^2→^3）为记录性质变更单，待人工知悉/追认；驳回须按 CR-002 §5 成对回退。
2. P-5（建议）：package-lock 10 条目缺 version/resolved/integrity，择机重生成锁并核查。
3. P-6（建议）：T03 将 dev 密码占位值改为环境变量注入（AGENTS §7）。
4. P-7（建议）：dev.py 死参数/类定义顺序/不可达 raise、测试 docstring case-ID 标注（ready 503 误标 C06）、仓根 .gitignore、§4 历史输出标注与覆盖率测量时点标注（本复核新增 2 条同类建议）。
5. C05「缺必须配置→清楚配置错误」路径仍待 T03 配置分层落地后补断言（R-T02 已如实登记，非本复核范围）。

## 7. 结论

**accepted。**

依据：R-T02 的 3 项必须修复（P-1/P-2/P-3）全部以实际文件与实测证据闭合——P-1 报告字节数全文一致且替换有附录公开披露、task_state 与报告状态一致；P-2 引擎守卫三件套在位且 **EBADENGINE 行为级拒绝实测成立**（不再存在「错误 Node 版本静默运行」缺口）；P-3 类型错误负例测试真实注入 arg-type 并断言非零+复原，负例非恒真。修复后全量单测 24/24、ruff/format/mypy 全 0、verify_plan 基线 PLAN_OK（冻结文件未动），变更面恰为预期修复面、无意外漂移，无伪造/无密钥/无状态造假（不触发升级）。

本 accepted 为**独立审查结论，不构成人工审批**；P-4（CR-002 追认）等遗留条件按 §6 承接，G0-D3/D4（CR-001 追认、20 合成案例人工复核）等阶段遗留不因本复核改变。T02 可按 G1 顺序推进 T03+。
