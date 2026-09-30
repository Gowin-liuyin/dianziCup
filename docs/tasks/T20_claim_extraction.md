
# T20 · 少样本抽取、来源片段与字段校验

阶段：G2｜前置：T18、T19、T09｜评分/要求：F2、P2、F3

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/03_data_contracts.md`
- `docs/plan/04_workflows_and_algorithms.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/enrichment/`；`backend/tests/contract/`；`config/prompts/`；`benchmarks/dev/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/enrichment/extraction.py`；`config/prompts/extraction/`；`reports/tasks/T20.md`。

测试/检查位置：`backend/tests/contract/test_t20_claim_extraction.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 按材料类型实现ExtractionBatch schema与运行时提示词，示例只取dev事件。

2. 先提取单组相关字段，再定位quote；不要一个提示词同时猜评分、条件和修复。

3. 实现标识、数字、版本、否定/限定、片段定位和字段类型检查，失败字段退为unverified。

4. 重复句要求block定位；引用存在与语义支持分别记录，不把前者当后者。

5. 保留模型假设为model_hypothesis，不进入确认规则；重要疑难条件进入复核队列。

6. 输出字段级错误统计与样本，禁止为提高指标只保留容易事件。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T20-C01 | 明确版本与修复段落 | 提取值、条件和原文片段一致 |
| T20-C02 | 只有在配置开启时受影响 | 必要限定条件保留 |
| T20-C03 | 来源否定某版本受影响 | 不抽成正向影响 |
| T20-C04 | quote不在原文或多次出现未定位 | 校验失败而非虚构偏移 |
| T20-C05 | 测试集事件进入few-shot候选 | 拒绝并报告泄漏 |
| T20-C06 | 模型附加无证据CVE/CVSS | 候选拒绝，不发布事实 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/contract/test_t20_claim_extraction.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T20.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
