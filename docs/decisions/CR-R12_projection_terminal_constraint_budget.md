# CR-R12 · 投影提交前最终约束与预算

文档首次创建时间：2026-10-16T12:25:25+08:00
本次写作开始时间：2026-10-16T12:25:25+08:00
状态：approved_for_implementation；fix2仍needs_changes，fix3待独立审查。

实际PG16.14下，0.6秒投影预算遇deferred trigger sleep2，COMMIT约2.14秒且receipt已提交，原红必须保留。独立诊断证实：[postgres.c](https://github.com/postgres/postgres/blob/REL_16_14/src/backend/tcop/postgres.c#L2806)在CommitTransactionCommand前关闭语句timer，[xact.c](https://github.com/postgres/postgres/blob/REL_16_14/src/backend/access/transam/xact.c)其后执行deferred triggers。LOCAL/SESSION/显式COMMIT均不能解决；原作者SESSION根因解释被更正，保留历史。

批准最小修复：有deadline的_projection_session全部writes后显式session.flush()，按单调剩余预算配置statement/lock timeout，执行SET CONSTRAINTS ALL IMMEDIATE，确认之后无新write/re-DEFER，再检查deadline与commit。deadline=None保留旧约束时序。删除仅由错误SESSION假设产生的event/恢复复杂度；不改数据分母、容量10000、FK或业务约束。

SET CONSTRAINTS在常规语句timer内处理最终延迟约束，仍不能对WAL flush/网络COMMIT ACK承诺硬20秒或receipt0。ACK不明保留幂等generation/outbox收据与租约有限重验；rollback方法调用不等于确认未提交。shared worker claim/read/complete三事务整体预算另主控接线，本包不得越权改worker或新增未经审查的状态。

兼容：无deadline旧调用与既有合法child-before-parent保留；新路径检查最终约束不能早于全部writes。迁移无schema变化；回滚撤销新代码保留PG事实与原失败日志。测试须覆盖实际0018 FK/NULL tenant、真实四表原子回滚、ORM flush、晚写listener负例、最终约束缺失、sleep超时、原31PG/默认入口/epoch/网络失败与fresh10001分区容量。诊断5个dummyPG对照不是实际业务全验收。freeze后交原非作者fresh复核，G-D仍partial。

本次写作结束时间：2026-10-16T12:28:28+08:00
最后更新时间：2026-10-16T12:28:28+08:00

修订记录：2026-10-16T14:57:02+08:00，依据独立PG16.14源码复核将关闭statement timer的真实锚更正为2806；原报告与原红不改，业务行为不变。原三个reader/writer/observer oracle实际需要3连接，已另批独占复跑；不能称原58单命令max2全部通过。
