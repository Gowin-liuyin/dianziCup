
# T15 · 技术标准与政策法规原文接入

阶段：G2｜前置：T09｜评分/要求：F1、F2、F3、R1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/07_sources_and_resources.md`
- `docs/plan/03_data_contracts.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

需要核验真实官方来源，部分公开入口当前未成功读取。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/ingestion/sources/`；`config/sources/`；`backend/tests/contract/`；`fixtures/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`config/sources/standards.yaml`；`config/sources/policies.yaml`；`reports/tasks/T15.md`。

测试/检查位置：`backend/tests/contract/test_t15_standards_policy_connectors.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 确定官方发布机构与可访问栏目，登记标准和政策两类独立来源；候选入口未成功访问不能算接通。

2. 采集文档编号、版本、发布/生效/失效时间、状态、原文链接和适用范围字段。

3. 文档kind区分standard/policy，保留章节与条款定位；不转换成CVE漏洞。

4. 实现替代/修订关系，但不同日期不自动等于生效日期。

5. 无法确认适用范围时保留原文和unknown，不生成法律合规结论或强制义务。

6. 为官方原文、征求意见稿、修订稿、失效文档和未取到全文建立合同测试。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T15-C01 | 标准编号与版本 | 可独立检索且不丢版本 |
| T15-C02 | 发布日期不同于生效日期 | 两字段保持区别 |
| T15-C03 | 征求意见稿 | 状态保留，不当正式生效文件 |
| T15-C04 | 后续修订 | 保存替代关系与历史原文 |
| T15-C05 | 官方栏目访问失败 | blocked_live，不能用模型自写材料凑数 |
| T15-C06 | 范围不明 | 回答仅引用条款与局限，不下法律判断 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/contract/test_t15_standards_policy_connectors.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T15.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07待核验）

最终需要：R06:T15、R09:T15。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
