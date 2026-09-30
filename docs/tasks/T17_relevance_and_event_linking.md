
# T17 · AI相关性、事件归并与可撤销关联

阶段：G2｜前置：T18、T09｜评分/要求：F1、F2、P2

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/03_data_contracts.md`
- `docs/plan/04_workflows_and_algorithms.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/knowledge/`；`backend/src/ai_intel/enrichment/`；`backend/tests/unit/`；`fixtures/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/knowledge/event_linking.py`；`backend/src/ai_intel/enrichment/relevance.py`；`reports/tasks/T17.md`。

测试/检查位置：`backend/tests/unit/test_t17_relevance_and_event_linking.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 建立产品/生态/风险词表与高召回规则，明确direct、dependency、background、irrelevant、uncertain分类。

2. 模糊材料通过受限模型分类返回证据句；模型不可用则标uncertain而不是全丢弃。

3. 实现内容去重、可靠别名事件归并和相似候选三层处理，保留全部来源版本。

4. 多CVE一文关联多个事件，同产品/CWE不自动合并；转载来源标同源组。

5. 建立合并/拆分记录及撤销接口，修复错误关联时发布影响事件。

6. 用困难负例和同名不同生态案例验证，不只用显而易见样本。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T17-C01 | 明确AI产品安全公告 | direct且证据句存在 |
| T17-C02 | 通用依赖进入已知AI清单 | dependency_relevant，不因无AI词漏掉 |
| T17-C03 | 普通产品发布文章 | irrelevant/background，不当漏洞 |
| T17-C04 | 同CWE不同CVE | 不合并 |
| T17-C05 | 一文同时提到两个CVE | 两事件关联而非并成同一事件 |
| T17-C06 | 错误合并撤销 | 来源与引用可恢复，不删除历史 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/unit/test_t17_relevance_and_event_linking.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T17.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
