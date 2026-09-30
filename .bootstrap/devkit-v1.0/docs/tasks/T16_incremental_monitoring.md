
# T16 · 持续增量采集、恢复与时效测量

阶段：G2｜前置：T10、T11、T12、T13、T14、T15、T07｜评分/要求：F1、P1、E1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/04_workflows_and_algorithms.md`
- `docs/plan/06_testing_and_evaluation.md`
- `docs/plan/09_operations_delivery.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/ingestion/`；`backend/src/ai_intel/workers/`；`backend/tests/integration/`；`config/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/ingestion/scheduler.py`；`reports/tasks/T16.md`。

测试/检查位置：`backend/tests/integration/test_t16_incremental_monitoring.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 将连接器接入Celery定时采集，live与backfill独立队列/游标，固定查询窗口。

2. 实现source+stream租约、分页提交、水位与重叠回看；抓取失败条目必须可恢复且可追踪。

3. 页面原始条目持久化后提交游标，解析/富化异步；不把未抓到原文的条目算已采集。

4. 实现退避、熔断、隔离坏记录、补采和健康状态；认证错误单独停止。

5. 记录发布到采集、采集到可问答延迟，缺时间与漏采单列；不填虚构持续运行数据。

6. 模拟中途宕机再启动，验证无漏页、无重复事件和无重复提醒。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T16-C01 | 多页窗口正常完成 | 每条原文有记录且水位正确 |
| T16-C02 | 第2页处理中断 | 恢复后补齐且不重复第1页业务结果 |
| T16-C03 | live与backfill并行 | 历史回补不推进实时错误水位 |
| T16-C04 | 迟到修订落在回看窗口 | 被再次发现并保留版本 |
| T16-C05 | 401/429/解析失败 | 状态和恢复策略各不相同 |
| T16-C06 | 缺发布时间/漏采 | 出现在报告分母与限制中，不被静默排除 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/integration/test_t16_incremental_monitoring.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T16.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
