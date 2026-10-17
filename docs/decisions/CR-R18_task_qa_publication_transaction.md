# CR-R18 · task QA 发布事务失败边界

首次创建时间：2026-10-17T10:11:41+08:00
状态：已有construction授权内必要实现；准确落实 awaiting 独立 review

原CR-R18_task_qa_publication_receipt.md aa4b3 固定字节保留。新publisher采用已验证owned task的caller root Session/transaction，不新open/commit/close、不用nested savepoint绕现reader根事务fence。真实QA与critic回执、answer、公证receipt、typed locator与complete_job在一个publication atomic unit；MAX_WORKFLOW_OPERATIONS/WorkflowBudget不抬。

写入之前未授权/输入错误拒绝，不回滚无关事务；开始本发布写入后遇任何异常，强制rollback当前caller root事务（包括同事务预备写）。成功只返回由caller commit。即使caller吞异常后commit，也不能留下answer/proof/locator/job success。后续失败标记由上层另一个受控事务完成；先前已提交的真实model回执保留。必须测试lease/auth/DBclock late failure及实际rollback，不能只测试raise。

兼容：仅新publication port显式定义rollback ownership，旧同步QA/typed binding方法不改。无表/迁移/外部服务；回滚恢复新port版本且保留事实历史。影响R14/R18/T35及PG事务/恢复验收；未接默认worker/API不能计完整。

修订记录：2026-10-17T10:11:41+08:00 Root明确原子失败义务，避免只抛异常但被上层提交。
