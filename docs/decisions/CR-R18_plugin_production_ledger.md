# CR-R18 · 插件真实端口与同事务账本

首次创建时间：2026-10-17T10:09:51+08:00
状态：已有三类插件批准建设目标内实施；准确落实 awaiting 独立 review

复用既有 PG investigation run、操作账本和 frozen PluginBroker；仅 actual running owned run、可信 JobExecutionContext 与服务端固定 AgentRole 可构建生产 factory。source/enrichment 复用既有 durable enqueue，accepted 不等于 completed。tool 复用真实工具业务与有效性 fences；不会新增任意 SQL/URL/shell，容器无密钥。

指定 ports 作者唯一抽出 tool_gateway.py PostgresEvidenceReader._read_evidence_in_session，原 standalone wrapper 委托，原业务顺序/graph/auth/current fences 保持。生产只换 caller Session 认证事务包装，不复制证据判断、不开第二事务。新增 ProductionPluginBroker 必要内部 dispatch seam 与实际 PG quota/ToolRun 端口；现 quota 缺失仍 fail closed。

invocation 用 original context key 唯一绑定 actor/run/operation/payload；相同重放复用，异 payload 冲突。tool operation.output_json 保持直接 ToolResult，source/enrich node 保持实际 accepted receipt。固定 operation_key 前缀 plugin:{live|fixture}:{tool|source|enrichment}: 与 UUID5 后缀仅用于识别真实 broker envelope；现 workflow_service.operation_output_bytes 由指定唯一作者追加此识别，按照实际 operation/result/data_mode/is_synthetic/cost unknown 序列化记总 bytes，quota settle 重构相同 envelope 验 result_bytes。不 padding、不换计分分母、不抬 MAX_WORKFLOW_OPERATIONS 或 WorkflowBudget；额度受控且同事务 rollback。

兼容/迁移：现 ToolResult/operation 输出结构与非 plugin accounting 不变，无新表/迁移/依赖；须核 actual operation-key 和 replay validators，若不兼容回报告具体条款，不绕过。Root 最终 App/worker 装配，当前端口未接线不得伪在线。回滚恢复两 seam/生产 factory 代码，保留 PG 历史，不 downgrade/删除。

测试影响 R18/R14/T35/T44：actor/owner、lease/attempt/deadline 最终 DBclock、事务/重放/并发、真实 encoded output计量、异 payload、来源/富化接受状态、工具当前证据/auth/epoch、bounded Docker 无网络及退出恢复。offline/PG/Docker/live 分别记录，不以 Dockerfile 或 Protocol 代替运行证据。原最终范围/评分/人工Gold不变。

修订记录：2026-10-17T10:09:51+08:00 Root登记必要账本兼容与共享函数所有权；新非作者审查后生效。
