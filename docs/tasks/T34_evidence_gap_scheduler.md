
# T34 · 关键证据缺口驱动调查与停止

阶段：G4｜前置：T33｜评分/要求：A1、F3、P3、X1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/03_data_contracts.md`
- `docs/plan/04_workflows_and_algorithms.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/investigation/`；`backend/tests/unit/`；`config/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/investigation/scheduler.py`；`config/investigation_policies.yaml`；`reports/tasks/T34.md`。

测试/检查位置：`backend/tests/unit/test_t34_evidence_gap_scheduler.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 从ConditionEvaluation和问题槽位生成MissingRequirement，列出现状、可填工具与是否可能改变结论。

2. 在不改事实的副本中试置unknown/conflict两种情况，做有限关键性分析；无法可靠分析则保守保留候选。

3. 对候选先授权/预算筛选，再按关键性、直接来源、可用性和成本排序；LLM只能选候选action ID。

4. 实现已足够、不可获取、预算耗尽、需授权、关键冲突五种停止路径。

5. 保留固定流程策略开关，冻结相同模型、工具和预算供对照，不预先断言动态更好。

6. 记录每步选择原因、补齐内容和停止原因，不能把LLM自报置信度当信息增益概率。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T34-C01 | 资产版本未知 | 优先查授权清单而非继续搜背景论文 |
| T34-C02 | 关键条件已全知 | 结束，不为展示多Agent继续调用 |
| T34-C03 | 未知项不影响当前结论 | 排序降低但不改写为已知 |
| T34-C04 | 模型选择候选外工具 | 拒绝并记录策略错误 |
| T34-C05 | 预算用完仍缺证 | 返回partial/unknown，不补写肯定结论 |
| T34-C06 | 对照同输入 | 固定与动态流程配置可复跑，费用和完成率均记录 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/unit/test_t34_evidence_gap_scheduler.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T34.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07待核验）

最终需要：R14:T34。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
