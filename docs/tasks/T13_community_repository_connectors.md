
# T13 · 安全社区与代码仓库记录接入

阶段：G2｜前置：T09｜评分/要求：F1、F2、P1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/07_sources_and_resources.md`
- `docs/plan/04_workflows_and_algorithms.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/ingestion/sources/`；`config/sources/`；`fixtures/`；`backend/tests/contract/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`config/sources/community.yaml`；`config/sources/repository.yaml`；`reports/tasks/T13.md`。

测试/检查位置：`backend/tests/contract/test_t13_community_repository_connectors.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 核验一个可用安全社区/协调披露来源及所选产品仓库API，来源类别分别登记。

2. 实现社区列表增量与正文提取；仓库记录保留release、commit、security advisory类型和固定标识。

3. 安全公告、发布说明与修复提交分别建立关联，不把release出现安全关键词当已确认漏洞。

4. 记录commit SHA与源时间；默认不执行代码、不克隆任意大仓库。

5. 处理分页、权限不足、删除或转私有记录和API限流，原有历史证据仍保留。

6. 保存脱敏探测记录，明示真实接通与仅fixture状态。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T13-C01 | 同产品release与修复commit | 两类记录可关联但不合并成同文档 |
| T13-C02 | 社区文章涉及多个漏洞 | 各自关联，不并成一个漏洞 |
| T13-C03 | 固定commit引用 | 可追溯版本，不只保存浮动main |
| T13-C04 | 仓库转私有/404 | 获取失败，历史证据不自动撤回 |
| T13-C05 | 接口无权限 | blocked_live，不退化成伪响应 |
| T13-C06 | POC链接进入材料 | 只保存元数据，不自动执行 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/contract/test_t13_community_repository_connectors.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T13.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07待核验）

最终需要：R06:T13、R07:T13。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
