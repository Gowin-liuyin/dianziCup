# R06 自动轮询装配小合同

本条落实已批准CR-R03/R06的持续采集目标，不改变官方指标/类别、原任务验收或授权资产范围。冻结供实现与独立审查；awaiting_review，不签整阶段。

输入是可信部署SOURCE_POLLING_ENABLED（默认false，compose同名显式透传），不是网页或任务可指定的URL/代码/租户。开启后既有beat每60秒发送受限poll_due；可信内部无租户system_admin只为CATALOG_SOURCES九key安排live任务，vLLM每1800秒，其余3600秒；每轮最多5页、原每页3次上限与7秒间隔不变。P0五分钟是计划目标，当前策略仍需实际时效验证，不能以配置证明达标。暂停配置不取消既有工作，不丢游标。

直接复用job_runs/job_payloads/outbox、enqueue_source_page、固定来源注册与原PG游标，不加调度事实表。UTC时间桶及source key确定唯一poll-v1 key与固定window_end，重复tick/多进程/重启同桶不增加root jobs；队列内正在处理的该源（包括continuation）先续接，不能无限叠加轮次。后台连续积压>500或存在非法/超4096字节的source请求时本轮明确失败，不当作零变化或吞异常；源请求当前合法合同远小于此界。事务回滚不保留job/outbox半成品。外部IO仍仅由source worker网关执行，poller本身不联网。

兼容性：原POST/GET/权限/DTO、source_kind集合、手动采集和测试默认不变；SOURCE_POLLING_ENABLED=false时不注册beat自动采集项，任务直接调用也只返回disabled，不连接PG。配置开启会产生实际公开源请求，运行手册需记录资源/时段与数据版本；不调用模型或测绘付费接口。

迁移：无需数据库迁移或数据清理；所有状态由既有PG表支撑。回滚：关闭配置并重启worker/beat即可停止新轮次，已入队与已存原文/历史保留；旧版本继续理解已写标准SourcePageRequest。不能删除旧任务/重置游标作为回滚。

任务/测试影响：补R06:T49/T54连续采集调度能力；不表示R06九通道或时效通过。核验重复tick、UTC边界/时区、并发不同进程、积压、continuation、崩溃后重放、事务回滚、无租户system_admin限制、实际beat→PG→worker链。unit/contract使用显式fixture，真实PG隔离库，最终来源live分开记录；原门槛/金标/分母保持。
