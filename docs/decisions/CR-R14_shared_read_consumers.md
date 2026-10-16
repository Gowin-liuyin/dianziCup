# CR-R14 · 调查角色消费共享只读服务

文档首次创建时间：2026-10-16T23:31:37+08:00
本次写作开始时间：2026-10-16T23:31:37+08:00
状态：approved_for_implementation；新非作者核对授权、实现和真实 PG 后生效。

授权依据：本次 R00–R24 有界批次、R14 九职责协作与既有共享工具合同。源候选为 5883a79458533f752f88ebc3ec62fceb85afbf16，材料为 a9b78f98ccbd40a3ac15fc42d8fde879918c1a76。公共 schema、金标、阈值、分母、总八次工具预算与 B2/B2b/B3 策略保持。

Collector 从真实 Graph 节点调用 GetAdvisory；Assessor 在资产与不可变快照成对存在时调用 GetInventory；Reporter 通过 FindChanges 读取分页变化。复用 PostgresReadToolAdapter、认证绑定、PG 操作预留和 typed receipt，禁止私建另一套事实权威。SharedReadData 不作为 QA 引文支持。读取公告不代表重新采集，读取快照不代表完成最终研判；相应职责明确 partial。变化分页只有 next_cursor 为空才完成，预算停止、部分读取与错误不得折成空成功。

内部版本标识 shared_read_consumer_version=r14-shared-read-consumers-1 进入既有配置/输入绑定。缺失或不一致的旧配置停止继续执行，避免恢复时再次付费或覆盖历史。已认证终态的 finish_stale 不重写终态 PG；旧历史 HTTP 查询是否仍可读取需另外证明，不以 PG 保留推断 API 历史已完成。

兼容与迁移：无新表或数据迁移，不重写旧输入、操作、答案、资产快照或历史。旧配置运行与新版本隔离。回滚恢复原消费者版本并停止新版本活动任务，不删除已存回执；旧调用路径只可在相符的原配置下恢复。

任务与测试影响：R14/R17/R20/R21 需验证默认 Graph 入口、实时 ACL、重放/预算、失败语义、分页以及旧配置。既有两处 PG 工具次数断言按新增真实调用精确修订，分别包括 advisory/triage/supports/changes，原 Oracle 与初红归档；不是修改评分分母。作者 234 离线通过、五项新增 PG 仅 collect，不能据此验收 integration。新 reviewer 必须亲跑关键 PG 与旧断言，记录审查 SHA、命令和范围。

本次写作结束时间：2026-10-16T23:33:40+08:00

修订记录：2026-10-16T23:33:40+08:00；按本轮工具实际 UTC 时钟纠正初稿误填的未来时间，开始时间依据首次写作工具时间。
