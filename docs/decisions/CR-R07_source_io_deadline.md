# CR-R07 · 原文读取事务与绝对截止时间

文档首次创建时间：2026-10-17T04:26:11+08:00
本次写作开始时间：2026-10-17T04:26:11+08:00
状态：approved_for_implementation；新冻结实现须独立复验，不能据本文件签验收。

这是对已批准 CR-R07 原文证明桥和 CR-R14 SourceReport 消费合同的落实：两次短事务之间读取原文，整个请求最多五秒的共同绝对 deadline。独立48审查用原五秒得到5.203秒Timeout，证明读存储没有接收截止时间；活动事务候选仍等无SQL观察确认，不能把观察器自己的SELECT auto-begin当缺陷。

共享 ContentStorage.read_verified 新增可选 keyword-only deadline_monotonic: float | None = None，原调用者省略时兼容原行为。ContentStore、MinioContentStore和直属测试存储同步该协议；必需deadline路径检查有限数值/已到期，在IO前及各有界读取阶段保留剩余时间，真实网络必须受整个剩余截止时间约束，不能只读完后报Timeout或复用10秒网络timeout。不得以无界后台线程继续读来伪装截止返回，不重新发明任意URL客户端。复用成熟存储/网关与已有进程隔离；若必须用新有界执行边界须完整关闭其资源，不把fixture当live。

StructuredFactProofReader先在短事务核身份、scope、修订/事实元数据、模式与指纹并退出；IO无活动PG事务/行锁，最后短事务重新锁当前身份并核完整指纹、模式、权限及epoch。过期、修订或授权变化明确失败，不返回旧可用证明。来源reported不等于资产确认/Strong/QA支持，原强证明门不放宽。跨多个refs共享原绝对deadline，不能每个ref重置五秒。

兼容：仅内部可选参数，无公开DTO/评分/金标/迁移/新依赖。旧非deadline调用语义保留；新R14消费者须强制deadline。回滚停止受此新内部版本影响的活动任务并恢复旧reader/协议，保留事实、操作回执、历史及原失败。不同业务版本不拼同一稳定窗口。影响R02/R07/R10/R12/R14/R18/R20全部存储调用者，必须先索引并rg核全部实现和调用方，不以Any/cast/忽略掩盖协议失配。

验证：真实延迟存储/慢响应与断流、剩余deadline耗尽、Unicode/大小/hash、并发独立deadline、不持续后台IO、初/末身份和版本失效、IO期间真实driver事务状态无SQL观察、57014/55P03映射与其他SQL错误传播；原348/304/658与affected原PG回归按必要去重。旧R10合成事实helper若缺mode/policy，仅明确fixture输入标签且记录逐字段变更，原断言/URI/金标不变；unknown/unmarked生产输入继续拒绝。最终deadline、真实PG/live/性能/人工各层分开，未运行not_run。


## 2026-10-17T05:17:54+08:00 · Windows原生执行边界的根因修复

新独立诊断以同一固定worker/guard证实NO_WINDOW派生额外conhost，而DETACHED_PROCESS保持PIPE与正确退出并减少两个console进程；冻结4d实际150ms原文deadline在656ms才OSError，最终8365byte stdin同步write未受communicate timeout约束。唯一IO作者获准仅将固定contentworker与共享_start_windows_cpu_guard的creationflags改DETACHED_PROCESS(0x8)，保留handle_list/PIPE/DEVNULL/Job/no-breakaway/并发slot2/原CPU与memory/进程10。不能过早退出持lastKILL_CLOSE handle的guardian。PDF与semantic全部受影响原生回归及typed失败必须复验，原CPU1秒红不能降低阈值。

最终编码的内部配置有明确小上限，并在fresh sole-writer stdin实测pipe容量足以容纳完整bytes后才写；GetNamedPipeInfo不是任意时点free容量证明。worker在guard readiness前消费配置，startup仍归父绝对deadline。秘密不写tempfile/CLI/env，不用无界writer线程；非阻塞/短写需准确处理。清理保留主Timeout/取消并分别关闭pipe/held handles；未确认worker及guardian终态不能释放slot冒空闲，应保留有界owner状态供关闭复核。只允许定向私有native身份/终态判断，不建立通用平台或改共享guard生命周期。

原4d/5a7 WIP及cap12/cap11/无XML红保留，既有658/76只归各自代码hash；新固定实现等待新的独立审查、真实PG事务两围栏及实际MinIO集成。loopback SDK与harmless native不计实际MinIO live。
