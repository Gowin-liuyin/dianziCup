
# T32 · 工具注册、权限、预算和调用记录

阶段：G4｜前置：T18、T25、T28、T30｜评分/要求：A1、E1、F3

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/05_api_and_tool_contracts.md`
- `docs/plan/04_workflows_and_algorithms.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/investigation/`；`backend/tests/security/`；`config/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/investigation/tools.py`；`backend/src/ai_intel/investigation/gateway.py`；`reports/tasks/T32.md`。

测试/检查位置：`backend/tests/security/test_t32_tool_gateway.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 实现05中列明的ToolSpec与注册表，每个工具有输入输出schema、角色、可填槽位、超时和权限。

2. gateway服务端注入tenant/范围/预算，模型自报role、skip_validation、任意URI全部拒绝。

3. 实现call_key、成功结果复用和费用预留；外部结果不明不能声称exactly-once或免费重试。

4. 区分succeeded/no_result/partial/failed/denied/not_configured，保留搜索范围与证据ID。

5. 私有清单只给授权资产角色必要字段，公开研究角色不能读取全部私有数据或密钥。

6. 保存脱敏ToolRun、错误与停止原因，检查总任务重试而不是每个角色各自无限调用。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T32-C01 | 允许工具与参数 | 记录真实执行轨迹与证据 |
| T32-C02 | 模型指定其他tenant/隐藏权限开关 | 拒绝，不影响服务端scope |
| T32-C03 | 预算耗尽 | budget_exhausted且不发外部调用 |
| T32-C04 | 同call_key已有成功结果 | 复用并记录cache，不重复计实际网络调用 |
| T32-C05 | 失败与无结果 | 状态不同，缺key不算空搜索 |
| T32-C06 | 外部材料要求读取秘密/任意shell | 工具不在注册表，无法执行 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/security/test_t32_tool_gateway.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T32.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
