# R04 · 固定来源分页任务装配细则

状态：awaiting_review；落实已批准的 CR-R01–09、R03/R04，不新增评分、来源类别或资产访问范围。首次创建和本次写作时间由主控运行收据记录，历史未发生的阶段通过不补写。

## 输入、执行与原子性

仅注册 nvd_ollama、vllm_vendor 两个固定公开来源；可信部署选择已有 DNS 配置。任务仅接受来源枚举、backfill/live 流、带时区的观察窗口截止时间、剩余页上限，不接受 URL、凭据、租户或可执行函数。公开来源只能由认证所得的无租户系统管理员提交；worker 使用固定内部公共来源权限，不接收自报身份。

每个任务处理一页，复用现有 execute_job 的 PG 围栏事务：确认固定来源→claim 来源游标→有界网关 GET→严格解析并保存原响应、成员修订、证据及事件→commit_page→release→任务完成。保存、分页回执、下一页任务/outbox 与本页完成状态同事务；错误回滚，不能仅凭 HTTP 200 推进游标。对象存储遗留孤儿沿用受锁保护的回收，不删除已引用对象。revision_ids 严格按来源记录输入顺序匹配；event_ids 可因跨来源别名解析而去重，禁止按其位置匹配记录。

每页 NVD 20 条、vLLM 10 条，单次 GET 总预算 12 秒、响应最多 5 MiB；每轮最多 20 页，每任务最多 3 次，由既有 PG 任务层重试。下一页 outbox 至少延后 7 秒，禁止 handler 内睡眠或另建重试层。页数用尽但上游仍有下一页时任务明确 partial/source_page_limit_reached，游标保留未完成位置，可显式续接，不声称采完。

## 分页和时间语义

NVD 使用固定 Ollama keywordSearch 查询与 startIndex，vLLM 使用固定仓库 published advisory 查询与 page。NVD 的下一页来自实际响应的 startIndex/resultsPerPage/totalResults，且须与请求一致；厂商页满则请求下一页确认，空页才结束。完成页输出空位置以便下一轮从首页重读；同源相同原文由现有版本服务幂等复用。

当前窗口仅记录观察轮次的开始/截止标识，**不是上游不可变快照或时间过滤覆盖保证**。未核明时区的 NVD 原始发布时间保持 unknown；本实现不据此推进发布时间 watermark，不声称完整增量监测或同版本持续运行。R06 负责来源广度、时间过滤、重叠补采与正式观测，R16 负责撤回后的结论失效与历史重判。来源原文中明确撤回/Rejected 状态留档，不将事件 active/merged 注册状态解释为仍有效或安全。

## API、兼容、回滚与验证

来源调度接口返回 PG job_id/状态引用；查询只读 PG 任务、来源游标与最新采集观察。写操作复用 session/Origin/CSRF 与系统管理员权限；普通租户不得借公共 job 读内部 payload。只返回固定错误码和内部引用，禁止回显原请求/连接串/凭据。

无需 schema、锁文件或原 read DTO 变更；新增固定 handler 与管理接口。回滚应先停止本轮调度并保留所有任务、原文、回执和历史，不 downgrade/删除数据。未识别 handler 仍由现有执行器 blocked，不伪装成功。

必要验证：真实 PG 页保存失败/任务失败均不推进；重放/两 worker/过期围栏；固定 URL 与 HTTP 分类；下一页持久延后/页上限 partial/空页；管理员与 CSRF/租户拒绝；真实公开 GET→MinIO/PG→worker→API→浏览器。fixture、直接 handler、真实队列和 live 证据分别记录，不相互替代。新独立 reviewer 复跑后才能登记限定通过，整卡与阶段条件不减少。
