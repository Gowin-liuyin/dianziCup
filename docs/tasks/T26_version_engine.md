
# T26 · 生态化版本比较与区间包含

阶段：G3｜前置：T04、T11｜评分/要求：F2、P2、F3

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/03_data_contracts.md`
- `docs/plan/04_workflows_and_algorithms.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/assessment/versions.py`；`backend/tests/unit/`；`fixtures/synthetic/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/assessment/versions.py`；`fixtures/synthetic/version_cases.json`；`reports/tasks/T26.md`。

测试/检查位置：`backend/tests/unit/test_t26_version_engine.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 使用成熟PEP440和SemVer解析库，封装compare_versions/contains_version；不自己用字符串或浮点比较。

2. 实现OSV输入到内部区间转换，introduced左闭、fixed右开、last_affected右闭、explicit列表独立。

3. 支持多区间和多个维护分支；排除项有明确语义，无法解释的范围返回unknown/unsupported。

4. 身份/生态不符先拒绝匹配；git提交没有祖先关系工具则不支持，不能按hash大小。

5. 对下游回补记录需要权威修复证据，不从上游版本猜已修复。

6. 用表驱动边界与性质测试验证比较一致性，测试期望由独立规范确定。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T26-C01 | 1.4.1位于[1.0.0,1.4.2) | true |
| T26-C02 | 1.4.2恰为fixed | false，不包含边界 |
| T26-C03 | 1.10.0与1.9.0 | 按生态排序，不字典序 |
| T26-C04 | 预发布/多个分支/不连续范围 | 按各scheme与范围独立判断 |
| T26-C05 | 未知版本、非法字符串、GIT无关系 | unknown/unsupported，不肯定排除 |
| T26-C06 | 同名不同生态或回补未知 | 不错误认定受影响/修复 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/unit/test_t26_version_engine.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T26.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
