
# T36 · 引用依赖、范围关注与负结果依赖

阶段：G4｜前置：T28、T31、T21｜评分/要求：F1、F3、E1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/03_data_contracts.md`
- `docs/plan/04_workflows_and_algorithms.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/revalidation/`；`backend/src/ai_intel/assessment/`；`backend/src/ai_intel/answering/`；`backend/migrations/`；`backend/tests/integration/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/revalidation/dependencies.py`；`backend/src/ai_intel/revalidation/watches.py`；`reports/tasks/T36.md`。

测试/检查位置：`backend/tests/integration/test_t36_dependency_watches.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 建立Dependency和ScopeWatch索引，每次Assessment/Answer记录实际引用及潜在产品/包/事件范围。

2. 对当前无命中的资产、空问答和订阅同样保存scope watch，不能只有已有证据时才建依赖。

3. 建立package/product到当前资产、规则和查询范围的反向索引。

4. 事实、资产、规则、别名和撤回变化生成统一ChangeEvent，包含before/after与scope epoch。

5. 未知范围或索引缺项配置保守扩大策略，不以空依赖集合认定无需更新。

6. 为索引重建和旧数据补建提供幂等迁移任务。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T36-C01 | 已有引用事实修订 | 找到依赖Assessment/Answer |
| T36-C02 | 此前无漏洞的资产新增相关公告 | scope watch匹配到该资产 |
| T36-C03 | 空结果答案后出现新事实 | 空缓存进入失效候选 |
| T36-C04 | 无关产品变化 | 不错认精确依赖，但必要保守回退有记录 |
| T36-C05 | 新别名连接旧产品 | 候选集合重新发现 |
| T36-C06 | 私有scope watch | 不泄露资产给其他租户或公开研究角色 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/integration/test_t36_dependency_watches.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T36.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07已独立核验生效）

最终需要：R16:T36。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
