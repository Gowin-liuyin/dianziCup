
# T04 · 领域类型、枚举与JSON Schema

阶段：G1｜前置：T02｜评分/要求：F1、F2、F3、E1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/03_data_contracts.md`
- `docs/plan/04_workflows_and_algorithms.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/domain/`；`backend/tests/unit/`；`contracts/schemas/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/domain/`；`contracts/schemas/`；`reports/tasks/T04.md`。

测试/检查位置：`backend/tests/unit/test_t04_domain_contracts.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 按03建立通用ID、UTC时间、范围、来源、文档、证据、事实、资产、规则、研判和任务DTO；按领域文件组织，不放一个巨大models.py。

2. 严格区分ClaimStatus、ConditionValue、FreshnessStatus和JobStatus；不合并为一个status字符串。

3. 实现字段校验：timezone、正长度、max limits、public/tenant约束、左闭右开证据范围。

4. 生成稳定JSON Schema并保存版本，准备前端类型来源，不手写另一套枚举。

5. 输入错误返回可定位的字段问题；原始外部JSON只留在边界，不把Any贯穿领域。

6. 为每个关键DTO构造正常、缺失、矛盾和额外字段测试。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T04-C01 | UTC与合法范围输入 | roundtrip保持字段语义 |
| T04-C02 | public带私有tenant或tenant缺ID | 拒绝 |
| T04-C03 | unknown与false | 序列化后仍是不同值 |
| T04-C04 | 无时区日期或负时长 | 拒绝而不是猜时区/取绝对值 |
| T04-C05 | 模型响应多出skip_validation | 拒绝多余字段 |
| T04-C06 | schema生成重复执行 | 无无关漂移且版本记录一致 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/unit/test_t04_domain_contracts.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T04.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07已独立核验生效）

最终需要：R00:T04、R02:T04、R18:T04。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
