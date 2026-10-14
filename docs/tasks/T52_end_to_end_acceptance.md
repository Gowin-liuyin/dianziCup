
# T52 · 三模块全链路与全部功能验收

阶段：G5｜前置：T41、T42、T43、T44、T51｜评分/要求：F1、F2、F3、A1、E1、R1、D2

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/01_scope_and_scoring.md`
- `docs/plan/06_testing_and_evaluation.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

需要真实来源与模型等资源才可完成live部分；离线通过不是完整功能优秀档证明。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`frontend/e2e/`；`backend/tests/integration/`；`scripts/acceptance/`；`reports/acceptance/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`frontend/e2e/`；`reports/acceptance/functional.md`；`reports/tasks/T52.md`。

测试/检查位置：`frontend/e2e/t52_end_to_end_acceptance.spec.ts`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 用固定dev案例运行采集→归并→全部适用富化→资产判定→检索问答→推荐完整链路。

2. 核查8类来源真实能力、论文/标准/政策、POC/CVSS/影响/资产等维度，不因主线创新而略过。

3. 覆盖多轮、多跳、影响范围、修复建议、攻击链与个性化；检查每个问题的证据路径。

4. 加入修订后重验证、Agent工具选择和失败恢复，UI/API/数据库结果一致。

5. 分别输出fixture E2E和live E2E报告；无凭据/全文/权限的项保持缺口，不能全打勾。

6. 把每个F1/F2/F3/A1/E1要求绑定实际截图、run_id和测试日志。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T52-C01 | 新事件完整链路 | 各阶段有真实产物与状态，不仅页面模拟 |
| T52-C02 | 8类配置但其中2类未live | 覆盖报告显示未接通而非8/8 |
| T52-C03 | 某富化维度失败 | partial并在验收列缺口 |
| T52-C04 | 问答关键证据移除 | 不输出原确定结论 |
| T52-C05 | 两个用户不同订阅 | 推荐实际不同且不串数据 |
| T52-C06 | fixture与live混用 | 验收拒绝混为真实功能完成 |

## 6. 执行与回归

主检查：

```text
cd frontend && npx playwright test e2e/t52_end_to_end_acceptance.spec.ts
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T52.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07待核验）

最终需要：R22:T52。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
