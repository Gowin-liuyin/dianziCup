# CR-R14 · 认领前投递恢复与有界补偿

文档首次创建时间：2026-10-16T18:21:19+08:00
本次写作开始时间：2026-10-16T18:21:19+08:00
状态：approved_for_implementation；本次用户完整批次授权内必要缺陷修复，awaiting独立复核。

实PG诊断source b8b75/ed549证明认领前OperationalError被Celery ACK后job仍queued/attempt0/leaseNone，publishedoutbox1且recover0，重进程也不补。旧恢复只扫running根因共享，不能仅补调查一个caller。独立报告G-D-R14-default-runtime-review-1.md与R14-preclaim-recovery-diagnosis.md保留原反例。

批准唯一作者workers/jobs.py/runtime.py和调查专用driver：due queued/retry_wait在最后真实published_at超过60s且无有效pending时，同事务SKIPLOCKED追加同job/payload outbox；无outbox仅created_at超过60s后补，已有有效pending不重复。全job历史delivery_attempts聚合上限job.max_attempts×3（默认15），耗尽job failed/delivery_attempts_exhausted；终态或耗尽未发outbox仍published_at NULL，next_delivery_at UTC9999-12-31和固定停止错误，不假造publication。一次GROUP BY聚合后join，不逐job扫描；beat扫描→relay持固定事务advisory try-lock，抢不到返回既有字段0。task从权威PG job_type选取，不信broker自报topic；消费前PG失败标delivery_unavailable，directdriver保留原OperationalError oracle，补偿靠共享PG扫描，不无界autoretry。

兼容/迁移：无新表/索引/身份权限/任务业务attempt/lease/模型预算更改，source450/caps不改；对既有shared任务恢复生效。回滚可停新dispatcher入口，保留真实outbox/事实/history，不downgrade/删除旧任务。测试：原queued反例原断言、重复beat/并发/有效pending/后续retry/15次上限/终态不可假published/原消费者、真实PG/Redis/Celery单workerACK补偿/重进程恢复。独立reviewer固定新source亲跑；6类及live分列。Root批准own Redis26489 64MiB CPU0.25/PIDs32/maxclients16、≤15min、PGslotA≤2conn，0model/public请求。原PG服务不重启不清队列，持久秘密只环境/加密引用。共享事实权威仍PG，费用unknown，评分/盲测不变。

本次写作结束/最后更新时间：2026-10-16T18:21:20+08:00；修订人/root。
