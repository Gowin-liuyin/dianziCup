# R18 · Typed async task PG 接线只读分析

分析任务：G-E/R18，状态 `awaiting_review`（只读建议待 Root 采用，不是实现或验收）。R18 原记录仍为 `in_progress / partial`，本报告不改进度、不签 accepted。开始：2026-10-16 21:42:28 UTC（2026-10-17 05:42:28 +08:00）；源码采样：2026-10-16 21:47:15 UTC；最终截止：2026-10-16 21:49:46 UTC（2026-10-17 05:49:46 +08:00）。60 个实际文件 raw SHA256 见 [source_hashes.json](../runs/r18_typed_task_bridge_analysis_20261017/source_hashes.json)，真实命令退出码与HEAD见 [receipt.json](../runs/r18_typed_task_bridge_analysis_20261017/receipt.json)。

分支 `codex/full-delivery-recovery`；HEAD `3fd9cd68f292afcd1b88ca55f218c4e869e8f706`。这是混合工作树审计：已有 Root R12/R19 未提交集成，以及 CR-R18 question reservation 未提交修订；不把 HEAD 当全部文件版本。只新增本报告与 `reports/runs/r18_typed_task_bridge_analysis_20261017/`。未修改业务、合同、迁移、状态或用户文件。

## 1. 结论与建议

公开 typed DTO、SDK 方法、PG 调查作业与秘密无关 ActorReference 都已存在；**公开 typed task producer / owner binding / 最终 QA 或 stack result 出版没有接通**。默认 `/api/v1/tasks/{id}` 不是可以轮询的生产能力：`public_extension_reads.py:801–805` 无条件抛 `PublicReadUnavailable`，`public_extension_routes.py:135–136` 返回 503 `not_configured`。没有公开 `/api/v1/ask` 或 `/api/v1/stack/check` POST，`/questions` 和 `/investigations` alias 不能代替它们。

建议采用 **Option A：调用方拥有一个 PG transaction 的窄接口**，复用 `enqueue_job`、现 owner/ActorReference、已有 workflow 和已核验证据/研判读取；新增明确 typed task binding 及对应最终结果出版。不要新增通用 JobService/BaseService、内存 task store、MCP task authority，也不要把 workflow 改成假成功。推荐 3 个相依 slice，所有权见 §8。

当前调查 `finish` 将除 failed / waiting_approval 外的结束一律保存为 `partial`（`workflow_service.py:1683–1718`）；Assessor 明确 `assessment_adapter_not_configured`（1423–1432），Reporter 明确 `report_export_adapter_not_configured`（1532–1533）。所以短期公开 ask task 可以合法保持 partial；只有存在真实、已出版、当前资格核验过的 QAAnswer 才能携 result，不能用 `WorkflowResult` 或 202 提交耗时代替完整回答。当前 Reporter/Assessor 缺口不能通过公开 bridge 的状态投影抹掉。

## 2. 合同和当前能力边界

已读 `AGENTS.md`、执行地图、R18 卡（`12_recovery_task_cards_20261014.md:203–211`）、T32/T35/T51、03/04/05、相关 06/09、全部七个 CR-R18、CR-R09、task_state 的 R18 和当前交接/所有权相关条目。使用 Ponytail 5.3.1：复用已有模块，最小完整改动，不删既定范围。

| 合同 | 实际要求 / 后果 |
|---|---|
| R18 卡 207–211 | 同业务服务输出 REST/OpenAPI、stdio 与 HTTP MCP、CLI/SDK、三扩展及沙箱真实日志；本分析只处理 typed task 子链，不完成整 R18。 |
| T35 33–43，C03/C04/C05 | 同步200 / 异步202、job↔answer追溯、完整延迟、幂等不重复扣预算、owner授权和实际轨迹。 |
| 04:110–122 | 已入库同步；缺外部证据异步；从最初提交到完整答案计时；202延迟不能当完整时延。 |
| 05:19–25、75–77、151 | route+tenant+principal 幂等，当前对象再次校验；200组件同步；独立上传10MiB/10000组件异步，不能同数组超200自动202。 |
| CR-R18 envelopes | TaskDescriptor 只有 ask/stack_check；succeeded必须真实对应result；pending无result/error；失败终态有明确PublicProblem。上传/report/subscription须另冻结扩展版本，范围没有取消。 |
| CR-R18 actor | 原auth_sessions/api_keys/users为身份权威；reference不是bearer；锁当前凭据/users→job/真实owner→资源；不保存raw token。 |
| CR-R18 question（工作树修订） | ActorReference+credential缝隙、成功新预约与ask bucket同事务，重放不扣；锁后DB clock重验；当前主源码尚未包含该新问答实现。 |
| CR-R09:15–29 | 两transport、六只读和可配置本人订阅；OAuth按选定客户端需求实施并实测；SourceConnector/Enricher/Tool三类扩展不删，subprocess不算容器沙箱。 |

`progress/task_state.json:6043` 的 R18 为 `in_progress / partial`，unit/contract/integration/security/frontend/e2e/live/manual 都 `not_run`。其 history 含过去限定切片证据，但不能把这些累加为当前完整 typed 链或整 R18 通过。

## 3. 默认产品→认证→业务→PG 当前链

| 环节 | 已支持的源码事实 | 缺口 / 不可推断 |
|---|---|---|
| 默认 App | `create_application(auth_service=None, *, settings=None) -> FastAPI`，`app.py:48–55`；PG engine按配置，使用PG auth state（64–70）；生命周期释放engine（72–81）。174–181挂public router。 | CORS allow_headers 在89仅 Content-Type/X-CSRF-Token/Idempotency-Key，没有 Authorization；浏览器Bearer跨域路径需主控核正式接线。只读CLI本身不受CORS。 |
| 公开 GET | `build_public_extension_router(engine, data_mode, *, source_polling_enabled) -> APIRouter`，routes78–83；GET vulns/vuln/sources/tasks（140–179）。 | 仅四GET；tasks方法本身恒503；无ask/stack公开POST。 |
| 当前读取事务 | routes92–120：parse cookie/Bearer→Session.begin→key consume read / cookie current principal→READ_PUBLIC→reader→再认证→重新读取并digest比较→再认证→JSON。 | generic reader只有Session+scope，不持本次credential；typed task需要窄受信引用/owner服务注入，不能只用tenant查任意job。双读不能执行副作用/再次消耗bucket。 |
| API Key | `parse_request_credential(authorization_headers, *, session_cookie=None, query_parameter_names=())`（credentials120）；cookie+Bearer/query/重复畸形拒绝；`lock_authenticated_principal(connection, credential, now) -> AccessScope`（252–262）。 | key不能传入 `session_token:str` 伪装cookie；publicPOST应用该显式接口。 |
| 原子限流 | `consume_api_key_rate_limit(connection, credential, now, *, operation:Literal['read','ask']='read') -> AccessScope`（265–312），要求当前事务，key/users锁，bucket insert+FOR UPDATE，失败rollback，锁后时间推进，read60/min、ask10/min。 | 当前workflow enqueue没有调用；publicPOST不能独立先扣再建job，也不能每个重放/最终回执再扣。 |
| 旧问答 | `build_question_router`（question_routes59）；authenticate只读cookie（71–87），write有CSRF/Origin；ask（118–124）传cookie。 | 不是Bearer `/ask`。`build_question_service` 57 构造 EventEvidenceRetriever 没传settings.data_mode；当前CR指出的fix2尚待Root合适版本。 |
| 同步问答服务 | `GroundedQuestionService.ask(payload:QuestionRequest, scope_provider:Callable[[],AccessScope], idempotency_key=None, *, session_token:str) -> QuestionAnswerResponse`（service197–204）。单event、无asset/conversation/history/investigate（209–217）；真实answer reservation / usage /最终响应。 | 不能解除限制后假称R12/R14能力；当前 reservation insert（254–270）没有身份锁或bucket。新增CR的ActorReference/credential分支在当前根文件未出现。 |
| 问答历史 | `read_grounded_answer(engine, scope, answer_id, *, session_token:str) -> QuestionAnswerResponse`（136–175）；本人tenant、completed限定、证据定位/版本检查、public epoch变更标stale。 | 自开Session，不能作为public poll事务内部的最终一致读取；缺 `read_in_session` port。它检查证据存在/版本/quote，不自动证明所有claim当前内容支持，typed producer须沿已核验support服务。 |
| 调查 enqueue | `InvestigationWorkflowService(engine, actor:AuthenticatedCredential|ActorReference, checkpoint_connection_string, checkpoint_schema, *, data_mode, model_factory=None, model_provider=None, model_version=None, content_store=None)`（331–343）。`enqueue(request:InvestigationRequest,budget:WorkflowBudget,*,idempotency_key:str)->UUID`（370–376）。393–466：自己开transaction、create_actor_reference、READ_PUBLIC、owner key、enqueue_job、immutable owner、图/epoch/快照绑定。 | 没有caller-owned Session port或created/replay receipt；缺原始公开AskRequest/task_type/result关联；调查目前一event/指定证据refs，任意AskRequest不能靠挑首event转换。 |
| 调查执行 | `execute(context:JobExecutionContext,*,pause_after=())->WorkflowResult`（485–490）；guard、PG advisory执行锁、checkpoint input digest、scope/current graph和lease（616–727）；外部工具/模型有限预算与receipt。 | WorkflowResult只含draft/receipts/missing，不含完整公开QAAnswer的answer_id/timing/citations；不能直接返回它。 |
| 默认worker | runtime118–129：investigation固定路由专queue，其他job固定普通executor；workers/investigation57–100 claim/job_type→PGpayload→storedActorRef→service.execute；registry+context不接受任意handler。 | 公开typed publication尚未挂在真实完成事务；不是只加路由就支持。 |
| Assessment | `AssessmentService(engine, session_token:str|ActorReference, content_store)`（107–109）；prepare/commit/read真实PG+授权快照/已发布规则；read328–370核current规则输入digest、资产current snapshot/active/fingerprint，stale独立。 | 当前无公开 `read_in_session`；read自开Session；不能在公开risk/Task事务里调用后就称最终一致。另独立作者负责的同事务read候选，本分析没有看到主仓接线，冻结签名unknown。APIkey有效permission只有read scopes，不应增加WRITE_ASSET来“使测试通过”。 |

## 4. ORM字段与身份/租约/当前结果的接线约束

实际是 SQLAlchemy Core `Table`，不是虚构 `PGJob` ORM类。

**Job 权威。** `knowledge/models.py:160–186` 的 `job_runs` 字段：job_id、tenant_id、job_type、status、idempotency_key、payload_sha256、payload_ref、attempt_count/max_attempts、lease_owner/lease_expires_at、created_at/updated_at、next_retry_at、started_at/finished_at、error_code、result_ref。没有 owner_user_id、trace_id 或公开 task_type。`job_payloads`（202–208）存byte payload；`outbox_events`（188–200）有job FK和payload_ref；`job_transitions`（210–220）保留attempt/状态/固定reason。**同tenant不足以授予读取权。**

**提交函数。** `enqueue_job(session:Session, tenant_id:str|None, job_type:str, payload:bytes, created_at:datetime, idempotency_key:str|None=None, max_attempts:int=5)->str`（outbox23–103）同事务保存job/payload/outbox；按tenant+job_type+idempotency key PG advisory xact lock，digest冲突409，重放返回已有job。公开入口需把route/owner编码进受信幂等域（如现workflow owner-key做法），不把raw key或请求自报tenant加入authority。当前返回值没有created bool，调用方应根据同事务已有binding/唯一插入receipt判新旧，不用created_at浮点比较猜重放。

**当前凭据表。** `credential_models.py:16–60`：api_keys只存key_id/token_hash/user_id/resource/scopes/issued/expires/revoked/version；rate PK=key+operation+minute。Key只有read:public/read:asset，角色表（access27–33）viewer public、analyst public+asset。ask所需READ_PUBLIC；涉及资产 additionally READ_ASSET和tenant真实对象，不信body。derived任务不是任意写权限。

**Durable actor。** `ActorReference`（actor_references59–79）存credential_kind/user/tenant/role/permissions/version/digest/resource/issuance/created/session_hash或key_id+credential_version；factory-only。`create_actor_reference(connection,credential,now)`（213–247）在当前事务锁真实credential/users并构造；`actor_reference_payload`（250–268）只给内部PG。后台只decode来自受信PG binding。`lock_actor_reference_scope(connection, reference, now)`（346–389）重验lifetime、revocation、owner/tenant/role（含升权变化拒绝）、权限版本、issuance、resource、key version，返回冻结与当前权限交集。

**真实owner。** investigation_workflows（workflow150–169）=job_id FK/owner_user_id FK/tenant_id/authorized_role/actor_reference/graph_version/input_sha256/input_json/budget_json/scope_epochs/asset_snapshot_id/deadline_at/created_at；有immutable trigger（214–217）。`InvestigationActorOwnerPort.lock_actor_job_owner(connection,job_id)`（249–271）真实锁该行。`lock_actor_job_scope(connection,reference,now,*,job_id,owner_port)`（actor422–439）按credential/users→job→owner，再重验expiry。新的public task binding必须给出同样真实owner port；不要用body返回owner。公开查询还需当前请求principal与stored owner同user/tenant，按原任务要求的权限交集核资源。原workflow guard还要求credential locator相同（workflow644–650）；是否允许同owner另一新key恢复公开任务为 **unknown**，不应悄悄放宽；初版沿现strict binding可行。

**Raw API Key。** 仅route/request内的 `ApiKeyCredential(SecretStr)` 与短事务认证使用；不得写job_payloads、request JSON、checkpoint、operations、model messages、typed output或报告。job_payload最多保存严格业务request和内部ID/digest；actor_reference仅存上面的无秘密locator/context。Reference本身不得成为公开请求schema或bearer。

**Lease。** `require_job_lease(session,job_id,worker_id,at,*,expected_attempt)->dict`（jobs182–208）必须running、owner/attempt一致、未过期，并FOR UPDATE；`complete_job(... outcome,completed_at,*,expected_attempt,result_ref=None,error_code=None)`（230–262）效果与状态同Session原子提交，清lease/nextretry，记transition。result_ref只允许固定 `pg:<kind>:<id>`，error只固定safe码（45–53）。普通job lease60s（18），不得只看Celery AsyncResult；旧attempt无法出版新result。

源码 `require_job_lease` 使用调用者先传入的at作为WHERE条件；它自身没有锁等待后再取DB clock。新typed出版端应在拿齐owner/job/resource锁后用同connection的PG `clock_timestamp()` 核真正的lease/deadline/credential时限，并在提交前重验（沿当前CR-R18 question fix2，不新建时钟真相）。本轮未做真实PG锁等待实验，不能把该静态风险写成已经复现的失败。

**Current result。** QA出版需真实answer row、request digest、verified generated claims与完整CitationProjection、scope epochs、data_mode、model/prompt和真实usage；latency从公开任务首次admit到完整publication。Assessment result（assessment_persistence25–69）append-only，固定tenant/asset/snapshot/event/rule/version/epoch/policy/inputdigest/result_payload；read现检资格（service348–370）。Task GET不能直接返回持久JSON，须在当前身份/owner/epoch/规则/资产/原文支持锁住时重新投影freshness；缺当前proof拒绝或partial/stale，不能保留已知current。历史不覆盖。

## 5. 九态、父子语义与公开error联合

| PG状态 | 冻结TaskResultEnvelope行为 |
|---|---|
| queued/running/retry_wait/waiting_approval | result=null，error=null；step来自真实receipt，不能动画递增。waiting_approval虽被worker delivery terminal集合包含，仍是公开pending；不能自动当failed或completed。 |
| succeeded | 必须对应typed result；error=null，pending_steps/failed_steps空。 |
| partial | schema允许对应typed result或null、error或null；没有强制另一个union形态。保留缺口，不自行把冻结schema收紧。 |
| failed/cancelled/blocked | result=null、明确PublicProblem；公开HTTP鉴权失败另走HTTP Problem，不泄漏不可见task。 |

TaskHandle（v2:554–590 / SDK models230–244）只有kind=task、task_id、queued/running/retry_wait/waiting_approval/partial、poll_uri、created_at；终态用TaskDescriptor（extensions1428–1475 / models524–553），不能返回旧queued句柄伪终态。URI必须是自身canonical task_id，SDK再核（models550–553）。

`TaskResultEnvelope.result = QAAnswer | StackCheckEnvelope | null`；error=`PublicProblem | null`（schema1513–1540、1573–1753；SDK565–597）。没有单独公开TaskError枚举或discriminator。PublicProblem是type/title/status/error:string/trace_id（schema1477–1511），不同于HTTP RFC9457 ApiProblem中的 `error:{code,message,retryable,details}`，也不同于MCP `is_error` ToolResult。需固定映射函数，只接受job固定safe码，不传异常str、SQL、raw token。trace_id须有真实稳定关联，可在typed binding建trace UUID；job_runs目前没有此列。

已有父子作业不能机械套入：

- Source job succeeded表示其受控窗口/页面业务完成，0新条目可以成功，不代表QA/stack。
- Enrichment parent `initialize`（job_service556–604）创建child+publication，返回JobExecutionResult默认succeeded，表示**排程结束**；它不是所有child/维度成功。最终publication另等child终态（1047），任何attempt或child非succeeded就partial（1125–1129）。公开task只看parent succeeded会是假完成。
- Investigation本身是PG job，角色operation不是独立child job；operation reserved/succeeded/partial/failed（workflow172–209），只能据各真实operation归类step。WorkflowState的stale映射PG partial+workflow_inputs_changed（1721–1735）；不能把stale创建新JobStatus枚举。
- Assessment当前prepare/commit是同步PG服务；没有自动存在assessment job/parent。裸assessment_id不能冒充task_id。
- Revalidation/subscription有自己的owner/generation/状态合同；不在当前TaskDescriptor的两task_type中，禁止把它们装成ask/stack。

## 6. 两个可实施接口 Option

下列是**拟新增签名**，不是现已存在。公开DTO沿冻结schema，不修改原八对象。Root先在CR/所有权登记内部port与迁移事实，再实现。

### Option A：调用方拥有transaction（推荐）

保留老engine-owned入口作wrapper，新增窄transaction ports，route/worker只协调同一Session；不复制业务判断。

```python
InvestigationWorkflowService.enqueue_in_session(
    session: Session, request: InvestigationRequest, budget: WorkflowBudget,
    *, actor: ActorReference, idempotency_key: str,
) -> InvestigationEnqueueReceipt  # job_id + replayed，原enqueue仍返回UUID

read_grounded_answer_in_session(
    session: Session, scope: AccessScope, answer_id: UUID,
    *, actor_reference: ActorReference,
) -> QuestionAnswerResponse

AssessmentService.read_in_session(
    session: Session, scope: AccessScope, assessment_id: str,
) -> AssessmentReceipt

read_public_task_in_session(
    session: Session, scope: AccessScope, task_id: UUID,
    *, actor_reference: ActorReference, result_reader: PublicTaskResultReader,
) -> TaskResultEnvelope
```

`PublicTaskResultReader`仅两个固定result分支（QA已出版row / Stack真实receipt+当前risk producer）；不通用CRUD、不任意URL/SQL、不接受用户回调。可用两固定函数代替Protocol，避免不必要抽象。它应由Root受信工厂传入public reader，`PublicExtensionReadService.get_task_result`不重新造认证/第二job truth。已有独立assessment作者的 `read_in_session`具体冻结签名 **unknown**，Root应协调采用其真实接口而非再实现。

最小持久化建议是一张窄 `public_task_bindings`：schema_version、task_id/job FK、task_type、真实owner_user_id/tenant_id/authorized_role、无秘密actor_reference、public_request严格DTO、request_sha256、trace_id、typed result locator（ask answer_id / stack receipt_id，互斥）、admitted_at/deadline_at。不可变绑定，status/attempt/lease仍读job_runs，不再维护第二状态列。现workflow owner须与binding同事务强校验；stack的owner不能借别的workflow。typed result locator不是结果已经存在证明，succeeded GET必须取到有效实体。

若ask只映射现调查job，task_id=真实investigation job_id；需要同事务公开绑定和原公开AskRequest，不能从WorkflowResult临时推测。`enqueue_in_session`使 create_actor_reference→幂等→新insert→ask限流→job/payload/outbox/owner/binding能整体rollback。新请求才consume ask；replay用既有job及原binding，不扣第二次。完成publication由workflow真实 `finish`事务使用对应answer publisher，当前scope/proof/lease有效才写grounded_answers completed与关联；不是在poll GET时生成/付费或补假状态。当前workflow实际partial保持partial。

Stack现同步200路径复用现独立risk producer与Assessment同事务read。若尚无真实stack async producer，就拒绝未绑定stack任务；不能先创建一堆空stack job来宣称范围覆盖。10MiB上传/10000组件是保留后续切片，需明确上传任务合同与真实parser/receipt；不修改普通check_stack数组上限或自动202。新增实际stack task receipt事实若需要新表，只存该集合业务的输入范围和已核验assessment refs，事实仍读现PG，不另存假判断。

优点：当前public routes `serve`本来持Session和scope（98–120），当前最终owner/proof可以在此锁住；worker publisher也能同Session complete_job。默认旧cookie入口不变，source/vuln四GET无需重写。代价：为现engine-owned QA/assessment/workflow抽出少量内部ports，需要与当前唯一作者协调文件所有权。

### Option B：task专用engine-owned service

```python
PublicTaskService.enqueue_ask(
    request: QuestionRequest, credential: AuthenticatedCredential,
    *, idempotency_key: str,
) -> QuestionAnswerResponse | TaskHandle

PublicTaskService.read_task(
    task_id: UUID, credential: AuthenticatedCredential,
) -> TaskResultEnvelope
```

此service自己开Session、认证/rate、真实owner、read/publish；task route绕开generic `serve`而只做strict输入/错误/DTO。其内部仍须调用上述in-session QA/Assessment/proof端口，不可用现自开Session的 `read()` 后只锁一次身份就称原子当前result。可以在task分支保持单一认证事务，但要新增一套与现serve相似的错误/限额/重验协调；如果直接复用engine-owned业务，会产生不同connection的锁序、最终资格空窗和rate double-consume风险。

两option共享同一窄binding和PG权威；B不等于新增通用任务系统或父子wrapper。就当前源码，A重用现transaction最多、重复协调最少，且自然闭合publication+complete_job，因此推荐A。为“让wrapper自己的状态succeeded”再加public parent/child调查job不是必要接口选择；如后续上传确需分phase，应按现enrichment事实说明排程/出版区别，单独设计真实child roster与出版触发，不套parent succeeded。

## 7. 真实客户端接线和未删范围

SDK `get_task_result(request:GetTaskResultRequest)->TaskResultEnvelope` 与async版本（client681–701）已有，绑定response task_id。ask result HTTP200必须QAAnswer、202必须TaskHandle（282–287）；check_stack当前只接受同步200（290–293）。CLI当前只有ask/check，ask到handle仍exit2并说明risk未确定（cli79），没有完整任务轮询命令。最小新增 `task <uuid>` 或受deadline约束的 `ask --wait` 应只调用已有GET；终态不是单纯收到handle的退出状态，完整计时取server出版结果。具体CLI体验为Root任务内选择，不改冻结0/1/2/3语义。

MCP adapter已有六工具代码，`include_extended_tools=False`为老调用默认（adapter172–173）；stdio入口26没有显式True，故默认产品仍两工具。HTTP context adapter239直接not_configured；逐请求/逐tool auth尚未闭合。enable六工具只能在真实producer连通后由Root明确改产品入口；旧API兼容默认参数可留。

子分析读取已安装官方2.3.0源码：`backend/.venv/Lib/site-packages/mcp_types/_types.py:610–612`任务types仅兼容、core不dispatch；`methods.py:101/146/174/209` tasks方法刻意不在core；低层server capability628–636未设tasks。所以不要假设Python SDK的协程或protocol taskID就是durable PG任务。现adapter只是await业务SDK；业务TaskHandle→get_task_result工具足以落实冻结公开异步合同；如选定客户端实际需要协议task extension，再按该版本成熟能力、明确映射、真实客户端测试做独立切片，禁止新内存authority。

两transport、OAuth的选定客户端条件与三插件/容器网关均留在R18后续有界范围：SourceConnector、Enricher、Tool/Skill真实模板/manifest/SDK/fixture/本地索引；非root只读容器、受限syscall/出口、无secret/主库/任意依赖。现SourceConnector Protocol不是插件沙箱交付；本轮未找到完整R18插件产物/runner，不把“未找到”写成绝对不存在。

## 8. 最小3-slice、文件所有权和依赖

| Slice | 文件所有权 / 真正输出 | 依赖与至少六类回归 |
|---|---|---|
| S1 身份/预约/事务ports | **Root唯一**：actor/auth/credential相关缝隙、answering/service的已批准CR集成、investigation/workflow_service transaction enqueue+真实typed出版port、binding metadata、前向迁移与public合同；**既定唯一作者**：Assessment `read_in_session`与risk producer候选，Root只定冻结接口并集成，不双writer。 | 先合独审认可的question fix2和同事务assessment接口；PG新请求+replay、不同payload409、限额rollback、两租户/同租户不同owner、撤销/角色/锁后expiry、lease旧attempt/重启恢复。网络/modelIO不在锁事务中。 |
| S2 公开producer+default App | **Root**：app.py、public_task最小binding/read/publish模块、POST `/ask`、`/stack/check`与GET任务注入；**公开adapter作者**只拥有指定risk/adapters和直属tests，不能同时改Root任务binding/schema。现sources/vulns读作者不触碰。 | S1真实PG过后；完整TaskHandle→GET九态、对应typedresult、rawsecret不进job/log、support撤回/epoch/资产变化、HTTPerror/taskerror区别、created/admitted→published完整时延；默认实际REST/Bearer/真实worker重启。 |
| S3 客户端/门与剩余transport接口 | **SDK唯一作者**：mcp_stdio.py显式六工具、mcp_adapter.py共享逐调用HTTP身份、CLI实际polling及直接tests；**Root**：App挂载/OpenAPI与CI接线/许可证/制品入口。三插件及OAuth按R18保留任务明确另冻结，不和S1混写。 | S2真实producer；stdio clean stdout、SDK install+真实REST contract、call cancellation不取消PGjob误报、HTTP key撤销/无全局代理key、8k/1MiB完整单元、客户端Codex/Claude实调用分项、package制品/CI有失败与零测试门。 |

不做：本轮不改任何这些代码、合同/评分/盲测/预算、不运行tests或PG、WSL/服务/native应用/网络、不读秘密或holdout、不push。不把未实现上传/report/subscription或OAuth/插件范围从计划删除。

**0031占用状态：** 当前 `backend/migrations/versions`实际源码最高0030，0030 revision/down_revision是0030_revalidation_actor_bindings→0029_recommendation_receipts。目录与docs/decisions、plan、progress、tasks的定向rg没有0031迁移/编号预留证据。结论仅“本根工作树未占用0031”；其它活跃worktree及Root未落盘编号预约 **unknown**。编号仍Root唯一，不能据本报告自行创建0031、编辑已应用0028/0030，或声称生产alembic_version已到0030。必要binding迁移需Root先确认并登记；若能用现真实typed持久关联完整解决且不丢原公开request，则不建空表/空迁移。

## 9. 索引交叉、真实命令与未查项

本轮只用PowerShell文件读取、rg、Git只读、SHA256与clock；不是测试。read-only tool日志保存在本对话；独立run另保存最终HEAD/status/文件hash和读证据收据。代表实际命令：

- `git rev-parse HEAD`、`git branch --show-current`、`git status --short`、`git diff --name-only`：exit0；diff有他人文件，全部保留。
- `rg --files docs/plan docs/tasks docs/decisions contracts/schemas progress` + 定向R18/T32/T35/T51筛选：exit0。
- `rg -n` 函数、当前caller、job/owner/result、0031 与公开task schema，以及带行号Get-Content：最终有效读取exit0。
- 首次对不存在 `cli/`、`plugins/`、`infrastructure/persistence/jobs.py`、`investigation/persistence_models.py`、`workers/investigation_worker.py`、`assets/inventory_service.py`及PowerShell不展开的`*.py`/`R18*`路径探测分别有路径错误/exit1；按真实 `rg --files` 定位并改读outbox.py/workers/investigation.py/workflow_service.py等。错误不冒充业务测试失败。
- `Get-FileHash -Algorithm SHA256`当前实际涉及文件：exit0，完整manifest与重复核验在独立run。
- tests数量=0（not_run，不是passed）；unit/integration/live/manual本轮全not_run。网络调用0，未开启模型/测绘付费任务；环境费用unknown。

读取既有CBM收据（没有执行其WSL命令）：`recovery_r18_api_key_expiry_fix2_20261016/cbm_final_index.json` 指明索引 `dianzi-r18-expiry-fix2-8e048523-20261016`、HEAD8e048523、历史exit0；`cbm_final_trace.json/log`追consume_api_key_rate_limit，列 `_lock_api_key/_advance_server_time/_validate_locked_api_key`等callees，历史caller数0。当前rg源码routes102确有read caller、workflow尚无ask caller，所以旧caller0不能证明当前无调用，也不能把旧图当当前Root接通证明。旧SDK CLI trace收据历史exit0仅辅助路径清单；当前SDK源码再核已有GET及无CLI poll。

关键raw hash：app.py=`5d314c5d06cb775f99cb0add95cfbc4482e1fb643cf6e269269b13976f26befe`；workflow_service.py=`ff4e9ee23be9dc6041d7cf5163f79cf93cd16d864730f59a1ad8c5e8feb004b4`；answering/service.py=`b3d1a18b0497972af1eaba81bb116b897c4d4559f4e91c5a96cf8423eefd66e1`；assessment_service.py=`761e5d51f7c4afc1f3cc1467f5628b930b38d84fb648ae2d98edae58ace628c5`；public_extension_reads.py=`4d6ae9d7cadef2524558dfbde9da0b5dde17542df7db6460f6bbbdca4c96ef92`；public_api_extensions_v1.json=`4ccc4337586137a407359a1c4a59dc5d92081a2f4b50ee32cc53fac16095d50b`。原v2文件本机raw hash=`4ff060b9c8ebb5f178c81bd5c957b65e7025a4afe20241ff083ed46ae4a22b84`，与CR历史canonical hash口径不同，不据此宣称结构合同改变。

未查 / unknown：未重新生成当前CBM图；未运行PG/Redis/默认App或客户端；生产DB迁移版本；其它活跃worktree0031编号占用；独立assessment/QA selector候选准确冻结接口；同owner换key恢复公开任务政策；上传任务新版本合同/实际parser产物；OAuth选定客户端需求；所有三插件完整产物与受限网关；真实模型当前可用性、token费用、性能/稳定窗口。静态接线分析不替代独审、真实PG撤销/租约和当前proof竞态验收。

评分证据仅表明T32/T35/T51在R18的未闭接线位置和实施路径；不登记A1/E1/X1已达档。下一步建议：Root冻结S1内部ports与真实binding的最小DDL/无需DDL理由，确认0031所有权和现QA/assessment候选的采样hash，再让唯一实现者按A接线并交全新非作者PG/默认产品审查。
