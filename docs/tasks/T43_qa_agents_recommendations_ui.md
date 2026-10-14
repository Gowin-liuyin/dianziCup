
# T43 · 问答、Agent轨迹和推荐交互

阶段：G4｜前置：T40、T35、T39｜评分/要求：F3、A1、D2、P3

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/05_api_and_tool_contracts.md`
- `docs/plan/09_operations_delivery.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`frontend/src/features/`；`frontend/tests/`；`frontend/e2e/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`frontend/src/features/questions/`；`frontend/src/features/investigations/`；`frontend/src/features/recommendations/`；`reports/tasks/T43.md`。

测试/检查位置：`frontend/tests/t43_qa_agents_recommendations_ui.test.tsx`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 实现多轮问答，区分快速完成与异步调查，保留job_id并可刷新恢复。

2. 回答逐关键结论展开证据、规则、版本与限制，不展示模型私有思考或假Agent台词。

3. 调查页仅根据真实ToolRun展示角色、目标、工具、状态、耗时、证据和停止原因。

4. 实现订阅创建/编辑/停用、推荐列表/原因/已读，以及修订后推荐变化。

5. 页面测量提交到完整回答时间，首字或加载动画不冒充完成。

6. 用不同用户配置、缺证、失败、超时和预算耗尽走完整交互测试。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T43-C01 | 异步调查刷新页面 | 仍可恢复同一job状态和结果 |
| T43-C02 | 工具失败 | 轨迹真实记录而非生成成功台词 |
| T43-C03 | 多轮问题与证据 | 引用当前合法快照且可展开 |
| T43-C04 | 不同订阅 | 推荐原因与资产不同，不是统一榜单 |
| T43-C05 | 预算耗尽/缺key | partial/not_configured可见，不显示已完成调查 |
| T43-C06 | 退订/越权访问 | 状态正确且无法读他人推荐与会话 |

## 6. 执行与回归

主检查：

```text
cd frontend && npm run test -- --run tests/t43_qa_agents_recommendations_ui.test.tsx
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T43.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07已独立核验生效）

最终需要：R05:T43、R12:T43、R14:T43、R15:T43、R17:T43。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
