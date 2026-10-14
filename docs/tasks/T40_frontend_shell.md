
# T40 · 前端骨架、认证与统一状态组件

阶段：G3｜前置：T02、T06｜评分/要求：F1、F2、F3、D2、E1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/05_api_and_tool_contracts.md`
- `docs/plan/08_code_style.md`
- `docs/plan/09_operations_delivery.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`frontend/src/`；`frontend/tests/`；`frontend/e2e/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`frontend/src/app/`；`frontend/src/components/`；`reports/tasks/T40.md`。

测试/检查位置：`frontend/tests/t40_frontend_shell.test.tsx`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 建立登录、工作台布局、路由和当前用户上下文，使用后端session/CSRF，不把token持久化到公开脚本。

2. 按features分模块，API客户端从合同生成或严格匹配类型；禁止Any掩盖错误。

3. 实现可复用EvidenceLink、FreshnessBadge、TaskStatus、EmptyState和ErrorPanel，只抽取实际共性。

4. 处理加载、空、失败、无权限、partial、stale和fixture/live标识；无数据不展示随机图表。

5. 保证键盘操作、可读字号、稳定表格和长文本展开，页面文案用清楚中文。

6. 接通真实health/auth接口，测试掉线、退出和刷新后的状态恢复。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T40-C01 | 登录后加载工作台 | 显示真实用户/权限与数据模式 |
| T40-C02 | 未认证访问私有路由 | 转登录且不泄露缓存内容 |
| T40-C03 | API断线 | 清晰错误和重试入口，不显示假成功 |
| T40-C04 | stale/partial/unknown | 视觉与文案区别于正常结果 |
| T40-C05 | 刷新/退出 | 会话正确恢复或清除私有前端缓存 |
| T40-C06 | 键盘访问按钮与表格 | 可操作、状态标签非仅靠颜色 |

## 6. 执行与回归

主检查：

```text
cd frontend && npm run test -- --run tests/t40_frontend_shell.test.tsx
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T40.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07已独立核验生效）

最终需要：R01:T40、R04:T40、R17:T40。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
