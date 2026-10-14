
# T51 · 完整CI/CD与受控发布流程

阶段：G5｜前置：T45、T48、T50｜评分/要求：E1、D1、X1、R2

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/09_operations_delivery.md`
- `docs/plan/06_testing_and_evaluation.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

CI平台和生产部署需要用户授权；可先验证本地等价流水线并披露范围。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`infra/`；`scripts/`；`docs/runbooks/`；`.github/workflows/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`.github/workflows/`；`infra/compose/`；`docs/runbooks/release.md`；`reports/tasks/T51.md`。

测试/检查位置：`backend/tests/integration/test_t51_ci_cd_release_pipeline.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 扩展CI覆盖实际unit/contract/integration/security/frontend/e2e，检查测试数与skip，不用||true。

2. 固定依赖和镜像，构建非root制品，执行秘密/依赖审计并记录有限白名单。

3. 生成制品manifest、schema/prompt/model配置hash和迁移版本，禁止打包holdout答案或真实秘密。

4. 建立staging部署→smoke→人工审批→正式发布流程，未授权不得push/public deploy。

5. 实现失败停止和应用回滚手册；数据库破坏性回滚必须人工决定。

6. 用干净环境验证pipeline，记录不可用的外部CI平台而不声称已云端运行。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T51-C01 | 新增失败测试 | pipeline失败而不是忽略 |
| T51-C02 | 全部skip或0测试 | 对必需检查不算通过 |
| T51-C03 | 镜像中扫描到secret/holdout答案 | 阻止发布 |
| T51-C04 | staging smoke失败 | 不进入正式部署 |
| T51-C05 | 未人工批准生产 | 无生产写操作 |
| T51-C06 | 锁文件安装和制品重建 | 版本可追溯，外部依赖漂移被发现 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/integration/test_t51_ci_cd_release_pipeline.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T51.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07待核验）

最终需要：R18:T51、R20:T51。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
