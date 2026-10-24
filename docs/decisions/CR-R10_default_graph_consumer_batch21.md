# CR-R10 · 默认图消费者协调批次21（graph_apply/reconcile/capture 默认 worker 注册）

文档首次创建时间：2026-10-25T01:20:00+08:00
本次写作开始时间：2026-10-25T01:20:00+08:00
状态：awaiting_independent_review；授权依据：批次21 有界批处理指令 C5.1；上游合同依据 docs/decisions/CR-R10_default_graph_runtime.md（含 addendum）与独立复核 reports/reviews/recovery/G-C-R10-default-graph-deadline-review-2.md（M01/M02 已关闭）。

## 协调合同（冻结）

1. **默认消费者**：默认 worker（backend/src/ai_intel/workers/runtime.py `consume_job`）在配置了 NEO4J_URI/USERNAME/PASSWORD（settings.py:47-49，校验 :78-113）时，经 `ai_intel.knowledge.default_graph_runtime.build_default_graph_job_handlers(engine, settings)` 注册三类图 job 消费者：`graph_apply`（`build_graph_apply_handler` + 永久 guard 的 `Neo4jProjectionStore`）、`graph_reconcile`、`graph_capture`，并组合 `knowledge_change`（图派发 + 原 hybrid 投影两阶段）。未配置 Neo4j 时仍注册三类型，全部显式映射 `graph_projection_not_configured` blocked，无静默成功；非图 job 构造不接触 Neo4j（driver 构造无网络 IO）。
2. **触发与鉴权**：job 由 `capture_event_projection` 同事务 enqueue（graph_projection.py:764-771，idempotency_key=`graph-apply:<batch_id>`）经 outbox 投递后由默认 worker 认领；scope 由服务端 canonical PG 租约行派生（require_job_lease + job_type/tenant 校验 + payload digest 复核），拒绝 payload 自报身份；generation 必须等于 UUID5(namespace, partition, epochs, rule)，guard 在已验证不可变 batch 后、store 写入前校验。
3. **失败语义**：scope/namespace/generation 不符 → blocked（`graph_projection_scope_denied`/`graph_projection_namespace_denied`/`graph_projection_generation_denied`）；digest/capacity/state → blocked；Neo4j DriverError/Neo4jError → `graph_projection_unavailable`，PG 回滚只产生安全重放（Neo4j 先提交、不可变批次幂等重放）。重试沿用既有 job 租约/max_attempts 层，不新增重试层。knowledge_change 的图派发不顶替父任务终态（返回仍 partial + `knowledge_change_other_consumers_pending`）。
4. **不挪 R16 fan-in**：fan-in 收敛域是 revalidation 子评估 receipt（revalidation/fan_in.py），与图投影 ACK 管道无共同合同面；本 CR 不改 `RevalidationChangeRequest`/`RevalidationFanInManifest`，不把图派发返回值当整个知识变更完成。
5. **不动公开合同**：无公开 API/DTO/schema/迁移变化；金标/阈值/分母不变；既有断言不放宽。

## 实现（恢复已审切片 + 两处装配替换）

1. **恢复已审切片**（基线 f3c2e41e3、0291d1975 均为 HEAD 祖先，实施前以 `git diff <base>..HEAD -- <触碰文件>` 复验零漂移）：
   - 切片 A：`96cf0732f`（graph_runtime_policy.py + 直属测试）、`986b01ea2`（ProjectionBatchGuard 窄回调 + guard 语义测试）；跳过过时的 `73634f30f` 中间装配。
   - 切片 B：`c554eae58`（default_graph_runtime.py 默认工厂 + 直属测试）、`2f4e83dcf`（官方 AsyncDriver + stdlib DNS 桥 + thread-ownership close，CR-R10 addendum 对应）、`e8df2b02d`（style）。
   - 恢复方式：文件级取自对应提交（本批次对 r12 帮助模块、批次19 对 r07_input_audit_helpers 的同类恢复先例），不做分支合并。
2. **Root 装配（本 CR 唯一新生产改动）**：workers/runtime.py 导入 `build_default_graph_job_handlers` 并将 `consume_job` 中 `build_projection_job_handlers` 装配位替换之（review2 所述"两处替换"）。
3. **直属测试（新增）**：backend/tests/unit/test_r10_default_worker_registration.py——仿 test_r16_default_worker_registration.py 模式：配置/未配置双参数化，断言 graph 三类型注册与否、未配置时 knowledge_change 保持纯 hybrid、driver close、SOURCE/enrichment/revalidation 装配不受影响。
4. **既有测试适配（CR 登记，非放宽）**：backend/tests/unit/test_r16_default_worker_registration.py:64 的 monkeypatch 目标由 `runtime.build_projection_job_handlers` 改指 `ai_intel.knowledge.default_graph_runtime.build_projection_job_handlers`（hybrid provider 仍由新工厂调用），全部断言原样保留。

## 明确不放宽的内容

- 986b 的 guard 语义与 review2 已关闭的 M01/M02 断言一字不改；`Neo4jProjectionStore` 真实 IO 仅发生在真实 apply 内（离线测试全部走 Synthetic/Mock driver，mock 不冒充 live）。
- Neo4j 真实资源不可用：real_services 组（test_r10_neo4j_projection.py 等）按既有 DPAPI 围栏语义记 blocked/not_run，不伪装通过。
- 停止信号：切片恢复出现语义冲突需改 guard 语义；装配越出"两处替换"波及 r12 投影装配断言或 test_r14_preclaim_recovery 的 `delivery_unavailable` 路径；任何波及公开 DTO/schema/fan-in/jobs.py 重试层——发现即停入 OQ。

## 验收与复跑

- 离线组：r10 全部 unit/contract/security + 两个新增/适配 unit 文件。
- real_pg 组（隔离容器）：test_r10_projection_pg.py、test_r10_graph_validity_pg.py、test_r10_graph_fix2_pg.py、test_r10_graph_source_coverage_pg.py、test_r10_evidence_graph_pg.py + 恢复的 test_r10_graph_runtime_policy_pg.py、test_r10_default_graph_runtime_pg.py。
- real_services（Neo4j/DPAPI）：blocked_live 如实记录。
- 全量对照：C6 终局复跑 failed 只减不增。

本次写作结束时间：2026-10-25T01:20:00+08:00
最后更新时间：2026-10-25T01:20:00+08:00
