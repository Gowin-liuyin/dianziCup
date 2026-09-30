
# T25 · FOFA被动观察与授权范围

阶段：G3｜前置：T24、T08｜评分/要求：F2、P2、E1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/05_api_and_tool_contracts.md`
- `docs/plan/07_sources_and_resources.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

必须使用用户授权FOFA账户/能力说明与允许范围；本任务默认不含主动扫描。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/assets/`；`backend/src/ai_intel/infrastructure/`；`config/`；`backend/tests/contract/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/assets/fofa.py`；`reports/tasks/T25.md`；`reports/tasks/T25_capabilities.md`。

测试/检查位置：`backend/tests/contract/test_t25_fofa_observations.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 先探测真实账号文档、可返回字段、分页/限流/费用与观察时间；记录未支持能力，不猜参数。

2. 实现结构化查询意图到受限FOFA查询的编译，服务端注入已批准资产范围和字段白名单。

3. 保存retrieved_at与observed_at，缺平台观察时间保持null；产品/版本证据分别保存。

4. 外部记录与内部资产通过显式授权映射关联，IP或域名相同不自动证明所有权。

5. 网关处理预算、日志脱敏、失败/no_result/partial，测试替身只在fixture模式。

6. 提供查询任务与观察展示API；没有真实账号只完成代码合同并列blocked_live。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T25-C01 | 授权范围产品查询 | 返回观察依据与实际可用字段 |
| T25-C02 | 平台仅有产品名无版本 | 版本unknown，不能确认漏洞 |
| T25-C03 | 平台无结果 | no_result，不推断资产不存在 |
| T25-C04 | 观察时间缺失 | 不使用请求时间替代 |
| T25-C05 | 模型注入扩大域名/IP范围 | 网关拒绝 |
| T25-C06 | 缺key/字段不支持/额度耗尽 | 分别not_configured/partial/budget_exhausted |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/contract/test_t25_fofa_observations.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T25.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
