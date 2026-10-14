
# T01 · 评分追踪、任务状态与首批验收样例

阶段：G0｜前置：T00｜评分/要求：F1、F2、F3、P1、P2、P3、A1、E1、D1、D2、X1、R1、R2

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/01_scope_and_scoring.md`
- `docs/plan/06_testing_and_evaluation.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`contracts/`；`progress/`；`fixtures/synthetic/`；`benchmarks/dev/`；`scripts/verify_plan.py`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`contracts/requirements.json`；`contracts/task_manifest.json`；`fixtures/synthetic/pilot_cases.json`；`scripts/verify_plan.py`；`reports/tasks/T01.md`。

测试/检查位置：`reports/acceptance/t01_checklist.md`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 按官方PDF逐项核对contracts/requirements.json，验证初赛与决赛各合计100，不把内部目标写成官方门槛。

2. 给每条评分要求关联至少一个实现任务、一个验收任务和一个证明材料；额外论文/标准/政策与提交格式独立登记。

3. 创建20个左右的合成开发案例提案：修订、不同版本、未知、冲突、空结果、跨租户；全部is_synthetic=true，不虚构真实CVE。

4. 建立样例输入/预期输出结构和标注说明；真值依人工规则给出，不用未来产品代码生成自己的期望。

5. 实现scripts/verify_plan.py，只校验本项目文档/任务JSON、依赖、状态和评分引用，不把校验通过当产品测试通过。

6. 初始化状态机和报告目录约定；人工确认尚无真实运行或盲测结果。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T01-C01 | 完整评分表 | 初赛100、决赛100，11个决赛评分项全部映射 |
| T01-C02 | 一条评分项没有任务 | 校验失败并指出编号 |
| T01-C03 | 任务依赖不存在或循环 | 校验失败而不是跳过 |
| T01-C04 | 合成案例 | 标记、来源和预期字段完整且与真实事件分开 |
| T01-C05 | 有测试目标却没有结果 | 状态为not_run而非passed |
| T01-C06 | 改变官方门槛或删除困难案例 | 需要变更单且不能静默进入正式合同 |

## 6. 执行与回归

主检查：

```text
按下表逐条核验实际文件、日志或人工记录；不创建空测试冒充通过。T01建立校验脚本后补跑 python scripts/verify_plan.py。
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T01.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07已独立核验生效）

最终需要：R00:T01、R19:T01。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
