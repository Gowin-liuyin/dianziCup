
# T33 · 四角色Agent固定工作流与持久化

阶段：G4｜前置：T31、T32、T07｜评分/要求：A1、F3、E1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/02_architecture.md`
- `docs/plan/04_workflows_and_algorithms.md`
- `docs/plan/05_api_and_tool_contracts.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

需要已核验LangGraph版本和持久化依赖；真实效果需模型资源。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/investigation/`；`config/prompts/`；`backend/tests/integration/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/investigation/graph.py`；`config/prompts/agents/`；`reports/tasks/T33.md`。

测试/检查位置：`backend/tests/integration/test_t33_agent_workflow.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 实现planner、intelligence_agent、asset_agent、answer_agent四个角色及不同输出schema/工具允许集。

2. 使用LangGraph表达单次调查状态；固定流程先作为基线：规划→资料/资产调查→校验研判→回答。

3. 通过PostgreSQL检查点恢复图，业务证据与任务仍以自身表为准，不把InMemorySaver当持久化。

4. 外部副作用走已幂等工具gateway；图恢复不自动把所有前序工具再执行一遍。

5. 定义queued/running/waiting_approval/partial/failed终态与停止原因；不是四个字符串轮流打印。

6. 任务完成可追溯到实际工具和证据；流程图由实际节点关系生成并保存。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T33-C01 | 复杂资产问题 | 四角色承担不同实际子任务且共享证据ID |
| T33-C02 | 无需资产的事实问题 | 可以跳过无意义分支，日志说明 |
| T33-C03 | worker重启 | 从检查点恢复，不丢任务或无界重复外部调用 |
| T33-C04 | 无授权关键工具 | waiting_approval/partial，不编造调查结果 |
| T33-C05 | 来源含角色重置指令 | 不改变工具权限或系统任务 |
| T33-C06 | fixture模型流程 | 明确fixture，不能计为真实Agent效果 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/integration/test_t33_agent_workflow.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T33.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07已独立核验生效）

最终需要：R14:T33。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
