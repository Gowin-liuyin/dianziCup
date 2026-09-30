
# T42 · 资产、规则条件与证据包页面

阶段：G3｜前置：T40、T28、T29｜评分/要求：F2、F3、D2

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

目标产物：`frontend/src/features/assets/`；`frontend/src/features/assessments/`；`reports/tasks/T42.md`。

测试/检查位置：`frontend/tests/t42_assets_assessment_ui.test.tsx`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 实现JSON/CSV导入界面、预览、字段错误、完整性声明和授权提示。

2. 资产页展示当前与历史快照，内部确认与外部观察分栏，版本/观察时间未知显式显示。

3. 研判页展示条件树、证据、缺口、冲突、范围和freshness，软件适用与路径暴露不合并。

4. 支持修改合成演示快照后重算，同一后端路径处理，不在前端写预设结论。

5. 提供经过权限检查的证据报告/OpenVEX导出与失败说明。

6. 覆盖加载、部分完成、旧任务和无支持规则等状态。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T42-C01 | 三份不同版本快照 | 显示后端实际不同判定 |
| T42-C02 | 缺版本或观察时间 | unknown清楚可见 |
| T42-C03 | 外部不可达 | 不显示软件已修复 |
| T42-C04 | 调整演示配置后重算 | 新任务和快照关联，不改旧历史 |
| T42-C05 | 旧结论stale | 显示待重验证，不能仍用绿色安全状态 |
| T42-C06 | 导出权限/映射不足 | 显示具体限制，不生成假VEX |

## 6. 执行与回归

主检查：

```text
cd frontend && npm run test -- --run tests/t42_assets_assessment_ui.test.tsx
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T42.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
