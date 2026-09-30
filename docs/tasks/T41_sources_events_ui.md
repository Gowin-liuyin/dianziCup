
# T41 · 来源、事件、维度与证据详情页面

阶段：G3｜前置：T40、T17、T21｜评分/要求：F1、F2、D2、R1

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

目标产物：`frontend/src/features/sources/`；`frontend/src/features/events/`；`frontend/src/features/evidence/`；`reports/tasks/T41.md`。

测试/检查位置：`frontend/tests/t41_sources_events_ui.test.tsx`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 建立来源列表，展示类别、增量能力、真实接通状态、最近成功/失败和采集延迟。

2. 事件列表提供产品/类型/时间过滤与分页，来源数和独立事件数不混淆。

3. 事件详情展示全部富化维度及available/not_found/not_applicable/blocked/failed，不只显示成功项。

4. 证据详情展示原文revision、quote位置、发布日期/修改/采集时间与支持关系。

5. 加入事件归并/修订时间线和冲突展示，原文链接失效不隐藏已保存证据。

6. 所有页面用真实API，开发fixture显著标识，前端不重新计算业务结论。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T41-C01 | 多来源同事件 | 显示一个事件与多个来源，而非多个漏洞 |
| T41-C02 | 某富化维度失败 | 错误状态可见且不会显示全部完成 |
| T41-C03 | 引用点击 | 打开对应历史版本准确片段 |
| T41-C04 | 未知发布时间 | 展示未知，不替换为采集日期 |
| T41-C05 | 长版本表和中文正文 | 不截断关键条件、表格可读 |
| T41-C06 | 无权限原文 | 不显示敏感标题/路径，按API拒绝 |

## 6. 执行与回归

主检查：

```text
cd frontend && npm run test -- --run tests/t41_sources_events_ui.test.tsx
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T41.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
