
# T12 · 厂商公告与技术博客自动接入

阶段：G2｜前置：T09｜评分/要求：F1、F2、P1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/07_sources_and_resources.md`
- `docs/plan/04_workflows_and_algorithms.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

需要确认可合法访问的厂商和博客源。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/ingestion/sources/`；`config/sources/`；`fixtures/`；`backend/tests/contract/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`config/sources/vendor.yaml`；`config/sources/blog.yaml`；`reports/tasks/T12.md`。

测试/检查位置：`backend/tests/contract/test_t12_vendor_blog_connectors.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 从已选产品中确定一个官方公告源和一个原创技术博客源，登记身份、许可和类别。

2. 共享RSS/Atom或公开索引发现代码，但每个源保留独立正文解析与修订识别规则。

3. 实现canonical URI与源record ID归一，不能删除会改变内容的query参数。

4. 保留发布日期与修改时间，无法取得修改时间则用内容比较并记录覆盖限制。

5. 对原文引用和产品标识保留证据，不把博客评论作为公告正文。

6. 各做一次真实增量周期；没有真实源时只算适配器合同完成。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T12-C01 | RSS新条目与正文 | 自动形成版本与来源证据 |
| T12-C02 | 同文章两个跟踪链接 | 归为同文档但不误删关键参数 |
| T12-C03 | 正文只有导航变化 | material_change=false |
| T12-C04 | 官方公告与转载 | 来源身份不混淆 |
| T12-C05 | 文章缺时间或付费不可读 | 明确缺失/blocked，不猜正文 |
| T12-C06 | 源结构改变 | 解析失败进入复核而非存空白成功 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/contract/test_t12_vendor_blog_connectors.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T12.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
