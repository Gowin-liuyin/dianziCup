
# T47 · 强基线、消融和复跑框架

阶段：G5｜前置：T34、T37、T46｜评分/要求：P2、P3、A1、X1、D1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/06_testing_and_evaluation.md`
- `docs/plan/10_provenance_decisions.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

正式比较需要真实模型、已冻结资料和授权成本；外部对照另核验依赖。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`experiments/`；`backend/src/ai_intel/evaluation/`；`scripts/`；`backend/tests/unit/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`experiments/configs/`；`backend/src/ai_intel/evaluation/`；`reports/tasks/T47.md`。

测试/检查位置：`backend/tests/unit/test_t47_baselines_and_ablation.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 实现统一CaseRunner/ResultRecord，记录模型、提示词、数据、权限、预算、缓存、硬件和代码hash。

2. 建立B0强RAG、B1单Agent、B2固定流程、B3缺口调度和B5全量重算配置，不给我方额外真值。

3. 实现条件/证据/冲突/scope watch/调度的独立消融开关，生产不暴露危险安全开关。

4. 为外部NVIDIA/GraphRAG/CTINexus参照建立复现记录与共同任务矩阵；无法部署标未复现，不假冒官方运行。

5. 报告正确率、完成率、未知率、时延、调用量和费用，不能只选择有利指标。

6. 配置和金标冻结后运行配对实验，记录多次随机运行和错误，不事后删例。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T47-C01 | 同case运行B0/B1/B2/B3 | 输入和预算等可比字段一致 |
| T47-C02 | 外部方案不支持某类任务 | N/A而非算错拉低对手 |
| T47-C03 | fixture结果 | 不混入真实效果报告 |
| T47-C04 | 关闭scope watch | 变化测试应能发现漏新增命中的问题 |
| T47-C05 | 省工具但拒答增多 | 完成率/未知率同时体现，不直接写提升 |
| T47-C06 | 缺模型或外部部署失败 | 明确阻塞/未复现，不生成比较数字 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/unit/test_t47_baselines_and_ablation.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T47.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07待核验）

最终需要：R21:T47。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
