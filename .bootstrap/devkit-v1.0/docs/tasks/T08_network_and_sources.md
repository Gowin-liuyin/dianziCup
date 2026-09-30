
# T08 · 受控抓取网关与来源注册

阶段：G1｜前置：T04、T06、T07｜评分/要求：F1、E1、R1

## 1. 开始前必须读取

`AGENTS.md`、`progress/task_state.json`、`progress/context_handoff.md`以及：

- `docs/plan/04_workflows_and_algorithms.md`
- `docs/plan/05_api_and_tool_contracts.md`
- `docs/plan/07_sources_and_resources.md`

确认前置已有所需实现和实际测试证据；同阶段仅代码验收通过的前置可继续内部开发，live阻塞保持可见。跨阶段必须经阶段检查。不得因为任务编号较大就猜测前置已做。

## 2. 本任务资源

无额外外部资源；按当前环境执行。

未具备资源：先做不依赖它的本任务步骤，验证状态标blocked/not_run；无法继续时写阻塞与最小所需输入，不编造测试通过。

## 3. 修改边界与目标产物

允许修改：`backend/src/ai_intel/ingestion/`；`backend/src/ai_intel/infrastructure/network.py`；`config/sources/`；`backend/tests/security/`；`reports/tasks/`。

另允许本任务指定测试、相关最小迁移、报告与进度文件。任何跨模块公共合同改动先说明；改变语义或栈/阈值要变更审批。不创建与本任务无关的未来模块。

目标产物：`backend/src/ai_intel/ingestion/connectors.py`；`backend/src/ai_intel/infrastructure/network.py`；`config/sources/`；`reports/tasks/T08.md`。

测试/检查位置：`backend/tests/security/test_t08_network_and_sources.py`。这是需要本任务创建并实际执行的位置，不是现有测试证明。

## 4. 按顺序实施

1. 实现SourceConnector协议与Source注册验证，来源类别、权限、解析器版本和能力状态必填。

2. 实现HTTP请求网关：域名/协议白名单、超时、重定向逐跳校验、响应大小、内容类型和限流分类。

3. 处理解析地址与实际连接一致性；不能只做一次DNS检查后允许重绑定到内网，默认不提供自由URL抓取。

4. 移除日志和录制响应中的认证头、cookie与query秘密，保留可审计hash。

5. 为source+stream提供bounded discovery请求上下文，不允许模型扩大授权范围。

6. 完成资源探测模板与源健康接口，真实外网探测必须在授权范围内小批量执行。

## 5. 最低验收案例

每项都要有实际输入与可观察断言；允许参数化，但case ID保留。负例不能只测“没有报错”。不能把被测实现输出再作为期望值。

| ID | 输入/场景 | 必须检查的结果 |
|---|---|---|
| T08-C01 | 允许域名返回正常文档 | 保存内容、时间和来源上下文 |
| T08-C02 | 重定向到本地/私有地址 | 阻断且记录安全原因 |
| T08-C03 | DNS结果在检查与连接间变化 | 连接校验/出口策略阻断 |
| T08-C04 | 超大或错误类型响应 | 中止而非读满内存 |
| T08-C05 | 429与401 | 分类不同，不相同无限重试 |
| T08-C06 | 注册8个同类别别名 | 覆盖统计仍只算实际类别 |

## 6. 执行与回归

主检查：

```text
cd backend && uv run pytest tests/security/test_t08_network_and_sources.py -v
```

命令是待实现的工程合同。若文件/工具不存在，应在本任务或前置中补齐，不得声称运行过。涉及后端的改动另跑Ruff、格式、类型与相关已有回归；前端跑lint/typecheck/build；纯文档任务检查链接、字段和引用，不凑假unit测试。

单元/合同测试可以使用fixture；live、性能、持续运行与人工标注不得以fixture代替。结果记录命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径和输入版本。

## 7. 完成与停止

更新 `reports/tasks/T08.md`、`progress/task_state.json`、交接与阻塞。每个相关评分项只登记本任务确有证据的能力，不能由代码存在推断优秀档已达到。

自检通过进入awaiting_review；没有独立验收不自行写accepted。存在安全、合同或数据问题标needs_changes/blocked。默认本轮到此停止；有界批处理按同阶段顺序继续，遇阶段检查点或风险变更停止。
