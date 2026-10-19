# CR-R10 · 默认图谱消费者接线

文档首次创建时间：2026-10-17T03:42:20+08:00
本次写作开始时间：2026-10-17T03:42:20+08:00
状态：approved_for_implementation；冻结实现须新非作者独立复核，不能据本文件签 accepted。

依据：本次 R00–R24 批次批准的 PostgreSQL 权威、六类关系、Neo4j 投影、更新重判与真实 worker 接线范围。补齐目前存在但未在默认 worker 注册的 graph_apply，保持原强关系证明门、租户隔离、历史、评分分母与金标规则。不存在新增依赖或公开 DTO 变化。

## 最小共享接口与事务边界

复用 GraphRuntimePolicy、GraphProjectionStore、Neo4jProjectionStore、PG job/outbox/manifest 与现有 DetachedJobHandler。运行配置新增可选 NEO4J_URI、NEO4J_USERNAME、NEO4J_PASSWORD，三者必须齐全且非空；密码保持 SecretStr，不进日志。URI 只允许无账号、路径、query、fragment 的 bolt/bolt+s origin；明文 bolt 仅 APP_ENV=test，其他环境须验证 CA 的 bolt+s。未配置保留原非图功能，图任务明确不可用，不能内存替代或静默成功。

默认工厂使用已锁 Neo4j 6.4 driver；连接池最多二、网络与获取连接超时有界、关闭 driver 的 finally 属于工厂拥有者。创建其他业务 handler 时不连接图服务或执行 schema；仅实际 graph_apply 在执行前复用固定 initialize_schema。图服务不可达不能阻止普通来源 job 被构造。

knowledge_change 的图派发不能机械依赖后段 R12 已完整验收。配置图时采用现有 detached 执行的两个有界 PG 阶段：先核 canonical 当前租约/任务/scope，在同一事务幂等登记 graph reconciliation jobs 后提交；再重新核 canonical 租约，调用原 hybrid handler。图派发事务无外部 IO；第二阶段失败保持真实错误与父任务恢复语义，已登记图任务不回滚或再次扩大重复队列。不得将图派发返回值当成整个知识变更完成。共享最终 fan-in guard 继续负责各消费者资格，其他消费者缺口仍 partial。

图任务权限由服务端 canonical PG tenant/job context 派生最小 READ_PUBLIC 或相应租户 READ_ASSET scope；不能接受 payload 自报身份或引入 system-admin 万能授权。图捕获保留 active 与历史事件集合，generation 绑定完整 scope epochs、规则和 namespace，变化后不得复用旧 manifest。Neo4j 只是投影，最终有效性仍回 PostgreSQL 验证。

## 兼容、迁移、回滚与影响

无数据库迁移、依赖锁更新、公开 API 字段或旧事实重写。未配置图的部署保持现有行为；新增配置错误在启动校验时明确拒绝。回滚停止本版本图任务消费、恢复旧默认 handler，保留 PG 原任务、manifest、投影与历史，不能删除证据。配置私密值仍从环境或秘密管理读取。

影响 R10/R12/R16/R20 与原 T 图谱、索引、更新任务的能力切片依赖。图捕获和混合检索的执行依赖拆开，不减少任一原 T 卡最终合并验收。控制器固定912来源窗口使用独立冻结 Product，不因 Root 的新图接线被覆盖。

## 必需验证与当前证据

配置相关 36 例真实离线回归通过，mypy 204 source files 通过；它们只证明配置与类型，没有证明默认图工厂/worker 已接线。原配置测试误继承 fixture 环境与一次 Root 误拼测试路径的红日志保留。

实现须查全部调用方并增加：未配置无图 IO、非图 job 不受图宕机影响、driver 成功/异常均关闭、graph_apply 有界失败、canonical 权限/租约变更、重放不重复派发、hybrid 失败后图任务仍 durable、图 unavailable 不被计完成、旧/新/空结果的 epoch 失效。新独审必须运行真实隔离 PG+Neo4j 默认 worker 路径；六类验证、live、人工分别记录，未执行明确 not_run。


## 2026-10-17T13:02:29.454+08:00 · 共享 namespace 与客户端 IO 期限复验补充

新非作者在固定96cf发现 graph_apply 未校factory namespace；共享 apply 在已验证不可变 batch 后、store/ACK前允许窄 batch_guard 同 Session 回调，旧 None 仅保持服务端手动恢复/random generation兼容。RuntimePolicy必须给 guard，校 namespace、partition及完整 scope epoch/rule推导的UUID5。历史batch可ACK为stale，不能伪称current或删除历史；修复986b待实际PG，旧反例保留。原PG仅缺updated_at的调用补既有一次now参数，原断言与全部其他AST保持。

固定c554默认工厂独审真实本地Bolt握手后停止回包：server tx_timeout=3000仍阻塞超过5秒，默认write30；不能拿server timeout当客户端期限。唯一默认工厂作者获准在infrastructure/neo4j_projection.py增加窄官方AsyncDriver/单stdlibRunner同线程bridge，保持旧同步store算法与接口兼容，所有session IO/commit/rollback/consume/close绑定绝对deadline，超时公共AsyncSession取消并拒成功ACK；factory采用官方asyncdriver和实际write deadline。旧同步直调未修的3秒界不被新路径代签。

DNS默认executor可能使Runner关闭等待300秒。允许唯一同模块用公开loop_factory/getaddrinfo与单固定标准库socket.getaddrinfo子进程解决：同OS解析算法和IPv4/IPv6/family/type/proto/flags，只有server固定Neo4j origin，无shell/凭据继承/新外部服务；输出有界，超限拒绝不截断，单时刻最多一child，剩余绝对deadline及持句柄kill/wait退出。无私有pool/executor monkeypatch、不关TLS。正常/失败/取消/任意延迟解析/线程及loop归属均需实际检查；原socket两反例与DNS结果分开。该必要复杂度用于已复现有界IO缺口，无依赖锁/表/评分变动，所有store调用者须回归。回滚恢复旧工厂并保留PG任务/批次/历史，旧路径有界不足仍公开，不降低门槛。
