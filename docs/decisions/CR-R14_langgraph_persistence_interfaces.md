# CR-R14 · 持久协作接口与框架依赖

文档首次创建时间：2026-10-16T12:25:25+08:00
本次写作开始时间：2026-10-16T12:25:25+08:00
状态：approved_for_implementation；独立审查与产品验收待执行。

依据本次完整批次及已批准 CR-R01/CR-R02 的真实九职责、LangGraph 与 PostgreSQL 建设目标，采用 LangGraph 1.2.15 和 langgraph-checkpoint-postgres 3.2.0。官方版本及 wheel 哈希已核对：[LangGraph](https://pypi.org/project/langgraph/)、[PG checkpointer](https://pypi.org/project/langgraph-checkpoint-postgres/)。[官方配置要求](https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/README.md)的 autocommit、dict_row 和 setup 必须落实；setup 仅受控部署/隔离测试命令执行。不得隐式开启远程 tracing、使用不可信 pickle 或类动态导入。

新增依赖仅用于确实要求的持久恢复。锁文件新增2个直接依赖及18个传递包，共20包，原113个包版本保持；133包锁已在仓外独立 runtime frozen sync，exit0，2026-10-16T12:04:54+08:00 至12:05:04+08:00。证据：[dependency_receipt.json](../../reports/runs/recovery_r14_langgraph_dependencies_20261016/dependency_receipt.json)。主 backend 环境未同步、未下载模型；安装成功不是工作流成功。LangSmith 是传递依赖，不授权向其传输数据。

输入为受限 InvestigationRequest：question、event_id、最多8个 evidence refs、可选 asset/snapshot、B2/B2b/B3。预算、身份、thread、角色、权限由服务端决定。enqueue 同 PostgreSQL 事务创建既有 job/payload/outbox 并绑定 owner；不能认领任意已有 job。执行只接受真实 JobExecutionContext/租约。thread ID 由 owner、tenant、job、graph version 确定；不暴露任意 checkpoint 查询或列举。

冻结两应用表，迁移0028唯一由主控写（ActorReference复用既有身份表，不创建空迁移，原0029预留撤销）。investigation_workflows 以 job_id 为PK/FK，保存 owner/tenant、authorized_role、graph_version、input JSON/hash、budget JSON、deadline_at、scope_epochs、可选 asset_snapshot_id 与 created_at；不增第二业务 status。owner/tenant 必须与 job、当前用户一致，输入/config/deadline/owner 不可变。investigation_operations 以 job_id+operation_key 为PK/FK，保存 kind(tool/model/node)、role、受限状态(reserved/succeeded/failed/partial)、request hash、可选 output JSON、input/output bytes、model/tool calls 与创建/完成时刻；计数非负，结果及证据/模型/prompt/工具版本可审计。预留与终态转换受CAS，成功结果不可改写。

工具与模型调用先事务预留，外部IO不持认证/来源锁；返回提交前重验认证、当前角色、权限、epoch、来源与资产。恢复沿原 deadline 和已消费预算，不重置额度。模型结果未知保守记消费且不自动再付费，返回 model_outcome_unknown；不承诺 exactly-once 付费。raw session/API token 不进入 job、checkpoint 或 operations；暂用内部 server actor resolver 端口，主控另冻结 ActorReference。

本包实际主路径为 planner→PG证据工具→真实 QA 模型→critic 支持校验→reporter。B2/B2b/B3共享工具、模型、预算，差异仅调度。其它九职责适配器缺失明确 not_configured，不能以九个节点名称验收全部R14；来源采集写入、富化写入、图写入、研判/导出接线仍须完成。空结果、冲突、未知、高后果缺证据不转为安全或确定事实。

兼容性：不改旧工具合同/角色权限/原预算与评分；新入口新增，既有任务仍权威。迁移：前向0028与受控 checkpointer setup；不用请求启动建表。回滚：撤销新handler/入口，保留PG事实、任务与审计，不自动downgrade。测试影响：严格输入、无配置、owner/tenant、撤销/锁后过期、重放/并发、两进程恢复、epoch/资产变化、预算与未知模型消费、真实模型/PG路径。unit/contract fixture不计live。实现冻结后由新非作者审查，阶段仍partial。

本次写作结束时间：2026-10-16T12:28:28+08:00
最后更新时间：2026-10-16T13:13:42+08:00

修订记录：2026-10-16T13:13:42+08:00，依据独立审查纠正授权条款与依赖分类。旧executor先持job锁，R14不得直接挂其长事务handler；root须用短认领、释放事务、带租约/actor重验的独立执行端口，外部IO不持认证/job锁；接线前置仍未完成。
