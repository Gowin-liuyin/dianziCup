
# T10 · CVE与NVD结构化连接器

阶段：G2｜前置：T09｜评分/要求：F1、F2、P1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/07_sources_and_resources.md`
- `docs/plan/03_data_contracts.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

公开接口访问；部分源可能需要用户授权key，缺失时live阻塞。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/ingestion/sources/`；`config/sources/`；`fixtures/recorded/`；`backend/tests/contract/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/ingestion/sources/cve.py`；`backend/src/ai_intel/ingestion/sources/nvd.py`；`reports/tasks/T10.md`。

测试/检查位置：`backend/tests/contract/test_t10_cve_nvd_connectors.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 从官方文档和小响应核验CVE/NVD字段、更新时间和分页，不根据旧记忆编造接口参数。

2. 各自实现discover/fetch/normalize，保留CVE标识、状态、发布日期、修改时间、描述、评分与引用。

3. 处理CVE拒绝/撤回状态和多来源评分，不能只保留最高分。

4. 对分页、空页、缺字段和429建立脱敏fixture；版本变化通过source schema版本记录。

5. 做有界live探测并保存能力报告；NVD正文或权限不可得则单独blocked，CVE可用部分继续。

6. 不把两个结构化源计作两种来源类别，也不根据CVE参考链接自动合并所有事件。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T10-C01 | 合法CVE记录 | 标识、日期和引用无损标准化 |
| T10-C02 | 同CVE更新描述 | 生成修订而非新漏洞 |
| T10-C03 | 分页末页/空窗口 | 正确完成，不漏页或循环 |
| T10-C04 | 缺CVSS或版本字段 | 明确missing，不编造 |
| T10-C05 | rejected记录 | 状态正确而非当普通活动漏洞 |
| T10-C06 | API字段不兼容/429 | contract失败或有限重试，不能返回假成功 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/contract/test_t10_cve_nvd_connectors.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T10.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。

## 恢复合并验收附录（R00 / CR-R07待核验）

最终需要：R04:T10。原C01–C06、实施范围、引用合同和原前置保留。恢复执行前置按manifest.recovery.work_packages.requires_slices；最终前置仍为原depends_on。单R完成不得自动验收整卡；独立review须核对当前冻结版本/真实证据。记录时间：2026-10-14T21:05:58+08:00。
