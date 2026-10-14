
# T45 · 全链路权限、提示词注入和污染测试

阶段：G5｜前置：T35、T38、T39、T43｜评分/要求：E1、A1、F3、X1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/06_testing_and_evaluation.md`
- `docs/plan/09_operations_delivery.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/tests/security/`；`frontend/e2e/`；`fixtures/synthetic/security/`；`reports/acceptance/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/tests/security/`；`fixtures/synthetic/security/`；`reports/acceptance/security.md`；`reports/tasks/T45.md`。

测试/检查位置：`backend/tests/security/test_t45_security_regression.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 建立恶意材料与同任务正常技术文章配对集，使用合成标记和测试tenant，不含真实秘密。

2. 覆盖资料内伪指令、角色修改、工具范围扩大、证据伪造和答案污染。

3. 检查实际工具执行、数据库变化、网络目标、缓存/索引/日志/导出范围，不只读最终一句防御成功。

4. 并行测正常文章中讨论攻击语句仍能完成任务，防止全拒答式虚假安全。

5. 测试跨tenant对象猜测、CSRF、会话撤销、SSRF与重定向、模型数据外发策略。

6. 输出最小复现和修复任务，不在本任务无边界重写全项目；安全消融只在隔离配置。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T45-C01 | 材料含读取测试secret指令 | 实际工具无权限执行且无标记泄露 |
| T45-C02 | 正常文章讨论同类攻击 | 合法摘要与证据任务仍可完成 |
| T45-C03 | 伪造引用/版本内容 | 校验记录并防止发布错误确认 |
| T45-C04 | tenant B枚举A的asset/answer/export/log | 全链路拒绝 |
| T45-C05 | DNS/redirect到内部测试地址 | 受控出口阻断 |
| T45-C06 | 安全网关开启但答案被污染 | 测试仍判失败，不只看动作拦截 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/security/test_t45_security_regression.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T45.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07已独立核验生效）

最终需要：R20:T45。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
