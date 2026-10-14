
# T11 · OSV字段和版本范围输入

阶段：G2｜前置：T09｜评分/要求：F1、F2、P2

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/03_data_contracts.md`
- `docs/plan/04_workflows_and_algorithms.md`
- `docs/plan/07_sources_and_resources.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/ingestion/sources/osv.py`；`backend/src/ai_intel/enrichment/`；`fixtures/`；`backend/tests/contract/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/ingestion/sources/osv.py`；`reports/tasks/T11.md`。

测试/检查位置：`backend/tests/contract/test_t11_osv_connector.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 依据固定版本OSV schema读取aliases、related、upstream及affected结构，分别保存关系。

2. 保留ecosystem、package、ranges.type、events和explicit versions，不提前把它们都转SemVer。

3. 解析introduced/fixed/last_affected的边界类型，未知scheme保留unsupported标记。

4. 实现按允许产品/包的小范围查询与结果标准化，不发起无界全库下载。

5. 为多个区间、分支、撤回、无CVE和related非alias设计夹具。

6. 完成官方schema验证及记录式合同测试，真实接口探测单独记录。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T11-C01 | aliases与related同时出现 | 前者可作等价候选，后者不合并身份 |
| T11-C02 | introduced/fixed | 保留左右边界语义 |
| T11-C03 | 多区间与明确版本列表 | 不丢分支和排除信息 |
| T11-C04 | GIT范围 | 保留原始关系，不比较hash大小 |
| T11-C05 | 无CVE但有OSV标识 | 事件可入库，不伪造CVE |
| T11-C06 | 未知字段版本或响应失败 | 明确错误且保留原始记录 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/contract/test_t11_osv_connector.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T11.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07已独立核验生效）

最终需要：R06:T11、R11:T11。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
