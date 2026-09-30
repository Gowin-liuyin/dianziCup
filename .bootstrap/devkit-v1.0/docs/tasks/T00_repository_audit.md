
# T00 · 仓库、资源与授权审计

阶段：G0｜前置：无｜评分/要求：E1、D1、X1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/02_architecture.md`
- `docs/plan/10_provenance_decisions.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`progress/`；`docs/decisions/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`reports/tasks/T00.md`；`progress/context_handoff.md`；`progress/blockers.md`；`docs/decisions/repository_mapping.md`。

测试/检查位置：`reports/acceptance/t00_checklist.md`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 确认工作目录和是否已有Git仓库；读取已有AGENTS、README、依赖、目录与测试，不改源码。

2. 运行只读环境检查：系统、Python/Node、容器可用性、Git状态；只记录secret变量是否存在，不读取或输出其值。

3. 整理现有实现与本方案目录对应表；有未提交修改逐文件记录，不覆盖、不重置。

4. 列出模型、embedding、rerank、FOFA、数据源、资产、部署和人工标注资源状态及缺口。

5. 形成默认技术栈与已有技术栈的差异；有冲突提出ADR，不进行未经批准迁移。

6. 建立progress/context_handoff.md和T00报告，提出本次会话后可执行的第一张任务卡；本任务结束即停止。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T00-C01 | 已存在仓库与未提交文件 | 报告准确保留其路径和状态，没有修改源码 |
| T00-C02 | 空目录 | 标为greenfield，给出默认落地目录而不伪称有代码 |
| T00-C03 | 已有测试命令 | 只在允许且环境具备时试运行，记录原始退出码 |
| T00-C04 | 没有模型或FOFA凭据 | 列为blocked_live，不索取明文密钥到报告 |
| T00-C05 | 旧AGENTS与本包冲突 | 提交具体冲突与映射，不覆盖 |
| T00-C06 | 无容器权限或网络授权 | 标受影响任务与可以继续的本地任务 |

## 6. 执行与回归

主检查：

```text
按下表逐条核验实际文件、日志或人工记录；不创建空测试冒充通过。T01建立校验脚本后补跑 python scripts/verify_plan.py。
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T00.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
