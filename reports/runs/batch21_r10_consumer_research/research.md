# 批次21 C5.1 · R10 默认图消费者协调 —— 只读调研报告

- 调研时间：2026-10-24T23:36:15+0800 开始，报告落盘 2026-10-24T23:48:42+0800
- 仓库：D:\dianzi，HEAD `b4407f833`（codex/full-delivery-recovery），工作区仅 batch21 既有报告改动与本目录新增
- 方法：只读 grep/read/git show（含未合并分支与 D:/wt 存活 worktree）；未运行 pytest；未修改任何业务文件

---

## 1. graph_apply 现状

### 1.1 是什么、签名

- `GRAPH_APPLY_JOB_TYPE = "graph_apply"`：backend/src/ai_intel/knowledge/graph_projection.py:52。
- 处理器工厂：`build_graph_apply_handler(store: GraphProjectionStore, authorize: TaskScopeAuthorizer) -> JobHandler`（graph_projection.py:1069-1100）。JobHandler 签名即 `(session, JobExecutionContext, payload: bytes) -> JobExecutionResult`（backend/src/ai_intel/workers/executor.py:77）。payload 只含 `{"batch_id": UUID}`；执行链为 `apply_projection_batch(session, scope, batch_id, store, now)`（graph_projection.py:831-898），失败语义全部映射为 blocked 错误码：`graph_projection_scope_denied` / `graph_projection_digest_conflict` / `graph_projection_capacity_exceeded` / `graph_projection_state_unavailable`（graph_projection.py:1090-1097）。
- 存储端：`Neo4jProjectionStore.apply_batch`（backend/src/ai_intel/infrastructure/neo4j_projection.py:166-249），一个显式事务内做 slot 锁、`projection_apply_decision` 序列判定、写节点/边、提交 marker；`initialize_schema` 是 operator-only 幂等初始化（neo4j_projection.py:155-164）。

### 1.2 谁产生图数据

- 图数据源头是 PG 知识表（events/claims/evidence）经 `EvidenceGraphReadService.event_graph` 产出 `GraphSnapshot`（backend/src/ai_intel/knowledge/evidence_graph.py，规则版本 `GRAPH_RULE_VERSION="r10-graph-1.2.0"`，evidence_graph.py:56）。
- `capture_event_projection`（graph_projection.py:644-793）：RR 候选读 + 锁定 PG 围栏，把 snapshot 编码为不可变 `GraphProjectionBatch` 写入 `graph_projection_batches`，**并在同一事务 enqueue 一个 `graph_apply` job**（graph_projection.py:764-771，idempotency_key=`graph-apply:<batch_id>`；job/outbox 机制见 backend/src/ai_intel/infrastructure/outbox.py:23 `enqueue_job`）。
- 上游清单由 `begin_reconciliation`（graph_projection.py:512-593）在调用者持有的 RR 事务中一次性捕获。
- 当前生产代码中 `capture_event_projection`/`begin_reconciliation` **没有任何生产调用方**，只有测试调用（grep 全仓：backend/tests/integration/test_r10_projection_pg.py 等测试文件）。

### 1.3 "默认无消费者"的具体含义（装配位为空）

- 默认 worker 装配在 backend/src/ai_intel/workers/runtime.py：静态表 `EXECUTION_HANDLERS`（runtime.py:108-115）只有 `record_source_fetch_failure` 和 `SOURCE_JOB_TYPE`；`consume_job`（runtime.py:160-185）按配置追加 enrichment（runtime.py:167-169）、revalidation（runtime.py:170-177）、`build_projection_job_handlers`（retrieval 语义投影，runtime.py:178-179）。
- `build_projection_job_handlers`（backend/src/ai_intel/retrieval/runtime_policy.py:145-188）只注册 `KNOWLEDGE_CHANGE_JOB_TYPE="knowledge_change"`（retrieval/runtime_policy.py:41），与图投影无关（名字撞了，是语料 hybrid 投影）。
- 全仓 grep `graph_apply`：src 内仅 graph_projection.py 自身。**没有任何地方把 `build_graph_apply_handler` 注册进 worker 处理器表。**
- 后果：一旦产生 graph_apply job，worker 认领后在 `execute_job` 的处理器查表落空，走 `JobExecutionError("unsupported_job_type", blocked=True)`（executor.py:120-122）——job 永久 blocked 而不是被消费。这就是交接记录"graph_apply 默认无消费者"（progress/context_handoff.md:43）的准确含义：**缺的是 workers/runtime.py 的处理器注册位，不是缺 handler 实现**。
- 补充事实：graph_apply 的 job 认证 scope 由 `authorize` 回调提供，工厂 docstring 明确"Root-owned worker registration supplies the authenticated task scope provider"（graph_projection.py:1073）——注册位被合同预留给了 Root。

---

## 2. R16 fan-in 边界（为什么不能挪）

- R16 fan-in 实现于 backend/src/ai_intel/revalidation/fan_in.py，模块定位："Owned PG cohorts converge without revising the terminal planning job or assessments"（fan_in.py:1）。`check_fan_in`（fan_in.py:347-363）读取子任务 `revalidate_assessment` 的状态并按 `summarize_dependency_statuses` 收敛四态结论；`guard_completed_fan_in`（fan_in.py:490）在完成 guard 里校验 VerifiedContent 证明。
- 装配方式：`RevalidationFanInManifest` 内嵌在 `RevalidationChangeRequest` payload（revalidation/runtime_policy.py:397-407），由 `make_revalidation_change_handler` 返回的 `DetachedJobHandler` 消费（revalidation/runtime_policy.py:423-424、guard 在 :579-618）；处理器注册于 `make_revalidation_job_handlers`（revalidation/runtime_policy.py:614-623，job 类型 `revalidate_change`/`revalidate_assessment`，:62-63）。
- 不可挪的理由：
  1. **领域不同**：fan-in 收敛的是"重判子评估 receipt"的完成态，依赖 `revalidation_job_bindings`/`assessment_results`（fan_in.py:33,43）；graph_apply 是"PG 不可变批次 → Neo4j 投影"的幂等 ACK 管道（graph_projection.py:855-897 有自己的 receipt/ack/manifest 计数），两者没有共同的依赖表或结论语义。
  2. **合同成本**：把 graph job 塞进 fan-in 必须扩 `RevalidationChangeRequest`/`RevalidationFanInManifest` 公开 DTO 或复用 revalidation 绑定表——前者是公开合同变更，后者制造第二套任务真相，均违反本批约束与 CR-R10。
  3. **既有裁决**：CR-R10_default_graph_runtime.md:15 明文"共享最终 fan-in guard 继续负责各消费者资格，其他消费者缺口仍 partial"、"不得将图派发返回值当成整个知识变更完成"；交接 progress/context_handoff.md:905 "knowledge_change继续partial，不借R16全局签完成"。fan-in 挪用正是被预先排除的路径。
  4. 现状佐证：knowledge_change 混合投影 handler 终态固定返回 `partial` + `error_code="knowledge_change_other_consumers_pending"`（retrieval/runtime_policy.py:136-139）——其他消费者缺口以 partial 表达，不进 fan-in 全局签收。

---

## 3. 默认消费者候选调研

### 3.1 结论性候选：默认 worker 的 graph_apply 处理器注册（推荐）

正常主路径里"消费已应用的图"的第一消费者就是**默认 worker 对 graph_apply job 的消费本身**（把批次应用到 Neo4j），这是 CR-R10 已批准的设计（docs/decisions/CR-R10_default_graph_runtime.md:7 "补齐目前存在但未在默认 worker 注册的 graph_apply"）。下游读侧候选均不满足"本批最小接线"：

- `read_projection_candidates` + `Neo4jProjectionStore.find_candidates`（graph_projection.py:901-1013、neo4j_projection.py:251-299）：为多跳检索（R12）设计的受限候选 ID 读侧，带 PG 有效性围栏；当前仅测试调用，无生产调用方——接线它是 R12 切片，不是 C5.1。
- API 图路由 `build_graph_router`（backend/src/ai_intel/api/graph_routes.py:30-106，装配于 api/app.py:138）：读 PG `EvidenceGraphReadService`，不读 Neo4j 投影——已接线且与投影无关。
- 调查工作流 GRAPH_WRITER 角色（backend/src/ai_intel/investigation/workflow_service.py:1378-1386）：读 PG 图，返回 `graph_projection_adapter_not_configured`——R14 适配切片，非 C5.1。

### 3.2 关键发现：消费者实现已写好且已过审，只差 Root 装配（未合并切片全景）

本仓库本地分支上存在完整、经过独立审查的未合并实现链（`git branch -a` 可见；均不在 HEAD 祖先内，`git merge-base --is-ancestor` 逐一验证为 NO）：

**切片 A（graph policy，基线 f3c2e41e3，分支 codex/r10-graph-policy-fix1）**
- `96cf0732f` "Add bounded PG-authoritative graph consumer policy"：新增 backend/src/ai_intel/knowledge/graph_runtime_policy.py（335 行：`graph_reconcile`/`graph_capture` job 类型、UUID5 generation 绑定 `graph_generation_id(namespace, partition, epochs)`、`build_graph_runtime_policy`）；graph_projection.py +64（公开 `read_projection_scope_epochs`/`read_reconciliation_manifest`、`begin_reconciliation` 预算参数）；直属测试 tests/unit/test_r10_graph_runtime_policy.py（384 行）、tests/integration/test_r10_graph_runtime_policy_pg.py（221 行）。
- `986b01ea2` "Bind runtime graph apply to namespace and immutable generation"：graph_projection.py 增加 `ProjectionBatchGuard` 窄回调（`apply_projection_batch`/`build_graph_apply_handler` 增加关键字参数 `batch_guard`，guard=None 仅保留 server-only 手动恢复兼容）；graph_runtime_policy.py 永远提供 guard，校验 namespace/partition/UUID5 generation（986b 版 graph_runtime_policy.py:326-346，拒绝码 `graph_projection_namespace_denied`/`graph_projection_scope_denied`/`graph_projection_generation_denied` 均 blocked）；新增 tests/unit/test_r10_graph_apply_runtime_scope.py（199 行 9 例）。修复任务报告 reports/tasks/R10-graph-policy-fix1.md（分支内）载明：原独审 counterexample 红→绿、相关 173 case 全 passed、PG/Neo4j 实跑 not_run、状态 awaiting_review。

**切片 B（默认工厂 + 有界 IO，基线 0291d1975，分支 codex/r10-default-consumer-fix1 / codex/r10-default-deadline-review2）**
- `c554eae58` "Compose canonical durable graph dispatch with default hybrid worker"：新增 backend/src/ai_intel/knowledge/default_graph_runtime.py（225 行）。核心 `build_default_graph_job_handlers(engine, settings)`（c554 版 :186-225）：内部包裹 `build_projection_job_handlers`，配置了 neo4j 时组合 `_knowledge_change_handler`（两阶段 detached：第一 PG 事务验证 canonical 租约/payload/scope 并幂等登记 graph reconciliation jobs，第二事务复核租约后调原 hybrid handler，:160-183）并注册 `graph_reconcile`/`graph_capture`/`graph_apply` 三个 job 类型；未配置时 store=None，三类型经 `build_graph_runtime_policy(engine, None, ...)` 全部映射为 `graph_projection_not_configured` blocked（986b 版 graph_runtime_policy.py:150-160），**无静默成功**。直属测试 tests/unit/test_r10_default_graph_runtime.py（345 行）、tests/contract/test_r10_default_graph_bolt_io_contract.py（203 行）、tests/integration/test_r10_default_graph_runtime_pg.py（211 行）。
- `2f4e83dcf` "fix(knowledge): bound default graph client IO and DNS teardown"：neo4j_projection.py +456（官方 AsyncDriver + 同线程标准库 Runner 桥 `_AsyncSessionBridge`、单固定 stdlib 子进程 DNS 解析、thread-ownership close），default_graph_runtime.py 改用 `AsyncGraphDatabase` + `connection_write_timeout` + `dns_origin`。对应 CR-R10 addendum（13:02:29 节，docs/decisions/CR-R10_default_graph_runtime.md:32-38）。
- `e8df2b02d`（style）、`af4984b8f`（证据封存）。
- 独立复核：reports/reviews/recovery/G-C-R10-default-graph-deadline-review-2.md（分支 codex/r10-default-deadline-review2，commit e69a52688）结论"旧 M01、M02 在本次固定新源独立复验中关闭；本范围没有新增已确认缺陷"；同时明确"本树 workers/runtime.py:178 仍调用旧 build_projection_job_handlers；**这是 Root 持有的公开接线任务**。准备中的两处替换是 Root 后续 diff，不是已挂载结果"。
- 过时的中间装配（不要恢复）：切片 A 的 `73634f30f` 曾在 runtime.py 接 `infrastructure/graph_projection_factory.py`（同步 driver），被 c554 的 default_graph_runtime 设计取代（review2 采用的是 default_graph_runtime + 四个 986b blob overlay）；其直属测试也被切片 B 的测试覆盖。

**依赖与冲突实测**：c554 的 default_graph_runtime.py 依赖切片 A 的 graph_runtime_policy 与 graph_projection 扩展（import 见 c554 版 :10-15、:33-40）；两个基线（f3c2e41e3、0291d1975）均为 HEAD 祖先，且 `git diff <base> HEAD --` 对切片触碰的 src 文件（graph_projection.py / neo4j_projection.py / workers/runtime.py / retrieval/runtime_policy.py / settings.py）**全部为空 diff**——cherry-pick 恢复预计零 src 冲突（实施时须重新验证）。
- 配置面已就绪：`neo4j_uri/username/password` 已在 backend/src/ai_intel/infrastructure/settings.py:47-49，校验 :78-113（三者齐全、bolt(s) origin、明文仅 APP_ENV=test）；驱动依赖 `neo4j==6.4.0` 已在 backend/pyproject.toml:26；配置直属测试 backend/tests/unit/test_r10_graph_runtime_settings.py 已在树。

### 3.3 其他"写好未接线"类（不属于 C5.1 默认消费者）

- `Neo4jProjectionStore` 本体已在树（neo4j_projection.py:126）但 src 内零调用方——正是等待上述工厂接线。
- `build_graph_apply_handler` 已在树（graph_projection.py:1069）但零调用方。
- 未合并分支之外，D:/wt 下存活 worktree（r10-default-worker-graph、r10-default-consumer-fix1、r10-default-deadline-review2 等 20+ 个）与上述分支一一对应，仅作取证，不作为实现来源。

---

## 4. r10 既有直属测试与可模仿模式

### 4.1 在树测试清单（def test_ 计数）

| 文件 | 数量 | 说明 |
|---|---|---|
| backend/tests/unit/test_r10_graph_runtime_settings.py | 6 | 图配置校验（在树，已绿） |
| backend/tests/unit/test_r10_projection_batches.py | 5 | 批次 DTO |
| backend/tests/unit/test_r10_projection_fix1_epochs.py | 2 | epoch 失效 |
| backend/tests/unit/test_r10_evidence_graph.py | 3 | 图读服务 |
| backend/tests/unit/test_r10_relation_polarity.py | 3 | 关系极性 |
| backend/tests/contract/test_r10_graph_contract.py / test_r10_projection_contract.py | 1 / 6 | DTO/尺寸合同 |
| backend/tests/security/test_r10_graph_boundary.py / test_r10_projection_scope.py | 2 / 3 | 边界/租户隔离 |
| backend/tests/integration/test_r10_evidence_graph_pg.py | 10 | real_pg |
| backend/tests/integration/test_r10_graph_fix2_pg.py | 4 | real_pg |
| backend/tests/integration/test_r10_graph_source_coverage_pg.py | 1 | real_pg |
| backend/tests/integration/test_r10_graph_validity_pg.py | 11 | real_pg |
| backend/tests/integration/test_r10_projection_pg.py | 13 | real_pg；含 graph_apply blocked 语义 |
| backend/tests/integration/test_r10_projection_fix2_empty_reads.py | 2 | real_pg |
| backend/tests/integration/test_r10_neo4j_projection.py | 7 | real_pg+real_services（DPAPI 资源 D:/dianzi-private/r10-neo4j-test-20261016.dpapi，缺资源时 `pytest.UsageError("blocked: ...")`，test 文件 :47-89） |
| backend/tests/integration/test_r10_projection_fix1_markers.py | 3 | real_services |

### 4.2 需随切片恢复的测试（分支内）

- tests/unit/test_r10_graph_runtime_policy.py（96cf）、tests/unit/test_r10_graph_apply_runtime_scope.py（986b，9 例 guard 语义）、tests/integration/test_r10_graph_runtime_policy_pg.py（96cf，986b 仅补一处 `now` 参数）。
- tests/unit/test_r10_default_graph_runtime.py、tests/contract/test_r10_default_graph_bolt_io_contract.py、tests/unit/test_r10_default_graph_io_deadline.py、tests/unit/test_r10_default_graph_dns_deadline.py（c554/2f4e83dcf）、tests/integration/test_r10_default_graph_runtime_pg.py。

### 4.3 可模仿的测试模式

1. **默认装配注册测试（C5.1 直属测试的直接模板）**：backend/tests/unit/test_r16_default_worker_registration.py:13-77——env 隔离 + `ApplicationSettings` 配置/未配置双参数化 + monkeypatch runtime 依赖 + 假 `execute_job` 捕获 handlers 字典 + 断言"配置才注册、未配置不注册、引擎 dispose、SOURCE handler 原样"。C5.1 需要的正是它的 graph 版：断言 `GRAPH_APPLY_JOB_TYPE`（及 graph_reconcile/graph_capture、组合后的 knowledge_change）注册/未注册。
2. **graph_apply 执行语义测试**：test_r10_projection_pg.py:440-486——`build_graph_apply_handler(SyntheticGraphStore(), authorize)` + `execute_job(engine, job_id, worker, {GRAPH_APPLY_JOB_TYPE: handler})`，断言 blocked 与 `error_code`、ack 计数不变；SyntheticGraphStore 显式非 Neo4j fixture（:91-113，"Explicit non-Neo4j fixture"）。
3. **真实资源围栏**：test_r10_neo4j_projection.py:47-89——DPAPI 私有资源 + 身份/ deadline 校验 + `pytest.UsageError("blocked: ...")`（不伪装 live）。
4. **无 IO 离线装配**：切片 B 的 test_r10_default_graph_runtime.py 走 MagicMock driver，"mocked drivers are never live evidence"。

---

## 5. 实现方案（供 CR 冻结与后续实现卡使用）

### 5.1 CR 合同要点（新建 docs/decisions/CR-R10_default_graph_consumer_batch21.md，命名沿用 `*_batch21` 先例；不修改 Root 的 CR-R10_default_graph_runtime.md）

1. **默认消费者是谁**：默认 Celery worker（workers/runtime.py `consume_job`）在配置了 NEO4J_URI/USERNAME/PASSWORD（settings.py:47-49，校验 :78-113）时，通过 `ai_intel.knowledge.default_graph_runtime.build_default_graph_job_handlers` 注册三类图 job 消费者：`graph_apply`（核心，`build_graph_apply_handler` + 永久 guard 的 `Neo4jProjectionStore`）、`graph_reconcile`、`graph_capture`，并组合 `knowledge_change`（图派发 + 原 hybrid 两阶段）。未配置时仍注册三类型，全部显式 `graph_projection_not_configured` blocked；非图 job 构造不接触 Neo4j（driver 构造无网络 IO，schema IO 仅发生在真实 apply 内，c554 版 default_graph_runtime.py:81-83,186-188）。
2. **触发条件**：`capture_event_projection` 同事务 enqueue 的 graph_apply job（graph_projection.py:764-771）经 PG outbox/beat 投递（runtime.py:132-157）后被默认 worker 认领执行；generation 必须等于 UUID5(namespace, partition, epochs, rule)（graph_runtime_policy.py:49-52），guard 在已验证不可变 batch 后、store/ACK 前同 Session 校验（986b graph_projection.py apply 路径）。
3. **失败语义**：scope/payload/generation/namespace 不符 → blocked（`graph_projection_scope_denied`/`graph_projection_namespace_denied`/`graph_projection_generation_denied`）；digest/capacity/state → blocked（graph_projection.py:1090-1097）；Neo4j DriverError/Neo4jError → `graph_projection_unavailable`，PG 回滚只产生安全重放（"Neo4j commits first; caller PG rollback can only cause safe immutable replay"，graph_projection.py:838）；重试沿既有 job 租约/max_attempts 层（workers/jobs.py），不新增重试层。knowledge_change 图派发不顶替父任务终态，返回仍 partial（`knowledge_change_other_consumers_pending`），不借 R16 fan-in 全局签收。
4. **权限**：scope 由服务端 canonical PG 租约行派生（require_job_lease + job_type/tenant 校验 + payload digest 复核，c554 default_graph_runtime.py:60-118），最小 READ_PUBLIC（public）或 READ_PUBLIC+READ_ASSET（tenant），拒绝 payload 自报身份。
5. **不动的部分**：不挪 R16 fan-in（第 2 节）；不改公开 API/DTO/schema/迁移；不放宽既有断言；金标/分母/评分不变。

### 5.2 最小实现路径

1. **CR 落盘**（前置）：docs/decisions/CR-R10_default_graph_consumer_batch21.md，内容=5.1。
2. **恢复已审切片**（cherry-pick，基线均为 HEAD 祖先且 src 零漂移）：
   - 切片 A：`96cf0732f` + `986b01ea2`（跳过 `73634f30f`——其 runtime.py 装配与 factory 被切片 B 取代）。
   - 切片 B：`c554eae58` + `2f4e83dcf` + `e8df2b02d`（af4984b8f 为证据封存，按 batch21 归档惯例另行处理）。
3. **Root 装配（本批唯一新生产改动）**：backend/src/ai_intel/workers/runtime.py——import `build_default_graph_job_handlers`；`consume_job` 中将 `with build_projection_job_handlers(engine, settings) as projection_handlers: handlers.update(projection_handlers)`（runtime.py:178-179）替换为 `with build_default_graph_job_handlers(engine, settings) as graph_handlers: handlers.update(graph_handlers)`（即 review2 所述"两处替换"）。
4. **直属测试（新增）**：backend/tests/unit/test_r10_default_worker_registration.py——按 4.3-1 模板：配置/未配置双参数化断言 graph_apply/graph_reconcile/graph_capture 注册与否、未配置时 knowledge_change 保持纯 hybrid、driver close、SOURCE/enrichment/revalidation 不受影响。
5. **既有测试适配（CR 内登记，非放宽）**：backend/tests/unit/test_r16_default_worker_registration.py:64 的 `monkeypatch.setattr(runtime, "build_projection_job_handlers", ...)` 在装配点替换后失效，需把 patch 目标改指 `ai_intel.knowledge.default_graph_runtime.build_projection_job_handlers`（hybrid provider 仍由该模块调用，c554 版 :186），**全部断言原样保留**。先例：batch21 C3.3 head 期望更新走 CR-migration_head_oracle_alignment_batch21.md。
6. **r10 回归**：离线组=unit（r10 全部 + 新增两个 unit）+ contract（r10 两文件 + bolt_io_contract）+ security；real_pg 组=4.1 表中 integration real_pg 文件 + 恢复的 test_r10_graph_runtime_policy_pg.py + test_r10_default_graph_runtime_pg.py；real_services（Neo4j）组=test_r10_neo4j_projection.py、test_r10_projection_fix1_markers.py——无 Neo4j 资源时按既有 fixture 语义记 blocked_live/not_run，不伪装通过。

### 5.3 风险与停止信号

- **风险 1**：cherry-pick 时 src 漂移（当前实测为零，实施前须以同一 `git diff <base> HEAD -- <files>` 复验；HEAD 变化后需重跑）。切片 A 的 graph_projection.py 含 `begin_reconciliation` max_events 预算与公开 read_* 助手，属共享模块改动——已获 Root 批准（R10-graph-policy-fix1.md"Root 已明确批准保留这个 server-only 手动恢复兼容边界"），CR 里引用即可，不再重新裁决。
- **风险 2**：切片 B 的 DNS/async 桥（neo4j_projection.py +456）是全部调用方共享路径，恢复后所有 `Neo4jProjectionStore` 调用方须回归（CR addendum 要求），real_pg 集成组即覆盖。
- **风险 3**：review2 明确未跑真实 PG/Neo4j 默认 worker 路径（not_run）——本批若能提供 Neo4j 资源则补真实路径，否则显式记 blocked_live，不得把离线 137/173 通过写成 live 达标。
- **停止信号（发现即停，转变更单/上报）**：
  1. 恢复切片时 graph_projection.py/neo4j_projection.py 出现语义冲突（非纯文本冲突），需要改已冻结的 986b guard 语义或 review2 关闭的 M01/M02 断言；
  2. 装配点替换要求改 `build_projection_job_handlers` 的公开行为或 test_r12_default_projection_runtime.py / test_r12_projection_failure_budget.py 的断言（说明装配越出了"两处替换"范围）；
  3. 任何改动波及公开 API DTO、schema/迁移、`RevalidationChangeRequest`/fan-in 合同，或需要对 `workers/jobs.py` 重试层新增语义——这些都是本批约束明确排除的公共合同变更；
  4. 发现 c554/2f4e83dcf 与当前 HEAD 的 execute_job/enrichment/revalidation 装配交互产生非预期 blocked（例如 test_r14_preclaim_recovery.py:66-69 的 `delivery_unavailable` 路径被 graph 工厂异常打断——当前判定不会发生，因未配置时工厂无网络 IO，但实施时必须以该测试实测确认）。

---

## 6. 事实来源索引

- progress/context_handoff.md:43（graph_apply 默认无消费者、不挪 R16）、:195（defaulthandler 待办）、:905/:920/:935/:949/:1008/:1010（R10 默认 worker/policy/factory 各切片审查与资源状态）
- docs/decisions/CR-R10_default_graph_runtime.md:1-38（已批准合同 + 13:02:29 addendum）
- 未合并分支：codex/r10-graph-policy-fix1（96cf0732f、73634f30f、986b01ea2、b254ba317）、codex/r10-default-consumer-fix1（c554eae58、2f4e83dcf、e8df2b02d、af4984b8f）、codex/r10-default-deadline-review2（e69a52688 含 review 报告）
- 报告：reports/tasks/R10-graph-policy-fix1.md（分支内）、reports/reviews/recovery/G-C-R10-default-graph-deadline-review-2.md（分支内）
- 在树代码行号均以 HEAD b4407f833 为准；分支内代码行号以对应 commit 为准（文中已注明 commit）。
