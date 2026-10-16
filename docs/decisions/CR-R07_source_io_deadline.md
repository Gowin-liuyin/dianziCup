# CR-R07 · 原文读取事务与绝对截止时间

文档首次创建时间：2026-10-17T04:26:11+08:00
本次写作开始时间：2026-10-17T04:26:11+08:00
状态：approved_for_implementation；新冻结实现须独立复验，不能据本文件签验收。

这是对已批准 CR-R07 原文证明桥和 CR-R14 SourceReport 消费合同的落实：两次短事务之间读取原文，整个请求最多五秒的共同绝对 deadline。独立48审查用原五秒得到5.203秒Timeout，证明读存储没有接收截止时间；活动事务候选仍等无SQL观察确认，不能把观察器自己的SELECT auto-begin当缺陷。

共享 ContentStorage.read_verified 新增可选 keyword-only deadline_monotonic: float | None = None，原调用者省略时兼容原行为。ContentStore、MinioContentStore和直属测试存储同步该协议；必需deadline路径检查有限数值/已到期，在IO前及各有界读取阶段保留剩余时间，真实网络必须受整个剩余截止时间约束，不能只读完后报Timeout或复用10秒网络timeout。不得以无界后台线程继续读来伪装截止返回，不重新发明任意URL客户端。复用成熟存储/网关与已有进程隔离；若必须用新有界执行边界须完整关闭其资源，不把fixture当live。

StructuredFactProofReader先在短事务核身份、scope、修订/事实元数据、模式与指纹并退出；IO无活动PG事务/行锁，最后短事务重新锁当前身份并核完整指纹、模式、权限及epoch。过期、修订或授权变化明确失败，不返回旧可用证明。来源reported不等于资产确认/Strong/QA支持，原强证明门不放宽。跨多个refs共享原绝对deadline，不能每个ref重置五秒。

兼容：仅内部可选参数，无公开DTO/评分/金标/迁移/新依赖。旧非deadline调用语义保留；新R14消费者须强制deadline。回滚停止受此新内部版本影响的活动任务并恢复旧reader/协议，保留事实、操作回执、历史及原失败。不同业务版本不拼同一稳定窗口。影响R02/R07/R10/R12/R14/R18/R20全部存储调用者，必须先索引并rg核全部实现和调用方，不以Any/cast/忽略掩盖协议失配。

验证：真实延迟存储/慢响应与断流、剩余deadline耗尽、Unicode/大小/hash、并发独立deadline、不持续后台IO、初/末身份和版本失效、IO期间真实driver事务状态无SQL观察、57014/55P03映射与其他SQL错误传播；原348/304/658与affected原PG回归按必要去重。旧R10合成事实helper若缺mode/policy，仅明确fixture输入标签且记录逐字段变更，原断言/URI/金标不变；unknown/unmarked生产输入继续拒绝。最终deadline、真实PG/live/性能/人工各层分开，未运行not_run。
