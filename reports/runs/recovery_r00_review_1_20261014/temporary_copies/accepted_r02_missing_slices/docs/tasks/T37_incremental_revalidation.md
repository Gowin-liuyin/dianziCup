
# T37 · 变化失效、局部重算与并发一致性

阶段：G4｜前置：T36、T07｜评分/要求：F1、F2、F3、E1、P1、X1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/04_workflows_and_algorithms.md`
- `docs/plan/06_testing_and_evaluation.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/revalidation/`；`backend/src/ai_intel/workers/`；`backend/tests/integration/`；`fixtures/synthetic/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/revalidation/service.py`；`fixtures/synthetic/change_sequences.json`；`reports/tasks/T37.md`。

测试/检查位置：`backend/tests/integration/test_t37_incremental_revalidation.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 计算旧引用依赖∪scope watchers∪新增资产候选∪负缓存命中的完整影响集合。

2. 变更事务提升scope epoch并写outbox；读取发现旧epoch即stale，不等待worker才承认已过期。

3. 对目标最新版本合并重算任务，复用未变节点但保留全量重算参照路径。

4. 提交时CAS比较知识/资产/规则版本；落后任务不得覆盖新结果，必要时重排。

5. 重算失败保留stale、错误和告警，不回退成current；变更原因与旧新结果可展示。

6. 回放扩大/缩小、撤回、别名、乱序、并发与worker中断，验证与全量结果一致。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T37-C01 | 范围<1.4.2扩大为<1.5.0 | 此前未命中的1.4.8资产被重新判断 |
| T37-C02 | 范围缩小 | 撤回不再成立的旧判断 |
| T37-C03 | 变更后失效worker尚未运行 | 读接口仍不能把旧结果标current |
| T37-C04 | 旧worker晚于新worker提交 | CAS拒绝旧覆盖 |
| T37-C05 | 负结果缓存与新资产 | 都进入更新集合 |
| T37-C06 | 相同最终快照全量/增量 | 候选与结构化状态一致，否则测试失败 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/integration/test_t37_incremental_revalidation.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T37.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07待核验）

最终需要：R16:T37。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
