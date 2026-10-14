
# T02 · 项目骨架、依赖锁定与质量命令

阶段：G1｜前置：T01｜评分/要求：E1、D1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/02_architecture.md`
- `docs/plan/08_code_style.md`
- `docs/plan/06_testing_and_evaluation.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/pyproject.toml`；`backend/uv.lock`；`backend/src/ai_intel/`；`backend/tests/unit/`；`frontend/`；`scripts/dev.py`；`infra/`；`README.md`；`.github/workflows/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/uv.lock`；`frontend/package-lock.json`；`scripts/dev.py`；`.github/workflows/ci.yml`；`reports/tasks/T02.md`。

测试/检查位置：`backend/tests/unit/test_t02_project_skeleton.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 只创建API最小入口、前端空工作台和必要包目录，不批量建立几十个空Service类。

2. 验证Python、Node和必要依赖兼容，生成真实uv.lock与package-lock.json，记录版本；不使用latest镜像或手工写锁文件。

3. 配置Ruff、mypy、pytest与TypeScript strict、lint、Vitest；冻结内部覆盖门槛，禁止忽略所有错误。

4. 实现scripts/dev.py的检查入口和参数验证；未建设的scope明确返回非零not_implemented，不能空跑成功。

5. 提供health/live和最小前端加载；health/ready尚未检查依赖时必须说明状态而非固定ready。

6. 配置初始CI执行已存在检查，README区分已可运行命令和待后续任务实现的命令。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T02-C01 | 干净虚拟环境按锁安装 | API可导入、前端可构建、最小测试执行数大于0 |
| T02-C02 | 错误Python/Node版本 | 明确版本不兼容，不绕过锁文件 |
| T02-C03 | 故意加入类型错误 | 类型检查非零退出 |
| T02-C04 | 执行未实现integration scope | nonzero/not_implemented，不能返回PASS |
| T02-C05 | 缺必须配置 | 清楚配置错误，不在导入时联网或泄露秘密 |
| T02-C06 | 前端没有API数据 | 展示未连接状态，不显示假业务统计 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/unit/test_t02_project_skeleton.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T02.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07已独立核验生效）

最终需要：R01:T02。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
