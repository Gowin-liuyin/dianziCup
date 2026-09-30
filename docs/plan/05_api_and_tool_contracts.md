
# 05 · API、工具与运行时Agent合同

以下为本项目待实现接口，不是第三方API。已有仓库接口需T00映射。统一前缀 `/v1`；前后端与worker不能各自定义不同状态。

## 1. 认证与会话

首版只服务预先创建的团队用户，不开放公共注册。密码使用经过维护的Argon2实现；随机不透明session token至少32随机字节，服务端保存hash。Cookie设HttpOnly、SameSite，生产Secure；限制有效期，登出撤销。不要自创加密或签名算法。

维护viewer、analyst、tenant_admin、system_admin角色和明确权限表。tenant_admin不能修改公共来源或其他租户。创建首个用户通过管理CLI读取秘密输入，不把默认密码写进代码或命令日志。

会话使用CSRF token和严格Origin/CORS检查；csrf随机值与session绑定，由登录响应或认证后的csrf接口取得，前端内存使用。不得用开放跨域加credentials。租户、角色、权限版本由服务端认证上下文注入，请求体同名字段应拒绝或忽略并记录，绝不信任。

## 2. HTTP公共规则

写入接口需要 `Idempotency-Key`，作用域包括当前tenant、route和主体。相同键+相同请求返回原操作；相同键+不同请求返回409。不要把token或凭据纳入可见日志。

成功同步操作200/201；已接收长任务202且返回job_id；400非法业务输入；401无登录；403明确权限不足；404不可见对象与不存在对象统一；409冲突或幂等碰撞；422schema错误；429预算/限流；503依赖不可用。

统一错误体：`error.code, error.message, error.retryable, error.details, trace_id`。details只含可公开字段，禁止原始异常栈、密钥或其他租户标识。

分页：cursor + limit（默认20，最大100）；按稳定排序键分页，返回next_cursor。客户端不能提供原始SQL、OpenSearch DSL或任意sort表达式。

## 3. 接口清单

| 方法与路径 | 输入核心字段 | 返回/权限 |
|---|---|---|
| POST `/auth/login` | username、password | session、csrf；登录限流 |
| GET `/auth/me` | 无 | 当前用户、tenant、角色，不返回凭据 |
| GET `/auth/csrf` | 已认证会话 | 当前session绑定CSRF值 |
| POST `/auth/logout` | CSRF | 撤销session |
| GET `/sources` | category、enabled、cursor | 来源与健康状态；私有范围过滤 |
| POST `/sources/{id}/collect` | stream_kind、bounded_window | 202 job；相应管理员 |
| GET `/events` | q、product、risk_type、updated_after、cursor | 事件列表与摘要状态 |
| GET `/events/{id}` | 无 | 事实、维度状态、修订时间线 |
| GET `/events/{id}/claims` | status、cursor | 事实与证据标识 |
| GET `/evidence/{id}` | 无 | 指定版本、原文片段与定位 |
| GET `/document-revisions/{id}` | 无 | 允许展示的正文、解析质量；不暴露存储路径 |
| POST `/asset-snapshots` | asset_id可选、display_name、snapshot | 201快照；analyst |
| POST `/asset-imports` | JSON/CSV上传、import_kind | 202解析任务；大小/行数限制 |
| GET `/assets` | product、cursor | 本tenant资产与快照 |
| GET `/assets/{id}/snapshots` | cursor | 历史快照 |
| POST `/asset-observations/search` | approved_scope_id、product_key、fields | 202被动查询；analyst且FOFA授权 |
| POST `/assessments` | event_id、asset_snapshot_id、rule_id可选 | 202研判任务 |
| GET `/assessments/{id}` | 无 | 结果、freshness、缺口 |
| GET `/assessments/{id}/evidence` | 无 | 完整条件树与证据包 |
| POST `/investigations` | question、asset_ids、event_ids、budget_profile | 202调查任务 |
| GET `/investigations/{id}` | 无 | 任务状态、停止原因、结果引用 |
| GET `/investigations/{id}/tool-runs` | cursor | 脱敏实际工具轨迹 |
| POST `/questions` | QuestionRequest | 200完成回答或202调查；计时规则统一 |
| GET `/answers/{id}` | 无 | 回答、引用、freshness与版本 |
| GET `/conversations/{id}` | cursor | 仅本人/授权范围历史 |
| GET `/changes` | asset_id、event_id、cursor | 更新原因、旧新结果与状态 |
| POST `/subscriptions` | product_keys、asset_ids、risk_topics | 201本人订阅 |
| PATCH `/subscriptions/{id}` | enabled、过滤条件 | 200；逐字段授权校验 |
| GET `/recommendations` | unread、cursor | 推荐原因、证据、关联资产 |
| POST `/recommendations/{id}/read` | 无 | 已读，不更改其他用户状态 |
| POST `/exports/openvex` | assessment_ids、export_profile | 202/200经过校验的导出；analyst |
| GET `/jobs/{id}` | 无 | 业务状态、分阶段结果、错误摘要 |
| GET `/health/live` | 无 | 进程活性；不伪称外部依赖正常 |
| GET `/health/ready` | 无 | 必须依赖可用性，未配置关键项说明 |
| GET `/operations/status` | 无 | source freshness、积压、索引滞后；管理员 |

外部标准/政策/论文作为事件或知识实体检索，通过kind筛选，不需要另建没有数据的空接口。

## 4. 请求与响应关键结构

`QuestionRequest`：question（非空、长度上限4096）；conversation_id可选；asset_ids最多20；event_ids最多20；mode=auto/library/investigate；known_at可选；valid_at可选。不同时间语义见03，不允许只提供模糊“历史”标志。

`AnswerResponse`：answer_id、status、answer_text、claims、evidence、assessment_refs、limitations、freshness、data_mode、knowledge_epoch、started_at、completed_at、latency_milliseconds、trace_id。

`JobResponse`：job_id、status、completed_steps、pending_steps、failed_steps、result_refs、error、created_at、updated_at。completed_steps只来自真实任务状态，不按页面动画递增。

所有对象引用在返回前重新核对可见范围。访问他人answer/trace/export与访问他人asset同样拒绝。

## 5. 连接器接口

`discover_updates(cursor, window) -> DiscoveryPage`

`fetch_record(candidate, request_context) -> RawFetchResult`

`normalize_record(raw_fetch_result) -> NormalizedDocument`

`probe_capabilities() -> ConnectorCapabilities`

DiscoveryPage包含candidates、next_cursor、has_more、window_complete；不以列表空自动推断已到末页。候选含source_record_id、uri、upstream_modified_at可空、upstream_version可空。

连接器不能直接改Claim或Assessment。normalize只做来源解析，不调用LLM判断真实影响。

## 6. 三类模型接口

`generate_structured(messages, output_schema, model_context) -> StructuredGenerationResult`

`embed_texts(texts, model_context) -> EmbeddingBatch`

`rerank_passages(query, passages, model_context) -> RankedPassages`

ModelContext含provider_id、approved_model_id、timeout、token_budget、data_policy、run_id，不含公开可见密钥。服务端注入认证信息。

记录provider/model revision、prompt_version、schema_version、输入hash、调用时间、token计数和费用。费用未知写unknown，不能填0。模型拒绝、超时、错误JSON和无检索结果分别处理。

真实接口依据已配置提供者官方文档实现，禁止假定所有“兼容”服务支持同样的工具或结构化输出参数。没有模型key时只做fixture合同测试并明确live阻塞。

## 7. 工具注册表

| 工具 | 填补的缺口 | 外部/权限 |
|---|---|---|
| search_intelligence | 事件、机制、补充资料 | 受控公开检索，预算限制 |
| get_advisory | 官方描述、版本、修复 | 仅注册来源/允许URL |
| get_inventory | 当前资产与组件 | tenant只读，不向公开研究角色暴露全部私有字段 |
| get_public_observations | 被动产品/版本观察 | FOFA授权范围与字段白名单 |
| compare_versions | 版本包含关系 | 纯计算，不联网 |
| evaluate_rule | 已发布规则判断 | 纯计算服务，固定快照 |
| search_papers | 论文候选与机制证据 | 注册学术来源 |
| read_evidence | 指定span与revision | ACL、时间与状态检查 |
| find_changes | 某对象历史变化 | tenant与已知时间范围 |

初版不提供shell、代码执行、任意SQL、任意内网URL、任意修改资产工具。每个工具定义输入schema、输出schema、角色、预算、超时、缓存/执行键和会填的槽位。

## 8. 工具输入输出与幂等

模型提出 `tool_name, arguments, goal_id`；gateway注入tenant、user、policy和预算。模型自报tenant、authorization、skip_validation全部拒绝。

ToolResult包含tool_run_id、status、data、evidence_ids、searched_scope、observed_at、executed_at、retryable、error_code、usage、is_synthetic。`no_result`说明查询范围，不能推论全网不存在。

同工具+目标快照+参数hash+策略版本使用call_key；已成功结果可复用。失败是否重试根据错误分类和总预算；不得由四个角色分别对同一失败再重复8次。

## 9. Agent输出schema

PlannerDecision：goal_id、missing_requirements[]、candidate_action_id可选、action=call_tool/finish/request_information/wait_for_approval、reason_code、short_reason。只能选择服务端列出的candidate_action_id。

ExtractionBatch：document_revision_id、candidates[]；每项subject_key、predicate、object、qualifiers、quote_text、block_id、origin；缺证字段为空并写reason，不擅自编造。

AssetDecision：asset_snapshot_id、rule_id、requested_tool_action可选、assessment_ref可选、missing_fields[]、scope_limitations[]。不允许模型自填最终确定判定绕过evaluate_rule。

AnswerDraft：conclusions[]（text、kind=source_fact/rule_result/project_suggestion、support_ids[]）、limitations[]、recommended_actions[]。source_fact/rule_result必须指向当前可见的已验证证据或Assessment；project_suggestion与官方修复明确区分。

对应运行时提示词在 `docs/runtime_prompts/`。这些提示词不授予工具权限，安全依然由服务端执行。

## 10. 故障与前端行为

前端显示queued/running/partial/failed/stale/not_configured，不拿空数组统一展示“暂无风险”。刷新页面后可用job_id恢复进度。无权限不显示对象标题、数量或敏感错误细节。

模型或搜索不可用时，允许显示已有结构化事实，但显著标注降级。不能把fallback模板当成正常高质量问答评测结果。
