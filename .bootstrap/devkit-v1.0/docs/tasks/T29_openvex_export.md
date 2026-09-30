
# T29 · 受限OpenVEX与证据报告导出

阶段：G3｜前置：T28｜评分/要求：F2、E1、D1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/04_workflows_and_algorithms.md`
- `docs/plan/05_api_and_tool_contracts.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/assessment/exports.py`；`backend/src/ai_intel/api/`；`backend/tests/contract/`；`config/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/assessment/exports.py`；`contracts/schemas/openvex/`；`reports/tasks/T29.md`。

测试/检查位置：`backend/tests/contract/test_t29_openvex_export.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 读取并固定OpenVEX规范/schema版本，保存本地schema或校验依赖及来源。

2. 为内部状态建立显式映射表；unknown/conflict/stale优先under_investigation，not_affected需足够范围依据。

3. fixed必须有当前版本和修复证据；阻断一条已知路径不足以宣称整体不受影响。

4. 对无法安全映射的非CVE风险输出内部证据报告而非伪造VEX。

5. 导出含作者配置、生成时间、产品身份、漏洞身份、理由/措施与证据版本。

6. 逐条检查tenant、信息公开范围和schema，任何记录不合规则返回具体失败而非静默忽略。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T29-C01 | 有明确修复与版本证据 | fixed导出符合选定schema |
| T29-C02 | unknown/conflict/stale | 不导出确定not_affected |
| T29-C03 | 仅一条路径被阻断 | 限定报告，不冒充整体排除 |
| T29-C04 | 缺required justification/action字段 | 校验拒绝 |
| T29-C05 | 非CVE风险无可靠映射 | 内部报告且标格式限制 |
| T29-C06 | 混入他人assessment_id | 整体授权拒绝，无私有数据泄漏 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/contract/test_t29_openvex_export.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T29.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
