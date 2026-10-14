
# T30 · 授权过滤的BM25、向量检索与重排

阶段：G3｜前置：T21、T18、T06｜评分/要求：F3、P3

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/04_workflows_and_algorithms.md`
- `docs/plan/05_api_and_tool_contracts.md`
- `docs/plan/06_testing_and_evaluation.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

需要真实OpenSearch；语义效果另需真实embedding和rerank资源。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/retrieval/`；`backend/tests/integration/`；`config/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/retrieval/service.py`；`backend/src/ai_intel/retrieval/indexing.py`；`reports/tasks/T30.md`。

测试/检查位置：`backend/tests/integration/test_t30_hybrid_retrieval.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 创建OpenSearch映射，固定embedding维度/model版本，文本块ID与永久EvidenceSpan分开。

2. 实现outbox驱动索引和版本化重建，记录索引水位；模型变化新建索引，不混合向量空间。

3. 实现精确标识优先、BM25和向量双分支；两分支查询均预过滤tenant/可见时间。

4. 首版固定应用层RRF(k=60开发初值)合并，再调用reranker；采用原生hybrid时用ADR替换而非双默认。

5. 返回前回查PostgreSQL事实状态、权限和scope epoch，索引滞后明确partial并对结构化问题补查。

6. 记录召回候选、重排和完整耗时；没有真实embedding不能把哈希向量计作语义检索。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T30-C01 | 精确CVE查询 | 优先命中对应事件不被相似文本挤走 |
| T30-C02 | 中英文同义问题 | 用实际embedding测试召回，fixture只测合同 |
| T30-C03 | 两tenant同关键词 | 每个检索分支都不返回越权候选 |
| T30-C04 | 已撤回事实仍在索引 | 返回前被过滤或标历史 |
| T30-C05 | 向量维度/模型版本改变 | 拒绝混写并要求重建 |
| T30-C06 | 新事实尚未索引 | 水位/partial可见，不声称全库无结果 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/integration/test_t30_hybrid_retrieval.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T30.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07已独立核验生效）

最终需要：R05:T30、R12:T30。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
