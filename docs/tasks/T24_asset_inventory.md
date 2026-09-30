
# T24 · 授权资产、组件和AI配置快照

阶段：G3｜前置：T05、T06、T04｜评分/要求：F2、F3、P2

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/03_data_contracts.md`
- `docs/plan/04_workflows_and_algorithms.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/assets/`；`backend/src/ai_intel/api/`；`backend/migrations/`；`backend/tests/integration/`；`fixtures/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/assets/inventory.py`；`backend/src/ai_intel/assets/router.py`；`reports/tasks/T24.md`。

测试/检查位置：`backend/tests/integration/test_t24_asset_inventory.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 实现JSON/CSV资产导入，显式列映射、大小/行数限制、错误逐行定位；不接受用户任意服务器文件路径。

2. 保存Asset与不可变AssetSnapshot，current指针单独维护，组件有生态/版本/摘要/字段来源。

3. 记录清单完整性与声明范围；未列组件不能默认不存在。

4. 加入工具权限、外部输入渠道、配置和网络暴露字段，缺值保持unknown，不从产品名猜默认配置。

5. 实现当前与历史快照API，租户隔离、幂等导入和变更事件。

6. 选择一种经核验的SBOM输入适配作为扩展，未完成时不宣称支持所有CycloneDX/SPDX版本。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T24-C01 | 合法JSON/CSV | 同一业务数据形成一致规范快照 |
| T24-C02 | 相同快照重复导入 | 幂等且不重复提醒 |
| T24-C03 | 版本改变 | 新快照与旧快照并存，current指向新版本 |
| T24-C04 | 清单缺组件且完整性未知 | 不提供排除证据 |
| T24-C05 | CSV超行数/非法格式 | 拒绝或逐行错误，无部分静默成功 |
| T24-C06 | 跨tenant asset_id或私有文件路径 | 拒绝，不泄露文件 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/integration/test_t24_asset_inventory.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T24.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
