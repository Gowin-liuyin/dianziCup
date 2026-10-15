# CR-R08 · 公网安全总量的不可变持久化与内部服务

状态：awaiting_review；建设范围经主控 /root 在 2026-10-16 明确授权，准确落实待独立审查。基线 `8a1b04d48346d8550f0326a77f003246a0ebbab5`；本单不批准公共 API/schema 或原 T 卡验收。

R08 / T08、T19、T23 要求成功、零、缺失、无权限和错误可区分，供应商明细不得流入业务存储、日志、缓存或模型；过期总量不能代表当前资产。原 `AggregateObservation`、`ExposureAggregateValue` 与 `r08-product-name-1` 查询目录原样复用。服务仍仅接收 ollama/vllm 两个枚举，不接收 URL、任意查询、凭据或客户端 tenant_id。

新增唯一表 `r08_aggregate_observations` 与现有知识库共享 metadata：UUID 不可变观测、现有 observation 规范 JSON/sha256、provider/query/version、retrieved_at UTC、observed_at 可空、outcome/固定 error、live/fixture、费用 unknown、服务器决定的 public/tenant 范围。具体命名列类型、Check、Index、固定安全异常的 UPDATE/DELETE 拒绝 trigger 见 [DDL 提案](../../reports/runs/recovery_r08_aggregate_persistence_20261016/ddl_proposal.sql)。主控唯一编写 0019 生产迁移；本切片隔离测试库从 0016 只创建自有表与该表触发器，不证明生产迁移通过。

`save_observation(observation, scope, policy, recorded_at=..., observation_id=...)` 在单个短事务内追加。相同 UUID、规范 JSON/hash/call-key/scope 相同为幂等；任一不同为 typed collision，事务回滚。不以 payload hash 对所有历史去重。数据库 trigger 拒绝历史 UPDATE/DELETE；未来 retrieval 保留为历史，当前读取排除；新输入不能通过更晚入库时间把较旧 retrieval 覆盖成当前。

`read_latest(provider, query_id, scope, policy, now=..., available_only=False)` 先选最新任一 outcome。按 retrieval、recorded_at 降序排序；同两时间取失败优先，再 UUID 确定排序。`available_only=True` 仅服务的 `previous_available` 历史参考使用，绝不用于替代最新失败。读取校验 JSON、hash、重复列和服务器 call-key/范围/模式。未知 observed_at 的 freshness 为 unknown；retrieval 或 observation 任一达到 86400 秒即 stale，当前 value 为空。错误不会回填 0。

`AggregateServerPolicy` 是内部服务器组合参数：闭合 authorization_profile、data_mode、collection_authorized、visibility。call-key 只含 provider/query/version/mode/服务器授权 profile；不含密钥。tenant identity 来自现有 `AccessScope`。public 写要求 MANAGE_PUBLIC_SOURCES，tenant 写要求 WRITE_ASSET；读分别要求 READ_PUBLIC/READ_ASSET，tenant SQL 范围从 scope 构造。服务器须对付费调用预先授权；此服务不会自行获授权、读取凭据或构建绕过网关的客户端。

`collect_provider_aggregate_observation(provider, query_id, scope, now=...)` 使用注入 `AggregateConnector` Protocol，接线原 Hunter/Quake connector。每个入口最多一次 adapter collect，无自动付费 retry；真实 connector 既有白名单网关 deadline 为 20 秒。`collect_product_aggregate_observations` 最多两个 provider，明确顺序执行，wire 总上界为 40 秒，另外有短 PG/cache 操作开销。主控 R07 可将两个供应商拆为两个子任务；本切片没有 ThreadPool、强杀线程或通用执行器。

服务实例内最多 4 个同时在途键，重复键立即返回 rate_limited/collection_in_progress，不排队重试。provider 网络 IO 无 PG 事务、row lock 或 advisory lock。独立进程/实例仍可能各调用一次；本实现不宣称 exactly-once 付费调用，跨实例调度由 R07 唯一任务状态负责。已持久且 retrieval TTL 有效的 available 总量可复用，但 observed_at 缺失仍 unknown；失败、缺失、权限状态不伪装 available。

可选 `SafeAggregateCache` 只作为服务器注入接口：仅写已提交 live available 的 UUID/hash/provider/query/version/mode/安全总量与时间，TTL 不超过 PG 值剩余有效期。每次先读 PG，再验证 cache identity/完整安全载荷；损坏缓存不能替代 PG 值，缓存异常独立标 failed。fixture 模式绝不触碰共享 cache，live/fixture call-key 不同。尚未实例化 Redis、未新增 Redis/TLS 配置或 bypass；具体 Redis IO 验证 not_run。

外部异常安全归约为现有固定 network_error/invalid_response 观测后保存；独立持久化失败返回 persistence_failed、没有当前值且不推进缓存。不保存 response 原文、headers、主机资产或密钥，不发 public outbox、不传给 LLM。暴露字段/公开发布仍由主控接线；本切片不改 enrichment/publisher/worker/API/frontend/progress。

回退方式是主控暂不启用该内部服务，保留已追加观测；不删除旧表或历史，不运行 downgrade。费用、查询误匹配局限沿用现有类型，实际费用仍 unknown；本轮测试全为显式 fixture/合成边界输入，没有模型或测绘真实请求。

## TTL 剩余期修复 1 · 2026-10-16

独立审查在冻结 `6706cd9eeae8bae612fc7e86dff2e2b0416eeaef` 复现：年龄 86399.5 秒时旧公式 `86400-int(age)` 写入 1 秒 cache，超过 PG 剩余有效期 0.5 秒。主控明确授权在独有 fix1 工作区修改剩余期的计算顺序，建设范围之外的公共 schema、24 小时 TTL、阈值、分母、原日志和原观测均不变。修复用 `floor(86400-age)` 分别限制 retrieval/observed 剩余整秒，再取最小；零或负剩余整秒不写 cache。PG 尚未过期的 0.5 秒总量仍按现有语义 available，未知 observed_at 仍 unknown，cache 独立不使用。详见 [fix1 报告](../../reports/tasks/R08-cache-ttl-fix1.md)。该修复准确落实仍 awaiting_review，原作者不签 accepted；原 320 项历史检查不作为新 SHA 验证。
