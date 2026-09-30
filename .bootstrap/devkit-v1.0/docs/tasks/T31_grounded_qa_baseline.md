
# T31 · 有引用问答基线与多轮会话

阶段：G3｜前置：T30、T18、T06｜评分/要求：F3、P3、R1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/03_data_contracts.md`
- `docs/plan/04_workflows_and_algorithms.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/answering/`；`backend/src/ai_intel/api/`；`backend/tests/integration/`；`config/prompts/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/answering/service.py`；`backend/src/ai_intel/answering/router.py`；`reports/tasks/T31.md`。

测试/检查位置：`backend/tests/integration/test_t31_grounded_qa_baseline.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 实现QuestionRequest与会话存取，当前用户每轮重新授权，聊天内容不能当权威知识。

2. 识别基础事实/机制/修复/历史/资产意图；先形成EvidenceBundle再生成AnswerDraft。

3. 通过真实生成接口组织中文回答，要求source_fact和rule_result有支持ID，项目建议分开。

4. 检查引用存在、数字/版本、状态一致和重要未知项，失败最多一次受限重写。

5. 记录首请求到完整完成时间与模型/提示词/数据版本；异步调查尚未完成时不冒充回答完成。

6. 实现无资料/冲突/模型不可用的明确响应，形成可复跑强RAG基线而非假聊天窗口。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T31-C01 | 单文档事实与引用 | 关键结论都可展开来源 |
| T31-C02 | 连续追问同一事件 | 保留会话语境但重新查当前证据 |
| T31-C03 | 资料冲突 | 明示冲突，不在润色中丢失 |
| T31-C04 | 模型编造span ID或修复版本 | 校验拒绝/受限重写 |
| T31-C05 | 资料不足或提供者未配置 | unknown/blocked，不返回硬编码答案伪装成功 |
| T31-C06 | 请求他人conversation/answer | 不可见且缓存不串租户 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/integration/test_t31_grounded_qa_baseline.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T31.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
