
# T22 · 论文关联、风险机制与标准政策知识卡

阶段：G2｜前置：T21、T14、T15｜评分/要求：F2、F3、R1、P2

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/03_data_contracts.md`
- `docs/plan/04_workflows_and_algorithms.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/enrichment/`；`backend/tests/contract/`；`config/prompts/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/enrichment/research_links.py`；`backend/src/ai_intel/enrichment/knowledge_cards.py`；`reports/tasks/T22.md`。

测试/检查位置：`backend/tests/contract/test_t22_research_and_document_links.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 实现事件到论文/分析候选检索，用标识、产品和机制生成受控查询，不仅按标题相似度连边。

2. 明确关系类型：首次提出、分析事件、验证同类机制、提供防御、背景相关；每条强关系要有支持段落。

3. 论文卡抽取攻击者控制能力、输入路径、模型/任务、权限、作者验证环境、结论和限制。

4. 标准/政策卡抽取机构、编号、版本、状态、时间、适用范围与条款；原文和摘要分开。

5. 区分作者报告、团队复现、对当前资产的规则推断；未复现不写系统验证通过。

6. 将无支持的关系保留为candidate/background，不进入确认资产规则。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T22-C01 | 论文明确分析某事件 | 关联类型和证据对应 |
| T22-C02 | 只共享提示词注入主题 | 最多背景关联，不写验证同一漏洞 |
| T22-C03 | 论文需要写工具权限 | 前提字段保留，不推广至只读环境 |
| T22-C04 | 论文没有CVE/CVSS/POC | 正确not_applicable或not_found |
| T22-C05 | 政策草案与正式文件 | 状态、时间不同，不能替换 |
| T22-C06 | 无法确认条款适用范围 | 给原文和局限，不生成合规裁决 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/contract/test_t22_research_and_document_links.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T22.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07已独立核验生效）

最终需要：R07:T22、R09:T22、R10:T22。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
