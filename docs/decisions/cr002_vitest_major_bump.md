# CR-002 · 前端测试工具主版本升级（vitest ^2 → ^3.0.5）

日期：2026-09-30（Goal 第 55 轮）｜性质：依赖主版本变更记录（AGENTS.md §2.5）｜变更实施者：主控工程 Agent（T02 实现）｜提出来源：T02 实测缺陷修复 + T02-C 文档批建议登记。

## 1. 变更内容

| 项 | 旧 | 新 | 范围 |
|---|---|---|---|
| frontend/package.json devDependencies.vitest | ^2.1.8 | ^3.0.5 | 仅开发期测试工具（不进入生产产物） |
| frontend/package-lock.json | 随之重新生成（工具生成，177770 B） | — | 真实锁文件 |

## 2. 变更理由（实测缺陷，非偏好升级）

vitest 2.x 自带 vite 5 副本，与项目 vite ^6.0.5 形成双副本，TypeScript 报
`Type 'PluginOption' (vite@6) is not assignable to 'PluginOption' (vitest/node_modules/vite@5)`，
`npm run typecheck` 与 `npm run build` 均失败（实测记录：reports/runs/t02_frontend_checks.log [3]/[5] 段）。
vitest 3.x 官方支持 vite 6，升级消除双副本后四项命令全绿（install/typecheck/test/build exit 0）。

备选（未采用）：vite 降级 ^5.4 —— 会把构建链整体回退到旧主版本，劣于升级测试工具。

## 3. 影响面

- 仅 devDependencies 与锁文件；生产构建产物（dist/）不受影响；后端无任何变化。
- 测试语义不变：`App.test.tsx` 断言未连接状态与防假数据，升级前后均通过（1 test passed）。
- 不涉及金标/门槛/分母/合同 JSON；冻结基线 source_hashes 三值不受影响（verify_plan 双模式持续 PLAN_OK，见 reports/runs/t02_backend_checks.log 末段）。

## 4. 验证记录

- npm install exit=0（package-lock.json 177770 B 工具生成）
- npm run typecheck exit=0；npm run test exit=0（1 passed）；npm run build exit=0（dist 生成 143.89 kB）
- npm audit：exit=1，存在开发依赖告警（明细见 reports/runs/t02_gap_closure.log [audit] 段），如实登记为「已审计、有告警未处置」，不隐瞒不夸大；处置留待安全批次（T45 前后）按实际风险评估。

## 5. 待人工知悉事项

本变更单为记录性质；如需驳回，回滚方式为将 vitest 恢复 ^2.1.8 并同时把 vite 降至 ^5.4（必须成对，否则双副本类型冲突复现）。
