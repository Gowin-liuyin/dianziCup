# CR-R04 / R03 · 任务和游标执行冻结细则

记录者/root；首次创建/本次写作开始/结束/最后更新时间：2026-10-15T11:44:14+08:00。
状态awaiting_review；落实已授权R03/T07/T08/T16，非新增产品范围、评分或架构决策。0011先由主控统一冻结，业务实现只消费该schema，变动先报主控。

## PG与接口

PostgreSQL始终唯一任务/事实/游标权威，Celery+Redis只交付job_id引用，不存另一份业务结果。0011在job_runs增next_retry_at/started_at/finished_at/error_code/result_ref，outbox增delivery_attempts/next_delivery_at/last_error_code；job_payloads按job_id保存<=1MiB bytes，new payload_ref=pg:job:<UUID>；已有pg:change:<UUID>沿用并检查同scope与digest。旧纯hash无法恢复内容，原样保留，消费必须blocked legacy_job_payload_unavailable，不编造payload。新job_transitions只追加attempt/status/reason/真实时刻，不含原请求/凭据。

旧全局idempotency_key唯一改为(COALESCE(tenant_id,''),job_type,idempotency_key)唯一；tenant空字符串拒绝；key相同scope/type/digest复用，跨租户同key独立、异payload冲突。enqueue_job同Session保存job+payload+outbox，事务失败不占key；并发需PG锁/唯一保障，不允许只先读后插。

保留现有job函数业务名，claim_next_job返回本次UPDATE后的行（含正确attempt_count），用FOR UPDATE SKIP LOCKED查queued、已到next_retry_at的retry_wait、过期running，attempt<max；耗尽的过期running不能永远挂住。新增claim_job按ID可共用内部查询。renew_lease/complete_job/schedule_retry_or_fail新增必须关键字expected_attempt，所有原调用方/测试同步传claim返回attempt_count；必须同时running、owner、attempt相同、lease_expires_at>现在。attempt单调递增即fence，不能复用静态owner绕过旧generation。完成/失败与业务结果同事务；失效owner不能提交。retry_wait持久next_retry_at，唯一重试层在PG任务调度；5s起、指数增长、上限300s，max_attempts有界<=10，Retry-After可有界覆盖。永久401/403 blocked/failed区别明确，不无限重试。

relay_pending_events只有调用实际publisher成功后才标published_at；要求显式publisher回调且有界limit，FOR UPDATE SKIP LOCKED避免并行双发。broker失败保留未发布、登记固定失败码/次数/下次时间，不回显底层连接串。发布成功后事务提交前宕机可以重投，消费者PG lease+幂等保证无重复副作用。测试回调必须显式fixture；生产发送统一固定Celery task名+job_id，不信任topic为可执行函数。

生产worker固定handler注册表，输入严格schema、没有任意shell/SQL/URL。建议JobExecutionContext(job_id,worker_id,attempt_count,tenant_id)，handler(Session,context,payload_bytes)->JobExecutionResult(outcome/result_ref/error_code)。先短事务claim提交，再同一个业务Session锁定并验证lease、调用有界handler，最终再次验证当前时钟与lease、complete和业务变化原子提交。失败回滚后新短事务记录retry/blocked。未知job_type blocked unsupported_job_type，不伪造成功。正式来源handler由R04接共享服务；至少一个有真实可观察PG效果的受控内置任务与实际Celery进程消费/重复/失败恢复作为R03证明，不能只心跳或直接调函数。API/worker不能自动迁移。

## source cursor

source_cursors按source_id+stream_kind(live/backfill)保存cursor_json/window_start/end/watermark/last_successful_page/lease_owner/expiry/generation/updated_at。领取时有效lease拒绝，重领generation递增、续期/提交必须owner+generation+未过期。窗口end在采集前冻结。source_page_receipts(source/stream/page_key SHA256)记录输入输出游标、已保存revision_ids、可恢复failed_job_ids、entry_count/真实提交时刻。source范围和敏感性由认证/固定来源配置校验，不能请求体tenant自报。

逐页在同PG事务保存每条原文/修订或明确可恢复失败job，并在全部成立后更新cursor+receipt；失败/False/缺ID不能仅丢进内存quarantine仍推进cursor。解析尚未完成可通过durable parse job推进原始采集游标，原文未取得必须有durable失败job引用、同scope/源/条目可恢复。callback抛错则回滚整页，已存对象允许成为可安全回收孤儿，不能清除其他已引用对象。重复页同page_key复用receipt；已过期owner/错generation/旧输入cursor拒绝覆盖新页。既有StreamState内存只供显式fixture兼容，不能是产品状态真相。

## 验证、兼容与回滚

原T07/T08/T16六项完整保留，加真实两worker抢占/旧owner在未被新worker领取前也不能过期提交/同owner旧attempt/未到期retry/幂等跨租户及并发/relay断线和重复/进程死亡恢复/失败页游标不前进/允许durable恢复job/重启持久。不改金标/阈值/分母或skip。新数据库r03_jobs_20261015独立，不升级正被固定0009/0010审查的库。0011真实空库/0006/0009路径与列映射165混合unit+PG检查于11:41:46–11:41:59通过；它只是schema准备，不是执行器/游标功能通过。只前向修复或隔离备份恢复，拒绝破坏性downgrade。主控唯一迁移/锁/公共schema/状态/Git所有者，实施者只awaiting_review；新初审Agent复跑后才可登记有限结论。


2026-10-15T11:57:27+08:00 · 游标内部表示补记：source_cursors.cursor_json内部使用position与window_complete envelope；公开SourceCursorLease、receipt及commit_page输入输出仍是connector dict，不暴露envelope。未完成窗口claim必须恢复原start/end，完成后按caller显式新窗口与重叠策略开始；release后的旧lease不能写。该约定由主控冻结，执行包报告需一致。

2026-10-15T11:57:27+08:00 · 显式公共DoH配置：本机系统DNS将公开NVD解析为198.18/15保留地址，继续拒绝。仅可信部署配置可选择dns_resolver=cloudflare_doh（默认system，无失败后隐式切换）；使用dnspython2.9成熟wireformat解析，并复用同一个有界、严格CA、固定已检公网IP的HTTPS网关访问固定1.1.1.1/dns-query。没有并行HTTP客户端/代理路径，最大DNS响应65535字节、同总截止时间、最多A/AAAA两问；原目标所有IP/peer/SNI/Host验证均保留。增加一个成熟DNS依赖而不手写wire协议，试装doh extra引入的额外HTTP2栈已移除、最终仅新增dnspython；锁文件67packages。官方依据[Cloudflare](https://developers.cloudflare.com/1.1.1.1/ip-addresses/)、[dnspython](https://dnspython.readthedocs.io/en/stable/message-make.html)。

系统DNS阻断与严格TLS curl403均保留为失败事实；11:53:40–11:53:41该真实网关显式DoH访问services.nvd.nist.gov API实际200、3106字节、一条CVE-2024-28224，原始响应hash与收据留档。不计持续采集、数据库闭环、模型live或正式性能。兼容回归首251范围有1失败/250passed（提前捕获系统resolver方法令原注入失效）、已修成仅显式DoH保存可选解析器，系统路径仍按传输对象当前方法调用；最终251passed/0失败/0skip/cov69.89%。未改原并发断言或skip。该网络整体候选仍须新独立审查，不凭author自检过门。

2026-10-15T12:06:22+08:00 · 同窗口水位冻结细则：cursor_json envelope可暂存pending_watermark_published_at（UTC ISO），未完成窗口中收集的有效发布时间不提前写authoritative watermark；只有最终页事务提交时max合并水位并清理pending。公开connector cursor不含该字段。实现者须验证重领、最终页失败和空页不提前推进。

2026-10-15T12:26:03+08:00 · 网络独立初审f0e0b19五项Must与修复待复核：跨origin Location反射query秘密实泄漏；DoH A提前返回未查AAAA；无关owner/CNAME环/TC被误接受；内层deadline重建导致过期后仍发请求；无Content-Type的401/429误分类。复用dnspython.resolve_chaining并核验question/ID/rcode/TC/owner，A与AAAA均取且所有返回地址须公网。内层fetch增加可选绝对deadline并取min，构造耗时不能刷新剩余预算；numeric IP跳过系统DNS。跨origin剥离所有敏感query及含已注入secret的query，路径反射拒绝，Authorization等不再注入，响应headers已知secret额外替换。非2xx不读取/解码body，保留真实status和Retry-After供唯一PG重试层分类，禁止把认证失败变为空成功；既有FixtureResponse错误reads1改0以要求根本不读取错误body，其余状态/连接/次数断言保留。新增DNS/实际HTTP序列化负例，root fullunit+T08security/contracts327passed/0fail/skip/cov66%，Ruff0/mypy64files0。12:24:39–42真实DoH NVD200/3106bytes，只一次无秘密GET诊断。最终审查仍awaiting_review，原初审失败证据保留，不用先前200抵消安全问题。
