
# T05 · 数据库迁移、原文存储和不可变版本

阶段：G1｜前置：T03、T04｜评分/要求：F1、F2、E1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/03_data_contracts.md`
- `docs/plan/04_workflows_and_algorithms.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/migrations/`；`backend/src/ai_intel/infrastructure/`；`backend/src/ai_intel/knowledge/`；`backend/tests/integration/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/migrations/`；`backend/src/ai_intel/knowledge/revisions.py`；`reports/tasks/T05.md`。

测试/检查位置：`backend/tests/integration/test_t05_persistence_and_raw_store.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 依据03建立核心表、外键、唯一键和索引；先满足当前数据链，后续表由对应任务按迁移补充。

2. 实现数据库Session/事务边界与内容存储：临时文件写入后原子替换、hash校验、路径不取自用户输入。

3. 实现save_document_revision，重复末版复用，A→B→A保留第三次修订；保存FetchAttempt而不误计新事件。

4. 实现revision与TextBlock/EvidenceSpan对应关系及租户范围校验。

5. 加入knowledge/scope epoch基础表，保证以后改变事实可使旧读缓存过期；记录迁移版本。

6. 验证空库升级、已有数据升级、回滚失败处理和原文重读；不在生产自动drop/create。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T05-C01 | 相同末版重复导入 | 不新增revision、不重复业务事件 |
| T05-C02 | 内容A→B→A | 有3个按时间排列修订，第一与第三可同hash |
| T05-C03 | 写原文后数据库失败 | 可清理未引用对象，不产生指向缺失原文的有效记录 |
| T05-C04 | 恶意文件路径 | 只能使用内容hash生成对象路径 |
| T05-C05 | 跨tenant证据引用 | 拒绝持久化 |
| T05-C06 | 旧库升级 | 已有事实、时间和unknown状态保留 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/integration/test_t05_persistence_and_raw_store.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T05.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07已独立核验生效）

最终需要：R02:T05。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
