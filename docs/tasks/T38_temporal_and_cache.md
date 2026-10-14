
# T38 · 双时间查询与缓存失效

阶段：G4｜前置：T37、T31｜评分/要求：F3、P3、E1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/03_data_contracts.md`
- `docs/plan/04_workflows_and_algorithms.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/answering/`；`backend/src/ai_intel/knowledge/`；`backend/src/ai_intel/retrieval/`；`backend/tests/integration/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/answering/cache.py`；`backend/src/ai_intel/knowledge/temporal.py`；`reports/tasks/T38.md`。

测试/检查位置：`backend/tests/integration/test_t38_temporal_and_cache.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 实现known_at与valid_at区分：历史时点只能看到当时已记录证据；当前回看可显示后来修订。

2. 缓存键包含tenant/user权限版本、会话摘要、问题、知识/资产/规则、模型/提示词与时间范围。

3. 答案保存scope watch和epoch，空结果也失效；返回前再核对权限与关键版本。

4. 索引落后时从权威库核查事实状态，必要结构化查询补查，不能复活撤回证据。

5. 历史答案保留并显示后续修订，不覆盖旧正文伪装当时就知道。

6. 测试权限撤销、会话切换、时间边界和并发请求。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T38-C01 | known_at早于公告修订 | 不能读取未来证据 |
| T38-C02 | 当前回看过去 | 可显示后续修正并说明来源时间 |
| T38-C03 | 两用户同问句不同资产/权限 | 缓存不共享私有结果 |
| T38-C04 | 旧空答案后新增事件 | 缓存失效 |
| T38-C05 | 权限被撤销 | 原缓存不能继续返回私有资料 |
| T38-C06 | 搜索索引含旧文档 | 当前问答过滤stale/withdrawn，不复活结论 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/integration/test_t38_temporal_and_cache.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T38.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07待核验）

最终需要：R16:T38。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
