
# T48 · 问答速度、吞吐与监测性能测试

阶段：G5｜前置：T35、T43、T47｜评分/要求：P1、P3、E1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/06_testing_and_evaluation.md`
- `docs/plan/09_operations_delivery.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

需要授权测试主机与模型成本上限；不能压测第三方公开服务。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`scripts/benchmarks/`；`experiments/`；`backend/tests/integration/`；`reports/acceptance/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`scripts/benchmarks/`；`reports/acceptance/performance.md`；`reports/tasks/T48.md`。

测试/检查位置：`backend/tests/integration/test_t48_performance_benchmarks.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 实现受控负载脚本，区分单用户/并发、冷/热缓存、简单/复杂、库内/联网任务。

2. 从请求进入到完整Answer或异步Job完成计时，另外保留首字但不替代完整延迟。

3. 对持续监测记录来源基准集合、漏采、无时间数据、p50/p95/max与超6小时项。

4. 记录硬件、模型、输入长度、索引规模、并发数、错误率和资源消耗，不能只测一个最好例子。

5. 分析真实瓶颈后提出小范围优化并做同配置前后测试，不能通过缩减问题难度优化数字。

6. 设置负载和费用上限，禁止对第三方来源或生产系统无授权压测。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T48-C01 | 200与202两条问答路径 | 均有完整完成时间 |
| T48-C02 | 缓存命中与未命中 | 分组报告且仍提供整体统计 |
| T48-C03 | 模型超时/失败 | 保留在总请求与错误统计中 |
| T48-C04 | 漏采和缺发布时间 | 单列且不从报告消失 |
| T48-C05 | 并发压测超预算 | 受控停止，不无界调用模型 |
| T48-C06 | 优化后数据集或模型变化 | 标非直接可比，不能假称纯系统提升 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/integration/test_t48_performance_benchmarks.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T48.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07待核验）

最终需要：R21:T48。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
