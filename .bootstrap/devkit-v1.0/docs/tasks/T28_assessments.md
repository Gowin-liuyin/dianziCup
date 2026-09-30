
# T28 · 资产研判、证据包与提交校验

阶段：G3｜前置：T24、T27、T07｜评分/要求：F2、F3、P2、A1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/03_data_contracts.md`
- `docs/plan/04_workflows_and_algorithms.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/assessment/`；`backend/src/ai_intel/api/`；`backend/migrations/`；`backend/tests/integration/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/assessment/service.py`；`backend/src/ai_intel/assessment/router.py`；`reports/tasks/T28.md`。

测试/检查位置：`backend/tests/integration/test_t28_assessments.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 实现assess_asset_snapshot，读published规则与指定快照，保存knowledge/scope版本和input_digest。

2. 调用纯版本/条件引擎，生成四类Assessment状态、缺口、冲突与独立暴露结果。

3. 建立证据包，列出节点结果、原文span、资产字段、规则和输入版本；不靠一段摘要替代。

4. 事务提交时比较输入仍有效，期间更新则保存stale/重新排队，禁止旧任务覆盖current。

5. 为未支持规则、过期观察、模型假设和空知识范围返回明确限制。

6. 实现创建任务、读取结果与证据API，所有对象检查tenant与来源范围。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T28-C01 | 同事件受影响/修复边界/未知版本三资产 | 三种合理且不同结论 |
| T28-C02 | 相同输入快照重复提交 | 幂等、结构化结果一致 |
| T28-C03 | 版本在任务执行中更新 | 旧结果不覆盖新快照 |
| T28-C04 | 网络不可达但软件版本匹配 | 软件适用与路径暴露分栏 |
| T28-C05 | 未经发布规则或model_hypothesis | 不形成确认影响 |
| T28-C06 | 他人assessment/evidence访问 | 404且不泄露资产信息 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/integration/test_t28_assessments.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T28.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
