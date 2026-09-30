
# T46 · 标注工具、开发集与盲测隔离

阶段：G5｜前置：T01、T04、T09、T10｜评分/要求：P2、P3、A1、D1、X1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/06_testing_and_evaluation.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

需要人工标注与裁决；Agent可做工具和候选数据，不能自认独立金标已完成。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`benchmarks/`；`scripts/annotation/`；`contracts/schemas/`；`reports/acceptance/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`benchmarks/manifests/`；`scripts/annotation/`；`reports/acceptance/dataset.md`；`reports/tasks/T46.md`。

测试/检查位置：`reports/acceptance/t46_checklist.md`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 固定case schema、事件家族分组、来源快照、数据类型、许可、预期事实/条件/状态和裁决记录。

2. 建立导入/校验/导出标注的简单工具，支持两位标注人和分歧列表，不默认模型即真值。

3. 整理开发案例并扩展真实事件/资产/问答/变化/配对安全任务，合成与真实分开计数。

4. 划分dev/demo/holdout，转载、译文、修订和派生题必须同组；holdout答案不进产品或Agent常规上下文。

5. 生成数据manifest与hash，扫描prompt示例/索引/fixtures中的事件泄漏。

6. 人工未完成时输出待标注清单，不宣称已有金标或足量数据；实际规模按资源冻结。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T46-C01 | 同事件的多语言/修订/题目 | 保持同一split |
| T46-C02 | 双人标签不一致 | 进入裁决而非自动多数/模型裁定 |
| T46-C03 | 合成资产与真实事件 | data_kind和来源清楚分离 |
| T46-C04 | holdout答案进入prompt或镜像 | 泄漏检查失败 |
| T46-C05 | 缺来源/许可/观察时间 | 标注校验失败或明确未知字段 |
| T46-C06 | 人工标签未完成 | awaiting_human_label，不生成“实测准确率” |

## 6. 执行与回归

主检查：

```text
按下表逐条核验实际文件、日志或人工记录；不创建空测试冒充通过。T01建立校验脚本后补跑 python scripts/verify_plan.py。
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T46.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
