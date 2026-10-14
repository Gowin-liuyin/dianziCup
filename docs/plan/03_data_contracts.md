
# 03 · 数据合同与不变量

> R00恢复合同补充（2026-10-14T21:05:58+08:00）：用户已批准CR-R01–CR-R09建设决策与完整有界批次；准确落实awaiting_review。独立核对生效后以[变更记录](../decisions/CR-R07.md)和manifest.recovery执行。原T卡最终范围/原前置/六项验收完整保留；执行依赖按能力切片。新review/push规则见用户执行提示词，未完成live/人工不算通过。


本文件定义业务语义。字段名和枚举不能由不同模块各自发挥。T04把它们实现为类型与JSON Schema，T05建立迁移；以后增改字段使用向后兼容迁移和变更记录。

## 1. 通用约定

ID默认UUID字符串，公开漏洞标识另存，不拿标题作为主键。时间为带时区UTC，API用ISO 8601；不接受无时区输入。字符位置采用保存后的规范文本中的Unicode code point，左闭右开；PDF页码从1开始。字节大小明确 `_bytes`，时长明确 `_seconds`或`_milliseconds`。

所有记录含 `schema_version`。原始外部JSON可以保留，但已进入业务的字段必须类型化。不得用一个 `metadata: dict`藏起所有核心字段。

可见范围使用 `visibility=public|tenant` 与 `tenant_id`；public记录的tenant_id为空，tenant记录必须非空。私有引用不得进入公共衍生对象；派生记录的范围不得宽于任一输入。仓库查询必须接收由认证系统构造的 `AccessScope`。

不存在、未知、字段不适用、网络失败和权限不足不同。可选值为空时需要与相应状态/原因一并返回。

## 2. 公共枚举

| 类型 | 值与语义 |
|---|---|
| `SourceCategory` | structured_vulnerability、vendor_advisory、security_community、code_repository、technical_blog、academic_paper、technical_standard、policy_regulation |
| `DocumentKind` | advisory、article、paper、repository_record、standard、policy、asset_inventory |
| `ClaimOrigin` | source_explicit、structured_source、rule_derived、model_hypothesis、human_confirmed |
| `ClaimStatus` | supported、disputed、unverified、superseded、withdrawn；描述事实记录状态，不与条件真假混用 |
| `ConditionValue` | true、false、unknown、conflict；描述一个条件是否得到支持 |
| `DimensionStatus` | available、not_found、not_applicable、conflict、blocked、failed、pending |
| `FreshnessStatus` | current、stale、unknown；缺观察时间不填current |
| `RuleStatus` | candidate、validated、published、retired |
| `AssessmentStatus` | supported_applicability、excluded_with_evidence、insufficient_evidence、conflicting_evidence |
| `ToolStatus` | succeeded、no_result、partial、failed、denied、budget_exhausted、not_configured |
| `JobStatus` | queued、running、retry_wait、waiting_approval、succeeded、partial、failed、cancelled |
| `PocStatus` | candidate_found、static_reviewed、lab_verified、verification_failed |

`AssessmentStatus`不是“已入侵/绝对安全”。`freshness`为独立字段，旧结论可以有原来的结果但标stale，不能继续当当前判断。

## 3. 数据对象

### 3.1 Source / SourceCursor / FetchAttempt

`Source`：source_id、name、category、publisher、base_origin、allowed_origins、connector_name、connector_version、enabled、capabilities、poll_interval_seconds、auth_secret_ref、redistribution_policy、visibility/tenant_id。

一个来源只有一个主要类别用于覆盖统计。相同内容通过多个入口不重复计作多类来源。`auth_secret_ref`是环境引用，不是密钥本身。

`SourceCursor`：source_id、stream_kind(live/backfill)、cursor_json、window_start、window_end、last_successful_page、lease_owner、lease_expires_at、generation。

`FetchAttempt`：attempt_id、source_id、source_record_id、requested_at、completed_at、status_code、error_code、raw_sha256、response_size_bytes、effective_uri、rate_limit_wait_seconds。HTTP错误不自动改变历史事实状态。

### 3.2 Document / DocumentRevision / TextBlock

`Document`：document_id、source_id、source_record_id、canonical_uri、latest_revision_id。唯一约束为source_id+source_record_id；没有源标识时使用经过源特有规则归一的URI。

`DocumentRevision`：revision_id、document_id、revision_number、previous_revision_id、raw_object_key、raw_sha256、normalized_object_key、normalized_sha256、source_published_at、source_modified_at、first_observed_at、ingested_at、parser_version、normalizer_version、document_kind、language、parse_status、is_synthetic、visibility/tenant_id。

只与当前末版比较是否重复。历史内容A→B→A必须允许第三个修订，即使其hash等于第一版；不能以document_id+hash作全历史唯一约束。相同末版重复抓取只新增FetchAttempt，不重复新增文档版本。

原始字节变化但规范正文未变，可以新增留档修订并标 `material_change=false`，不必重新产生相同事实。历史原文不可覆盖。已归一内容的hash不是来源真实性证明。

`TextBlock`：block_id、revision_id、block_kind、text、text_sha256、page_number/section/json_pointer、start_offset/end_offset（相对于该revision固定规范文本）、table_headers。检索chunk是派生物，不能作为永久证据身份。

### 3.3 EvidenceSpan

span_id、revision_id、block_id、start_offset、end_offset、quote_text、quote_sha256、locator_kind、page_number、bounding_box可选、json_pointer可选、verified_at、visibility/tenant_id。

不变量：`block.text[start_offset:end_offset] == quote_text`，hash一致，范围合法。相同句子多次出现时，必须指定block和出现位置；不能默认第一次出现。模型只给候选片段，由程序定位。引用文字在原文中存在与该文字能支持论断，是两道不同检查。

### 3.4 Entity / EntityAlias / Event

Entity：entity_id、entity_type、canonical_name、ecosystem、canonical_external_id、visibility/tenant_id。

EntityAlias：alias_id、entity_id、alias_text、alias_kind、source_span_ids、valid_from/valid_to、status。硬标识冲突时不自动合并。

Event：event_id、event_type、title、external_ids、primary_product_ids、first_seen_at、status。一个多漏洞报告可以关联多个Event；不能因为文章同时出现两个CVE就把两个CVE合并。

漏洞别名、上游关系和普通相关关系分开。OSV中的相关对象不能全部转换成等价别名，版本字段按官方语义解析[S09]。

### 3.5 Claim / ClaimEvidence / EnrichmentResult

Claim：claim_id、event_id可选、subject_id、predicate、object_value（受predicate限定的联合类型）、condition_scope、origin、status、valid_from/valid_to、recorded_at、superseded_at可选、extractor_version、source_revision_id、visibility/tenant_id。

ClaimEvidence：claim_id、span_id、support_kind(supports/refutes/context)、validation_status。

相同对象、谓词、范围与时间下的冲突并列保留；复制同一来源的转载不构成独立多数。`human_confirmed`仍必须有证据和核验记录。

EnrichmentResult：event_id、dimension、status、claim_ids、reference_ids、error_code、searched_at、source_scope、last_job_id。每个维度独立状态。无CVE论文没有CVSS可以not_applicable；适用维度尚未发现信息是not_found，接口失败是failed/blocked。

### 3.6 VersionRange / PublishedRule

VersionRange：ecosystem、package_key、scheme(pep440/semver/osv_ecosystem/git)、intervals、excluded_versions、source_span_ids、supported_comparison。

Interval：introduced可选、fixed可选、last_affected可选、explicit_versions可选、branch可选。不得把fixed的右开边界改成包含；无法比较的scheme返回unknown，不按字符串或git hash比较。

PublishedRule：rule_id、version、event_id、rule_kind(software_applicability/observed_path/research_prerequisites)、condition_ast、supporting_claim_ids、source_span_ids、status、validation_record、published_at、retired_at。

AST仅允许all_of/any_of与类型化叶节点，见04。不得执行Python、SQL或模型生成表达式。规则模板和schema可预先审核，能通过明确发布策略的结构化规则可以自动发布；新谓词、无证据条件或争议规则进入审核池。自动化不等于跳过有效性校验。

### 3.7 Asset / AssetSnapshot / Component / AssetObservation

Asset：asset_id、tenant_id、display_name、criticality、current_snapshot_id、active。

AssetSnapshot：snapshot_id、asset_id、tenant_id、snapshot_number、observed_at、recorded_at、source_kind、inventory_completeness(complete_for_declared_scope/partial/unknown)、declared_scope、components、configuration、tool_permissions、input_channels、network_exposure、snapshot_sha256。

Component：component_id、ecosystem、package_name、purl可选、version可选、version_scheme、image_digest可选、dependency_path可选、source_field_locator。组件未列出只有在清单对该范围完整且有效时才可支持“不存在”。

AssetObservation：observation_id、provider、provider_record_id、retrieved_at、observed_at可空、ip/domain/port可选、product_evidence、version_evidence、ownership_mapping_status、authorized_scope_id、raw_reference、tenant_id。请求时间不能冒充平台观察时间；外部观察不自动证明资产归属。

### 3.8 ConditionEvaluation / Assessment

ConditionEvaluation：node_id、value、reason_code、evidence_ids、asset_field_refs、child_results、observed_conflict_ids。对父节点无决定作用的冲突仍保留在审计信息中。

Assessment：assessment_id、tenant_id、asset_id、asset_snapshot_id、event_id、rule_id/rule_version、knowledge_epoch、scope_epoch_map、rule_result、status、freshness、evaluation_tree、missing_requirements、conflicts、exposure_result、exploit_evidence_status、created_at、superseded_by、input_digest。

唯一执行键包括asset_snapshot_id+rule_version+input_digest+任务策略版本。只有比较所用快照仍有效才能把结果设为current。未支持规则必须返回unsupported_rule/insufficient_evidence，不能通过LLM猜状态。

### 3.9 Dependency / ScopeWatch / ChangeEvent

Dependency：derived_type、derived_id、input_type、input_id、input_version。

ScopeWatch：derived_type、derived_id可选、watch_kind、tenant_id、package_keys、product_ids、event_ids、time_scope、query_fingerprint、created_epoch。包括空答案、未命中资产和此前无相关事件的订阅。

ChangeEvent：change_id、change_type、changed_ids、affected_scope、before_version、after_version、knowledge_epoch、occurred_at、recorded_at。

旧引用依赖和潜在相关范围必须都建索引。无法界定影响范围时保守扩大到相关分区，不能为了省计算漏掉新增命中。

### 3.10 JobRun / OutboxEvent / Investigation / ToolRun

JobRun：job_id、job_type、tenant_id、idempotency_key、input_digest、status、attempt_count、lease_owner、lease_expires_at、started_at、finished_at、error_code、result_ref、trace_id。

OutboxEvent：outbox_id、event_type、payload_ref、created_at、published_at、delivery_attempts。与业务改变同事务写；消息发布失败不丢事件。发出后宕机可能重复投递，消费者必须幂等。

Investigation：investigation_id、tenant_id、user_id、request_scope、snapshot_refs、status、budget、remaining_budget、graph_version、thread_id、stop_reason、result_ref。

ToolRun：tool_run_id、investigation_id、tool_name、call_key、input_digest、policy_version、status、attempts、started_at、finished_at、result_ref、evidence_ids、cost_record、error_code。调用参数需脱敏；工具结果权限不宽于输入。

外部调用在宕机边界可能重复且计费。不能宣称exactly-once付费调用；先预留预算，已确认结果可复用，结果不明时保守计入消费或人工核实。

### 3.11 Conversation / Answer / Subscription / Recommendation

Conversation绑定tenant_id和user_id，每轮重新认证。历史对话不能作为权威证据。

Answer：answer_id、conversation_id、question_id、structured_claims、rendered_text、evidence_ids、assessment_ids、query_scope_watch、knowledge_epoch、asset_snapshot_refs、model_version、prompt_version、data_mode、status、freshness、generated_at、completed_at、latency_milliseconds。

缓存键至少包含租户、用户权限版本、问题规范化结果、会话上下文摘要hash、知识/资产/规则版本、模型与提示词版本、时间查询范围。空答案也有scope watch。

Subscription：subscription_id、tenant_id、user_id、product_keys、asset_ids、risk_topics、minimum_priority、enabled。

Recommendation：recommendation_id、subscription_id、event_id、assessment_id可选、reason_codes、evidence_ids、priority_bucket、freshness、change_id、created_at、read_at。幂等键为subscription+事件+实质变化版本；不是每次轮询都提醒。

## 4. 数据库最低约束与索引

唯一：source+source_record；document+revision_number；asset+snapshot_number；事件外部ID映射；job_type+tenant_scope+idempotency_key；tool call_key；recommendation幂等键。

索引：claims(subject,predicate,status)；asset components(package_key,tenant)；rules(package_key,status)；dependencies(input_type,input_id)；scope_watch(package_key,tenant)；jobs(status,lease_expires_at)；outbox(published_at,created_at)。tenant参与私有唯一键和查询索引。

不可变历史采用新增版本和状态转换；不能无迁移删除旧字段。外键和检查约束拒绝跨tenant引用；复杂跨范围校验在服务层与集成测试实现。

## 5. 序列化与迁移

Pydantic输出schema→保存JSON Schema→API生成OpenAPI→前端生成或维护严格匹配类型。不要手工创建两套不同枚举。

迁移使用Alembic。测试空库升级、上一版本升级、备份恢复；有数据的破坏性downgrade不自动执行。新增默认值不能改变既有unknown语义。
