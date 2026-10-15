# CR-R07 · 幂等主体与事件路由范围

状态：`awaiting_review`，主代理已批准本窄方案实施；这是 05 合同 §2 的落实，未修改公共合同、评分、阈值、金标或业务状态。

旧实现将父 job key 与 workflow UUID 仅绑定事件 tenant 和客户端 raw key，遗漏认证主体和事件 route。独立真实 PG/HTTP 两探针确认，两合法公共管理员或同管理员两个事件路径共用 key 时第二次错误 409。

新增独立常量 `ENRICHMENT_IDEMPOTENCY_NAMESPACE_VERSION='r07-scope-v2'`。规范 JSON 固定包含 namespace_version、认证 `current.tenant_id`（真实 null）、`/v1/events/{canonical UUID}/enrichment-jobs`、`current.user_id` 和原始 key，经 SHA256 得到 77 字符内部 key。父 job/outbox 使用同一规范 key，workflow 为 `uuid5(NAMESPACE_URL, 'ai-intel:enrichment:' + parent_key)`。`/api/v1` 是同一业务 route 的 alias。父 job.tenant 仍为事件真实业务范围；身份不从 body 接收。JSON 避免 delimiter 碰撞、null/public 字符串碰撞和 raw key 长度扩张。

session 不进 namespace，仍冻结在完整 binding；同 actor/route/tenant 的新 session、body 或服务器 policy 变化继续 409。RULE_VERSION、worker payload、已有请求/源快照和调用预约协议保持原格式，不让 namespace 修复失效旧执行任务。

复用新记录前核验 parent type/key、PG payload reference/hash、workflow UUID/parent relation/scope、请求与 policy 型别/摘要、完整 binding 与 rule。没有新范围记录时查旧事件 tenant+raw key，仅查 ENRICHMENT_PARENT_JOB_TYPE。旧 UUID 必须等于源码真实算法 `uuid5(NAMESPACE_URL,'ai-intel:enrichment:'+repr((event_tenant,raw_key)))`。旧 self-consistency 全部成立且 actor/event/authenticated tenant 与当前完整 binding 相等才保留旧 UUID/parent 并 reused；同旧 actor/event 任一绑定差异仍 409。合法另一 actor/event 不阻断新 v2，旧记录原样保留。未知、orphan 或篡改的预期 enrichment parent 固定拒绝 409。

raw key 若恰等于已有合法 v2 内部 key，仍须核实际 type/key/UUID/WF/PG payload 和摘要，随后识别为非 legacy，建立该 raw key 自身的新规范范围。非 enrichment 来源任务同 key 不被读取或重绑，也不阻断新富化。新 v2 并发唯一仍由既有 enqueue_job 的事务 advisory lock 保证，不改 outbox/worker/source。

旧已预约的潜在付费 child 被直接复用，reservation 和 trace 不变；不为修 namespace 重发调用或新建同范围 workflow。回滚应保留本兼容读取/键生成能力，或停用新 enqueue 接线并保留全部历史；不得仅恢复旧 namespace 后把已有 v2 当不存在收费重放。无迁移、删除、actor/UUID 重绑或旧 receipt 覆盖。

实现范围只有 job_service.py 的 enqueue 与直接必要 helpers、新专属测试和本批材料；原 API/settings/workers/shared contracts/migrations/table metadata/依赖/progress/旧测试未改。代码与材料 SHA、真实红绿测试见任务报告；由原独立 reviewer 定向复核，执行者不签 accepted。
