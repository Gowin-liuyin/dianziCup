# Root-batch21 C5.2 公开 producer 完整性盘点

- 文档首次创建时间：2026-10-24T23:36:15+0800（`date +%Y-%m-%dT%H:%M:%S%z` 真实输出）
- 最后更新时间：2026-10-24T23:44:01+0800（`date +%Y-%m-%dT%H:%M:%S%z` 真实输出）
- 性质：只读代码盘点。未运行 pytest，未修改除本文件外任何文件，未执行任何改变 git 状态的操作。
- 盘点时 git 状态（事实记录）：HEAD `b4407f833`（checkpoint: batch21 C2 prep）；工作区已有他人未提交修改（`progress/OPEN_QUESTIONS.md`、`progress/goal_state.json`、`reports/runs/batch21_*`、`scripts/dev_integration_container.py` 等），本盘点未触碰。

## 0. 方法与路由清单一致性基准

四组公开面的实际挂载集合，与以下三层事实相互核对：

1. **挂载代码**：`backend/src/ai_intel/api/app.py`
   - `app.py:182-189` 把 `build_public_extension_router(engine, configuration.data_mode, source_polling_enabled=configuration.source_polling_enabled)` 挂到 `prefix="/api/v1"`，承载 `GET /vulns`、`GET /vulns/{event_id}`、`GET /sources`、`GET /tasks/{task_id}` 四条。
   - `app.py:190` 把 `build_public_ask_router(...)` 挂到 `prefix="/api/v1"`，承载 `POST /ask`。
   - 五条公开路由都**只挂 `/api/v1`**，不挂 `/v1`（与 README「只挂在 /api/v1 的公开读取」一致）。
2. **路由清单一致性测试**：`backend/tests/contract/test_route_inventory.py:168-181`（`test_readme_route_table_matches_mounted_application_routes`）从 `create_application()` 递归枚举全部 (path, method)，与 README「## 已挂载的路由」（`README.md:44-63`）做精确集合相等断言，双向报漂移。`README.md:63` 明列五条：`GET /vulns`，`GET /vulns/{event_id}`，`GET /sources`，`GET /tasks/{task_id}`，`POST /ask`。该测试最近一次记录在案的通过证据是 `progress/context_handoff.md:1033`（「路由清单合同测试1 passed（README补录15条路径，(path,method)粒度）」）；`reports/runs/` 的 batch21 门禁日志（batch21_quality_gates/、batch21_red_zero/、batch21_integration_unlocked/）中没有该测试的单独运行记录，本盘点未复跑。
3. **公开面冻结契约测试**：
   - `backend/tests/contract/test_r18_public_producer_contract.py:13-30`：扩展路由恰好是冻结 SDK 四条 GET（多一条少一条都失败），并对照 `contracts/schemas/public_api_extensions_v1.json` 的 `VulnerabilityDetailPage`/`SourcePage` 必填集；`:42-56` 断言未配置工厂（engine=None）返回 503 `not_configured` 的 RFC9457 problem 形状。
   - `backend/tests/contract/test_r18_default_public_read_mount.py:12-24`：默认 App 下四条 GET 匿名一律 401 `unauthenticated` + `Cache-Control: no-store`；`:27-40` 断言 openapi 中四条 GET 与 `POST /v1/sources/{source_kind}/collect` 在场。

核对结论：挂载集合、README 路由表、冻结契约测试三者一致，没有幽灵路由（挂了未记录）也没有幽灵文档（记了未挂）。本盘点的甄别重点是**路由背后的 producer 是否在默认装配里真实接线**。

---

## 1. `/vulns`（公开漏洞面）—— `GET /api/v1/vulns`、`GET /api/v1/vulns/{event_id}`

### 挂载点
- `backend/src/ai_intel/api/public_extension_routes.py:140-146`：`@router.get("/vulns")` → `search_vulns`；
- `backend/src/ai_intel/api/public_extension_routes.py:148-155`：`@router.get("/vulns/{event_id}")` → `get_vuln`；
- 经 `app.py:182-189` 挂到 `/api/v1`。

### producer 链
路由处理函数 → `serve()`（`public_extension_routes.py:87-138`）在请求事务内构造 `PublicExtensionReadService(session, scope, data_mode, source_polling_enabled)`（`public_extension_routes.py:106-108`）→ `search_vulns`（`public_extension_reads.py:523-574`）/ `get_vuln`（`:576-635`）→ 组合两个既有读服务：`KnowledgeReadService` 与 `EvidenceGraphReadService`（`public_extension_reads.py:158-159`）。详情页再走 `knowledge.event_detail`、`graph.event_graph`（`public_extension_reads.py:275-280`），维度支持复核走 claims/claim_assertions/claim_evidence/evidence/text_blocks 联查（`:367-438`）。

### 装配状态
- `app.py:58`：`engine = build_engine(configuration) if configuration.database_url else None`；`app.py:182-189` 把 engine 与 `configuration.data_mode`、`configuration.source_polling_enabled`（`settings.py:73`，默认 `False`）直接传入工厂。producer 在默认装配中被真实实例化（每请求一次，类与构造参数全部接线）。
- engine 为 None（无 database_url）时 `serve()` 显式抛 `PublicReadUnavailable("public database producer is not configured")` → 503 `not_configured`（`public_extension_routes.py:97-98`），被 `test_r18_public_producer_contract.py:42-56` 钉住——是显式声明，不是静默缺 producer。

### 鉴权与数据来源
- 鉴权：匿名 401（`public_extension_routes.py:121-122`；`test_r18_default_public_read_mount.py:12-24` 钉住）。API key 走 `consume_api_key_rate_limit` 限流（`:101-102`），会话走 `lock_authenticated_principal`；两者都 `scope.requires(READ_PUBLIC)`（`:105`；`domain/access.py:20` 定义，四角色均有）。租户模型：投影强制 `visibility == "public"` 且 `tenant_id IS NULL`（如 `public_extension_reads.py:530`、`:207-213`），即任何持 READ_PUBLIC 的已认证主体读到同一份全局公开集；`CrossTenantAccessError` → 404（`:129-130`）。响应前同事务复读比对摘要（`:110-119`）。
- 数据来源（PostgreSQL）：`events`、`event_external_ids`（搜索，`:530-539`）；`event_documents`/`document_revisions`/`documents`/`sources`（当前规范化情报，`:185-229`）；`evidence`（引文，`:231-266`）；`claims`/`claim_evidence`/`claim_assertions`/`text_blocks`（维度支持复核，`:367-438`）；`scope_epochs`（游标绑定，`:162-168`）。全部为知识库既有表，无独立第二真相。

### 结论分类：**已完整接线**
路由、producer、默认装配、鉴权、数据来源五环齐备，且有默认 App 级 401/503 契约测试钉住。无缺口。

---

## 2. `/sources`（公开来源面）—— `GET /api/v1/sources`

### 挂载点
- `backend/src/ai_intel/api/public_extension_routes.py:157-163`：`@router.get("/sources")` → `list_sources`；经 `app.py:182-189` 挂到 `/api/v1`。
- 注意区分：内部采集面 `POST /sources/{source_kind}/collect`（`backend/src/ai_intel/api/source_routes.py:145-159`）经 `app.py:135`（`include_job_reader=False`）挂到 `/v1`（`app.py:160`）与 `/api/v1`（`app.py:173`），**不属于公开读取面**——它走会话 Cookie + CSRF 的管理员调度（`source_routes.py:77`「管理员调度固定公开来源」），入队 `enqueue_source_page`（`:170-176`）。

### producer 链
同一 `PublicExtensionReadService`（`public_extension_routes.py:106-108`）→ `list_sources`（`public_extension_reads.py:637-771`）：来源标识来自 `sources` 表（仅 `visibility == "public"` 且 `tenant_id IS NULL`，`:642-645`）；健康度由真实观测推导 `derive_source_health`（`:125-133`），输入为 `source_response_receipts`、`fetch_attempts`、`source_page_receipts` 三张收据表的最近观测（`:665-745`）；`enabled` 字段 = `source_polling_enabled and source_id in CATALOG_SOURCES`（`:751`，目录来自 `ai_intel/ingestion/source_catalog.py`）；存储修订模式经 `classify_revision_mode` 复核（`:653-664`、`:773-799`）。

### 装配状态
与 `/vulns` 完全同链：`app.py:182-189` 真实传入 engine + data_mode + source_polling_enabled；engine 缺失时同一 503 `not_configured` 显式路径。producer 已实例化、无 None 注入。

### 鉴权与数据来源
- 鉴权：与 `/vulns` 同（匿名 401、API key 限流、READ_PUBLIC、全局公开集、跨租户 404）。
- 数据来源：`sources` + 三张采集收据表 + 源目录常量。默认 `source_polling_enabled=False`（`settings.py:73`）时 `enabled` 恒为 false——这是配置语义（自动轮询关闭，README 断点 6「自动轮询关闭」），不是接线缺口；健康/最后成功时间仍来自真实收据。

### 结论分类：**已完整接线**
无缺口。`enabled=false` 是声明的配置态，producer 本身真实接线。

---

## 3. `/tasks`（公开任务面）—— `GET /api/v1/tasks/{task_id}`

### 挂载点
- `backend/src/ai_intel/api/public_extension_routes.py:165-173`：`@router.get("/tasks/{task_id}")` → `get_task_result`；经 `app.py:182-189` 挂到 `/api/v1`。
- 契约侧：`contracts/schemas/public_api_extensions_v1.json` 的 `TaskDescriptor`（task_type 枚举 ask/stack_check，poll_uri 固定 `/api/v1/tasks/<uuid>`）与 `TaskResultEnvelope`（task/result/error/completed_steps/pending_steps/failed_steps）。

### producer 链
路由 → `reader.get_task_result(identifier)`（`public_extension_routes.py:173`）→ `PublicExtensionReadService.get_task_result`（`backend/src/ai_intel/api/public_extension_reads.py:801-805`）——**无条件抛出**：

```python
def get_task_result(self, task_id: UUID) -> dict[str, JsonValue]:
    """Generic jobs cannot establish an ask/stack request type, owner and result contract."""
    raise PublicReadUnavailable(
        "public task owner and typed result producer are not configured"
    )
```

即 `GET /api/v1/tasks/{任何uuid}` 恒为 503 `not_configured`。

**关键甄别（模式 b：producer 类存在但从未在默认装配中实例化）**：真正按冻结契约写好的 typed task producer 已经存在——`backend/src/ai_intel/api/public_task_bindings.py`：
- `PublicTaskBindingService`（`:265`）+ `read_in_session`（`:594-647`）：在调用方事务内锁 `job_runs` + `public_task_bindings` + `investigation_workflows`，投影九状态联合、步骤收据与已发布 QA 结果，输出恰为冻结 `TaskResultEnvelope` 形状（`:631-647`）。
- 写侧 `bind_in_session`（`:421-491`，受理时原子绑定）与 `publish_result_in_session`（`:539-592`，租约下 CAS 发布结果定位符）。
- `stack_check` 明确拒绝：`UnsupportedPublicTaskError`（`:145-146`「No actual owned stack async producer has been frozen and installed」、`:433-434`、`:387-388`）。
- 该模块**在 `backend/src/` 内零导入者**（全仓 grep 仅文件自身）；`bind_in_session`/`publish_result_in_session`/`read_in_session` 的调用全部在测试里（`tests/contract/test_r18_public_task_binding_contract.py`、`tests/integration/test_r18_public_task_binding_pg.py:134,358,427,477,526`、`tests/security/test_r18_public_task_binding_security.py`）。
- `app.py` 默认装配从未实例化 `PublicTaskBindingService`；`get_task_result` 也未委托它。

### 装配状态（app.py 引用）
`app.py:182-189` 只装配了 engine/data_mode/source_polling_enabled 三项；没有 `PublicTaskBindingService` 的实例化，没有 `PublicTaskResultReader` 适配器，也没有把凭据/actor 传入读服务以支撑 `read_in_session(session, task_id=..., actor=...)` 所需的 `ActorReference`。**装配链在 producer 一环断裂**。

### 鉴权与数据来源
- 鉴权：路由层与 `/vulns` 同（匿名 401、READ_PUBLIC）。设计中的任务归属校验在 `_lock_job`/`_owner_matches`（`public_task_bindings.py:336-369`：tenant_id 与 owner_user_id/actor 绑定不符一律 `CrossTenantAccessError` → 404），与 README「租户会话看不到不属于自己的来源任务」的语义一致——但当前因 503 桩先于鉴权后返回，所有权语义未在默认 App 上生效。
- 数据来源（设计）：`job_runs`（状态权威）+ `public_task_bindings`（不可变触发器保护，`:106-120`）+ `investigation_workflows`/`investigation_operations`（步骤收据）+ 已发布 `grounded_answers`（经 `PublicTaskResultReader.read_qa_answer_in_session` 固定端口）。
- 当前 503 桩被冻结测试钉住：`tests/integration/test_r18_public_read_producer_pg.py:250`（`test_task_without_typed_owner_is_not_configured_and_no_secret_reflection`）。改动它属于合同变更，不是静默补线。
- 前端不消费该路由：`frontend/src/features/tasks/task-workspace.tsx` 查询的是来源/富化任务与调查任务的内部接口（README「#tasks 按输入的任务标识读取已有收据」），公开任务面目前只有 SDK 契约消费者。

### 结论分类：**需要新 producer（入 OQ）**
这不是「当场补一根线」能闭环的：
1. 读侧把 `get_task_result` 委托给 `PublicTaskBindingService.read_in_session` 技术上可行（见下），但**写侧没有任何生产路径会创建 `public_task_bindings` 行**——`bind_in_session` 在 src 中零调用方；`POST /ask` 走的是同步 `GroundedQuestionService.ask`（见第 4 节），从不入队 `job_runs`（job_type='investigation'），也不写绑定。接线后任何 task_id 都只会从 503 变为 404，任务面依旧空转。
2. 端到端闭环需要新的 admission/publish producer：ask（以及未来的 stack_check）受理时入队 typed job + `bind_in_session`，worker 完成时 `publish_result_in_session`，再接 `read_in_session`。这与交接记录一致的未闭项（`progress/context_handoff.md:909`「typedtask503/ask-stack发布/HTTPMCP/OAuth/三类插件仍未闭」、`:37`「Root还未装配公开producer/typed task/ask/stack…整R18partial」）。
3. 读侧最小接线方案（若走变更单解冻 503 桩，可作为 OQ 内第一小步，非本轮授权范围）：
   - 改 `backend/src/ai_intel/api/public_extension_reads.py`：`PublicExtensionReadService.__init__` 增加可选 `task_binding_service`/凭据参数；`get_task_result` 改为构造 `ActorReference`（复用 `api/actor_references.py:213` `create_actor_reference`）后委托 `read_in_session`。
   - 改 `backend/src/ai_intel/api/public_extension_routes.py`：`serve()` 把已解析 credential 传入 reader 构造。
   - 新增 `PublicTaskResultReader` 实现：以 `answering/service.py` 的 `read_grounded_answer` 为后端实现 `read_qa_answer_in_session` 固定端口（同事务、只读、不产生配额）。
   - 测试：解冻 `test_r18_public_read_producer_pg.py:250`（503→404 语义变更需变更单），新增「绑定存在的 task 可投影、他人 task 404、未发布结果不得伪造 completed」三条 PG 用例。
   - 上述仅定义缺口与方案；本盘点不实施。

---

## 4. `/ask`（公开问答面）—— `POST /api/v1/ask`

### 挂载点
- `backend/src/ai_intel/api/public_ask_routes.py:187-204`：`@router.post("/ask", response_model=QuestionAnswerResponse, openapi_extra=...)`（处理器 `ask_question` `:205-249`）；经 `app.py:190` 挂到 `/api/v1`（不挂 `/v1`）。

### producer 链
路由 → `serve()`（`public_ask_routes.py:123-185`）→ `GroundedQuestionService.ask`（`backend/src/ai_intel/answering/service.py:309` 起）：
- 请求合同：`schemas/public_ask_request_v1.json` 打包资源（`:117-121`）+ `parse_public_ask_request`（`api/public_write_adapters.py`，1MiB 上限 `:222-227`）；
- 身份：`create_actor_reference`（`public_ask_routes.py:160`；`api/actor_references.py:213`）在同事务冻结 actor；
- 检索/生成：`EventEvidenceRetriever(engine, models, data_mode=...)` + `GenerationClient`（`api/question_routes.py:46-53`），语义模型 `LocalSemanticModels`；
- 持久化与幂等：`grounded_answers`（uuid5 幂等键，`service.py:342-345`，冲突 409 `:357-358`）；API key 的 ask 配额在事务内 `consume_api_key_rate_limit(operation="ask")`（`service.py:409-413`）；保留/租约 `ANSWER_RESERVATION_SECONDS=420`（`service.py:74`）。

### 装配状态（含模式 (a) 甄别：producer 为 None 的情况）
- `app.py:140`：`questions = question_routes.build_question_service(engine, configuration)`——默认装配在启动时**真实实例化** producer；
- `app.py:144-146`：`public_ask_router = build_public_ask_router(lambda: service, engine, configuration, questions_provider=lambda: questions)`——接线完成；
- `build_question_service`（`question_routes.py:37-59`）在 `engine is None` 或 `generation_api_key is None` 或 `semantic_model_cache_directory is None` 时返回 None（`:40-45`；三个设置项默认均为 None，`settings.py:41,66,68`）。此时运行期 `serve()` 显式抛 `QuestionFailure("question_models_not_configured")` → 503（`public_ask_routes.py:161-162`），被 `tests/unit/test_public_ask_routes.py:301` 与 `tests/integration/test_r05_question_api_pg.py:436` 钉住。
- 甄别结论：这属于**配置驱动的显式降级**（缺付费生成模型凭据/本地模型缓存时明确 503，不冒充在线），不是路由与 producer 之间的接线断裂。按工作区约定应记 `blocked_live`，不构成接线缺口。

### 鉴权与数据来源
- 鉴权：匿名 401（`public_ask_routes.py:74-78`、`:207-209`）；会话凭据额外强制 CSRF 头 + Origin 校验（`:132-145`，`authentication.validate_write_request`）；API key 走 ask 配额限流（`service.py:409-413`）；`scope.requires(READ_PUBLIC)`（`:152-153`、`:158-159`；`service.py:321`）。请求体自报身份被拒：`record_rejected_identity_fields`（`:229-231`）+ `parse_public_ask_request` 剥离权威字段（`tests/contract/test_public_ask_route_contracts.py:59` 钉住）。
- 数据来源：问答范围锁定单事件公开证据（`service.py:328-336`：多事件/带资产/带会话/带时间/mode=investigate 一律 422 `question_scope_not_supported`）；证据检索走 PG 公开证据（EventEvidenceRetriever），答案与模型轨迹落 `grounded_answers`；PG 为唯一权威，无第二真相。
- PG 生命周期测试：`tests/integration/test_public_ask_route_pg.py`（重放共享答案与配额、配额失败回滚、双主同键隔离、证据变更复检等 10 项）。

### 结论分类：**已完整接线**（条件装配；无模型凭据环境为 blocked_live，非接线缺口）

---

## 5. 汇总

### 四组结论一览

| 路由组 | 挂载点 | producer | 默认装配 | 结论 |
|---|---|---|---|---|
| `GET /vulns`、`GET /vulns/{event_id}` | `public_extension_routes.py:140,148` ← `app.py:182-189` | `PublicExtensionReadService.search_vulns/get_vuln` + `KnowledgeReadService`/`EvidenceGraphReadService` | 真实接线（`app.py:58,182-189`） | **完整接线** |
| `GET /sources` | `public_extension_routes.py:157` ← `app.py:182-189` | `PublicExtensionReadService.list_sources`（sources + 三张采集收据表 + CATALOG_SOURCES） | 真实接线（同上） | **完整接线**（enabled=false 为声明配置态） |
| `GET /tasks/{task_id}` | `public_extension_routes.py:165` ← `app.py:182-189` | 桩 `get_task_result` 恒 503（`public_extension_reads.py:801-805`）；真实 producer `PublicTaskBindingService.read_in_session`（`public_task_bindings.py:594`）存在但 src 零装配、写侧零调用方 | **未接线**（`app.py` 无任何 `PublicTaskBindingService` 装配） | **需要新 producer（入 OQ）** |
| `POST /ask` | `public_ask_routes.py:187` ← `app.py:190` | `GroundedQuestionService`（`app.py:140,144-146` 经 `build_question_service`） | 真实接线；无模型凭据时显式 503 `question_models_not_configured` | **完整接线**（缺凭据环境记 blocked_live） |

### 当场可补的接线缺口清单
**0 项。** 三条已挂公开读取面（/vulns、/sources、/ask）的 producer 均在默认装配中真实实例化并经契约/集成测试钉住；唯一未接的 /tasks 不是纯接线问题（见下），不符合「当场可补」的定义。

### 需要新 producer 的清单（入 OQ）
1. **公开 typed task 面端到端 producer**（`GET /api/v1/tasks/{task_id}`）：
   - 缺口：(a) `PublicTaskBindingService` 及其 `bind_in_session`/`publish_result_in_session` 在生产代码中无任何调用方，`public_task_bindings` 表永远为空；(b) `POST /ask` 是同步问答，不存在 ask→typed job（job_type='investigation'）的入队与绑定受理路径；(c) `PublicTaskResultReader` 固定端口无生产实现；(d) 503 桩被 `test_r18_public_read_producer_pg.py:250` 冻结，语义变更（503→404/真实投影）需变更单。
   - 所需新工作：ask 受理入队 + `bind_in_session` 受理绑定、worker 完成路径接 `publish_result_in_session`、`read_grounded_answer` 后端的 result reader、`get_task_result` 读侧委托与测试解冻。stack_check 按冻结契约仍显式 unsupported（`public_task_bindings.py:145-146`），不随本项闭。
   - 对应历史未闭项：`progress/context_handoff.md:37`（「Root还未装配公开producer/typed task/ask/stack…」）、`:909`（「typedtask503/ask-stack发布…仍未闭」）。

### 相邻观察（不在四组范围，供后续批次参考）
- `backend/src/ai_intel/api/public_risk_summary.py`（约 13 个函数，冻结契约 `RiskSummary`/`RiskFinding`）：src 内零导入者、无路由挂载、`app.py` 无装配——与 /tasks 同属「producer 已写、默认装配未接」家族，且它连路由都未挂（README 路由表亦无对应条目，`test_route_inventory.py` 因此不会报漂移）。入后续批次的公开面 producer 盘点范围为宜。

### 盘点边界声明
- 本盘点为纯静态代码核对：所有行号以当前工作区 HEAD `b4407f833` + 未提交工作区状态为准；未运行任何 pytest，未复跑 `test_route_inventory.py`，其最近记录在案的通过证据为 `progress/context_handoff.md:1033`。
- 「完整接线」指装配链与契约测试的静态事实，不代表 live 环境已验证（模型凭据、真实轮询、真实任务数据均属 blocked_live）。
