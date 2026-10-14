
# T39 · 个性化订阅、推荐与修订撤回

阶段：G4｜前置：T38、T28、T31｜评分/要求：F3、P3、E1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/05_api_and_tool_contracts.md`
- `docs/plan/06_testing_and_evaluation.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/recommendations/`；`backend/src/ai_intel/api/`；`backend/migrations/`；`backend/tests/integration/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/recommendations/service.py`；`backend/src/ai_intel/recommendations/router.py`；`reports/tasks/T39.md`。

测试/检查位置：`backend/tests/integration/test_t39_personalized_recommendations.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 实现用户显式产品、资产、风险主题订阅以及启停/编辑/已读状态。

2. 按订阅候选与同一Assessment生成推荐，原因包括命中组件、相关条件、变化和证据。

3. 风险优先级采用明确项目规则，区分已支持风险与优先核实；不把unknown默认低风险。

4. 以subscription+事件+实质版本幂等去重，修订后更新或撤回旧推荐，退订立即生效。

5. 私有推荐、数量、已读和历史都绑定用户/tenant，不按全局热门榜伪装个性化。

6. 为不同用户固定配置建立推荐验收集，报告理由正确性与覆盖，不编造点击率。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T39-C01 | 两用户关注不同产品 | 同一事件库产生有依据的不同推荐 |
| T39-C02 | 同一来源重复轮询 | 不重复提醒同一实质版本 |
| T39-C03 | 公告排除先前影响 | 旧推荐更新/撤回并有原因 |
| T39-C04 | 高后果但关键证据未知 | 推荐优先核实，不称确认受影响 |
| T39-C05 | 用户退订 | 停止新推送，不更改他人订阅 |
| T39-C06 | 读取他人推荐/统计 | 拒绝且不泄露资产兴趣或数量 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/integration/test_t39_personalized_recommendations.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T39.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07待核验）

最终需要：R15:T39、R16:T39。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
