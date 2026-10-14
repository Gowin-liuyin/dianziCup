
# T44 · 变化、运行监控与评测结果展示

阶段：G4｜前置：T40、T37、T49｜评分/要求：F1、E1、D2、P1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/03_data_contracts.md`
- `docs/plan/04_workflows_and_algorithms.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`frontend/src/features/`；`frontend/tests/`；`frontend/e2e/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`frontend/src/features/changes/`；`frontend/src/features/operations/`；`frontend/src/features/evaluation/`；`reports/tasks/T44.md`。

测试/检查位置：`frontend/tests/t44_changes_operations_ui.test.tsx`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 变化页展示旧/新事实与结论、影响对象、重验证状态和明确原因。

2. 运行页读取实际监控数据，显示来源新鲜度、积压、失败、索引滞后和stale结论。

3. 评测展示只读取带run_id/配置hash的结果，未运行栏目显示未测，不预填95%。

4. 对普通用户隐藏管理员指标和跨tenant计数，提供允许范围的任务状态。

5. 区分实时指标、历史结果、回放和fixture；图表无数据时为空态而非随机演示曲线。

6. 检查超长错误、分页和无权限响应，保证现场能打开证据记录。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T44-C01 | 公告范围扩大 | 页面展示新增受影响对象与变化原因 |
| T44-C02 | 更新任务失败 | stale/failed可见而非偷偷显示旧current |
| T44-C03 | 没有正式评测文件 | 未测，不显示目标95%为实际值 |
| T44-C04 | 真实监控有缺失区间 | 图上/文案保留缺口 |
| T44-C05 | viewer访问admin运维页 | 拒绝且无全局资产统计泄漏 |
| T44-C06 | 离线回放 | 显著显示快照时间和回放模式 |

## 6. 执行与回归

主检查：

```text
cd frontend && npm run test -- --run tests/t44_changes_operations_ui.test.tsx
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T44.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07待核验）

最终需要：R16:T44、R17:T44、R20:T44。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
