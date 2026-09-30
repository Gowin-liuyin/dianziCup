
# T18 · 真实模型、向量与重排接口及测试替身

阶段：G2｜前置：T04、T08｜评分/要求：F2、F3、A1、E1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/02_architecture.md`
- `docs/plan/05_api_and_tool_contracts.md`
- `docs/plan/07_sources_and_resources.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

真实生成、embedding与rerank资源需用户授权；缺失不阻碍fixture合同测试，但影响live验收。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/infrastructure/models/`；`config/models/`；`backend/tests/contract/`；`fixtures/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/infrastructure/models/`；`config/models/providers.yaml`；`reports/tasks/T18.md`。

测试/检查位置：`backend/tests/contract/test_t18_model_clients.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 实现generate_structured、embed_texts、rerank_passages协议，服务端配置提供者，不把SDK对象泄漏到领域层。

2. 按授权提供者实际文档写一个真实生成实现和实际embedding/rerank实现；未配置的能力保持not_configured。

3. 实现仅测试用fixture provider并强制DATA_MODE隔离；禁止production使用固定答案或哈希向量。

4. 校验JSON输出、embedding维度、批次顺序、timeout、token预算和数据外发策略。

5. 模型拒绝、超时、429、格式错误、费用未知分别记录，最多一次受限格式修复。

6. 做最小live探测并固定模型/提示词版本，未经费用授权不批量调用或下载大模型。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T18-C01 | 合法结构化输出 | 通过schema且保留用量与版本 |
| T18-C02 | 多余字段/错误JSON | 格式错误或一次修复后失败，不悄悄降级成功 |
| T18-C03 | 向量维度或条目数量错 | 拒绝入索引 |
| T18-C04 | fixture provider在production | 启动/调用拒绝 |
| T18-C05 | 私有资产未经外发许可 | 网关阻断，不把原文送外部模型 |
| T18-C06 | 无key或无预算 | not_configured/blocked_live，不伪称模型可用 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/contract/test_t18_model_clients.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T18.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
