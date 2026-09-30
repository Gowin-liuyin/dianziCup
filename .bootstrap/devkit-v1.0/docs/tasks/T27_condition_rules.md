
# T27 · 受限条件AST、规则发布与四态执行

阶段：G3｜前置：T21、T26｜评分/要求：F2、P2、F3、A1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/03_data_contracts.md`
- `docs/plan/04_workflows_and_algorithms.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/assessment/`；`config/rules/`；`backend/tests/unit/`；`contracts/schemas/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/assessment/conditions.py`；`backend/src/ai_intel/assessment/rules.py`；`reports/tasks/T27.md`。

测试/检查位置：`backend/tests/unit/test_t27_condition_rules.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 实现W06叶节点联合类型、all_of/any_of组合和节点/深度上限；拒绝任意表达式、eval和模型生成Python。

2. 按04的两张四态真值表实现纯函数evaluate_condition_tree，保留全部证据与非决定性冲突。

3. 叶节点只读规范资产快照与支持事实，清单缺失不转false。

4. 规则来源、范围、支持片段、schema验证与发布策略版本化；新谓词或争议规则进入待审核。

5. 区分software_applicability、observed_path与research_prerequisites，禁止网络阻断修改软件修复状态。

6. 实现规则验证器与全部边界测试，不用LLM决定逻辑结果。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T27-C01 | true AND unknown | unknown；false AND conflict => false且保留冲突记录 |
| T27-C02 | false OR unknown | unknown；true OR conflict => true且保留冲突记录 |
| T27-C03 | 版本未知与不完整清单 | 不被当排除证据 |
| T27-C04 | AST含eval/任意SQL/空组合/过深 | schema或规则验证拒绝 |
| T27-C05 | 模型提议无证据必要条件 | 不发布确认规则 |
| T27-C06 | 一条路径被阻断或论文前提匹配 | 只给限定范围结果，不宣布绝对安全/成功利用 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/unit/test_t27_condition_rules.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T27.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
