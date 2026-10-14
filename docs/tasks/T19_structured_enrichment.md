
# T19 · 结构化富化与维度状态

阶段：G2｜前置：T11、T17｜评分/要求：F2、P2

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/03_data_contracts.md`
- `docs/plan/04_workflows_and_algorithms.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/enrichment/`；`backend/src/ai_intel/knowledge/`；`backend/tests/unit/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/enrichment/dimensions.py`；`backend/src/ai_intel/enrichment/structured.py`；`reports/tasks/T19.md`。

测试/检查位置：`backend/tests/unit/test_t19_structured_enrichment.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 建立按DocumentKind适用的维度矩阵；软件漏洞、论文、标准和政策不共享强制CVE/CVSS字段。

2. 将结构化源字段转换成带EvidenceSpan/JSON路径的Claim，保留来源和评分机构。

3. 每个维度独立available/not_found/not_applicable/conflict/blocked/failed状态。

4. 建立富化作业输入输出和字段级幂等，部分成功可保存，失败不会覆盖先前可信事实。

5. 公开数据与私有资产维度分范围存储，私有富化结果不进入公共事件摘要。

6. 为不同kind、缺字段、多来源分歧和重跑建立测试。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T19-C01 | 结构化版本和CVSS | 原始值与来源路径可追溯 |
| T19-C02 | 无CVE论文 | CVSS可not_applicable，论文机制维度仍待处理 |
| T19-C03 | 资产查询失败但论文成功 | partial并保留论文结果 |
| T19-C04 | 重复富化相同输入 | 不生成重复事实或消息 |
| T19-C05 | 不同评分机构 | 并列记录，不静默取最高分 |
| T19-C06 | 私有资产信息 | 不出现在公共事件返回中 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/unit/test_t19_structured_enrichment.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T19.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07已独立核验生效）

最终需要：R02:T19、R07:T19、R08:T19。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
