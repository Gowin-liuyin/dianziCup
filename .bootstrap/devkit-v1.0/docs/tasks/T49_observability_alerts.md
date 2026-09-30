
# T49 · 结构化监控、指标和告警

阶段：G4｜前置：T07、T16、T35｜评分/要求：E1、P1、D2

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/09_operations_delivery.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/infrastructure/observability.py`；`infra/monitoring/`；`backend/tests/integration/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`infra/monitoring/`；`backend/src/ai_intel/infrastructure/observability.py`；`reports/tasks/T49.md`。

测试/检查位置：`backend/tests/integration/test_t49_observability_alerts.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 统一结构化日志、trace_id、job_id与工具/来源事件；秘密和私有正文不进入日志。

2. 采集source freshness、失败率、queue backlog、worker心跳、索引滞后、stale数量、模型/工具用量和问答延迟。

3. 提供受限operations/status与监控端点，配置Prometheus/Grafana及一个可用告警通道。

4. 初始阈值依据开发负载配置并标内部选择，不写成官方或理论阈值。

5. 模拟来源连续失败、队列积压和费用接近上限，验证实际告警与恢复解除。

6. 记录指标缺失与采集器故障，不用默认0表示系统健康。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T49-C01 | 请求/worker/工具链 | trace可串联且无秘密 |
| T49-C02 | 源持续失败 | 有真实告警和影响来源标识 |
| T49-C03 | 队列恢复正常 | 告警解除且保留历史 |
| T49-C04 | 指标采集失联 | unknown/unavailable，不显示健康0 |
| T49-C05 | 非管理员请求运维数据 | 权限拒绝 |
| T49-C06 | 费用提供者未返回 | 标unknown，不显示零费用 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/integration/test_t49_observability_alerts.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T49.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
