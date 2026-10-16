# CR-R18 · 同一 PG 事务内的调查入队端口

文档首次创建时间：2026-10-17T05:57:40.006+08:00
状态：approved_for_implementation；新作者实现后必须由新非作者审查，不代表R18或G-E已验收。

现 InvestigationWorkflowService.enqueue 自开engine连接和事务，公开API无法把凭据、幂等、新请求quota、真实job/payload/outbox、owner与typed binding整体提交或回滚。只读分析 reports/tasks/R18-typed-task-bridge-analysis.md 的调用方持有事务方案复用现判断最多；不新建第二套任务状态，也不把WorkflowResult强转QAAnswer。

唯一指定作者只可在 investigation/workflow_service.py 抽出 enqueue_in_session(session, request, budget, *, actor: ActorReference, idempotency_key) -> InvestigationEnqueueReceipt(job_id:UUID, created:bool)。session必须来自同engine且已有caller-owned事务；port不commit/rollback/close、不另开连接。现enqueue签名和UUID返回保持，由旧wrapper创建新鲜actor reference并委托同port。port自身仍锁认证、核tenant/owner和graph/source/asset currentproof，保留原输入预算、payload绑定、outbox、幂等冲突与约束检查；不信任body identity。不允许其他workflow判断/worker/finish/source报告/原测试断言变化。

公开quota和typed绑定由Root同事务完成，created false不得重复扣ask额度；新port不是网络或付费调用入口，也不保存原始API key/cookie。新结果型仅内部，不改公共schemas。暂不新增迁移；public_task_bindings如确需0031由Root唯一后续设计并登记，不由作者创建空表。

验收含旧wrapper结果、caller rollback整体撤销、replay/不同payload冲突、错误engine/no transaction、actor过期/撤销/两租户/当前proof、实际PG同connection/无额外开连接；未运行层级明确not_run。原源码调用链/测试及新freeze需非作者复跑。兼容旧cookie入口；无新依赖/锁变更。回滚只恢复旧wrapper实现和停止新公开producer，不删除job、payload、事实或历史。当前完整typed出版、REST/MCP/插件仍必须另接线。
