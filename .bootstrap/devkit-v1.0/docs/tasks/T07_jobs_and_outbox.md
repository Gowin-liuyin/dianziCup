
# T07 · 任务、事务outbox与幂等工作进程

阶段：G1｜前置：T05、T06｜评分/要求：F1、A1、E1、P1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/02_architecture.md`
- `docs/plan/03_data_contracts.md`
- `docs/plan/04_workflows_and_algorithms.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/workers/`；`backend/src/ai_intel/infrastructure/`；`backend/migrations/`；`backend/tests/integration/`；`infra/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/workers/jobs.py`；`backend/src/ai_intel/infrastructure/outbox.py`；`reports/tasks/T07.md`。

测试/检查位置：`backend/tests/integration/test_t07_jobs_and_outbox.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 建立JobRun、OutboxEvent和租约表，定义业务任务与Celery状态分工。

2. 实现enqueue_job，把业务记录和outbox同事务提交；relay只发布引用与最小元数据。

3. worker以唯一键认领任务，成功/失败/部分完成分别记录；相同任务重复投递不能重复业务写入。

4. 实现有限重试、retry_wait、lease续期和丢失worker恢复；重试分类由唯一层执行。

5. 为幂等键不同payload返回409；任务读取/取消检查tenant和权限。

6. 模拟relay发布后宕机、worker提交前后宕机、Redis不可用；补足可重放日志。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T07-C01 | 事务提交成功但队列暂时不可用 | outbox保留，恢复后被投递 |
| T07-C02 | 同一消息重复到达 | 只形成一个有效业务结果 |
| T07-C03 | 相同Idempotency-Key不同payload | 409，不覆盖原请求 |
| T07-C04 | worker中断 | 租约过期后恢复且不丢任务 |
| T07-C05 | 永久认证错误 | blocked/failed且不无限重试 |
| T07-C06 | 用户猜测他人job_id | 404且无任务参数泄露 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/integration/test_t07_jobs_and_outbox.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T07.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
