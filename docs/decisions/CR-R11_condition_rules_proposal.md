# R11 / T27 纯条件切片与 PostgreSQL 窄接线提案

状态：proposal；本文件不批准公共 schema、生产迁移、认证或产品发布变更。实现切片仅 awaiting_review，G-D 独立准备，未阶段放行。基线 e310f7735bd499c4d9fbcefe8a644e2309a16a62。

## 合同与内部输入输出

03 §3.6、§3.7、§3.8 与 04 W06/W07 保持原语义。实际 `domain/records.py`、`contracts/schemas/` 中没有既有 ConditionNode 或 PublishedRule DTO；本切片在 `assessment/conditions.py` 和 `assessment/rules.py` 建独立内部类型，不改变公共 schema。叶节点覆盖 component_matches、version_in_range、configuration_equals、permission_includes、input_channel_enabled、network_reachable、inventory_proves_absence、mitigation_confirmed；组合只接受 all_of / any_of，根深度为 1，上限 8，总节点上限 64。

- `parse_condition_tree(raw: str | bytes | Mapping[str, object]) -> ConditionNode`：discriminator 为 kind，node_id 是树内唯一定位符；重复 JSON 键、循环/共享节点、未知谓词、额外表达式字段及空组合拒绝。16 MiB 原 JSON 限制和 50000 个 JSON 标量/容器预算覆盖 64 节点内已有受限版本字段的最大容量；JSON 字段数不等于 AST 节点数。
- `evaluate_condition_tree(condition, asset_snapshot: AssetSnapshotResponse, *, access_scope, supporting_facts=(), rule_kind="software_applicability") -> ConditionEvaluation`：只读授权固定快照；value 使用已有 ConditionValue，保留所有 child_results、asset_field_refs、evidence_ids、observed_conflict_ids、missing_requirements、limitations。服务端认证构造 AccessScope；纯函数只核对提供的范围，不读取 PG，不证明实际来源 ACL。
- `ConditionFact`：只表示指定 asset_snapshot_id 上的 typed 缓解观察，不是事实账本。包括 claim/status/origin/condition_scope、source_id/document_id/source_revision_id、scope 与 EvidenceReference。model_hypothesis、unverified、withdrawn、superseded 不确认；disputed 与互斥支持并列保留。厂商说缓解有效不能单独证明资产已实施缓解。调用者必须确认快照关联与来源支持。
- `ConditionRule`：rule_id/version/event_id/rule_kind/condition_ast/supporting_claim_ids/source_span_ids/scope/status/published_at/retired_at。status 复用现有 RuleStatus。validation_record 由下述 PG 验证收据保存，不复制为第二套事实状态。
- `validate_rule(rule, *, access_scope, policy: RuleValidationPolicy, supports: tuple[RuleLeafSupport,...]) -> RuleValidationResult`：叶支持绑定 node_id + 精确 condition_sha256；返回 eligible、automatic_publication_eligible、resulting_status、missing_requirements、conflicts、pending_review、policy/schema/validator/rule 版本与完整 source_supports。eligible 仅允许验证，函数不发布、不造人工 approver。
- `evaluate_rule(rule, snapshot, *, access_scope, supporting_facts=()) -> RuleEvaluation`：只接受 published 生命周期输入；四态映射已有 AssessmentStatus，rule_kind 和限制字段保留。PG 调用者须先后核对当前有效性。

三个 rule_kind 分别评估，不合并为“安全”或“利用成功”。software_applicability 中 network_reachable 永远不决定软件修复/安全状态，并阻止此类规则取得发布资格；observed_path 中网络声明只能决定已建模路径，research_prerequisites 匹配只说明前提。没有网络探测或 PoC 执行。

版本叶复用 `assessment/version_ranges.evaluate_version_assertion`，不改变依赖或生态支持。当前成熟比较只支持 PyPI/PEP440 与 npm/SemVer；Go/generic 的 Ollama 等输入继续 unknown，并记录 unsupported_ecosystem，不作排除。规范快照没有维护分支或回补确认字段，执行器不猜这些信息；版本引擎的未决结果传播。

## 0021 生产迁移与调用者提案（由 root 独占实施）

以下是窄 IO 约束，不是已实现 PG 验证；0021 号由 root 预留，本切片不创建 migration/Table。

规则版本记录保存 rule_id/version/event_id、scope、schema_version、condition_ast、condition_sha256、status 与生命周期时间；AST 内容发布后不可变，语义改变新增规则版本。验证收据保存 validator_version、policy_version、input_digest、knowledge/scope epochs、source 支持快照、missing/conflict/pending_review 及验证时间。支持关系按 rule_id/version/node_id/condition_sha256/claim_id/span_id/source_revision_id 绑定到现有事实/证据，不另建事实真相。审计收据内的状态是当时输入，当前状态仍回查现有 PG claims/evidence/documents。

PG 发布窄入口：服务端提供 AccessScope、固定 ConditionRule、版本化 RuleValidationPolicy；仓储读取支持关系，并组装 RuleLeafSupport。事务内必须逐项确认：

1. 来源、文档、修订配对真实，修订状态可用且满足当前性策略；claim 属于指定事件/必要条件，claim_origin/status 合规，condition_scope 与 rule_kind 相同。
2. span 位于指定 revision/block，Unicode code point 左闭右开范围合法，规范 block 子串等于 quote_text，quote_sha256 相符；真实位置核验与“支持该必要条件”两项分别确认。纯接口的布尔标记不能替代数据库/人工支持校验。
3. rule scope 不宽于 claim、span 与所有来源；tenant 记录同租户，public 规则不能引用私有来源。模型不得提交 tenant、policy 或权限字段扩大范围。
4. 每个必要叶有绑定其精确摘要的来源支持；range_complete=True 要有独立范围完整性证据。无证据、争议、未核验引用或未批准谓词留 candidate/pending_review。
5. 自动发布仅在服务端已批准 schema/谓词/策略且 automatic_publication_eligible=True 的范围进行；人工策略需要真实授权审核记录，不从 fixture 或模型生成 approver。纯验证只产 validated，published/retired 写入由事务负责。
6. 同事务写生命周期/验证记录、scope epoch 与 outbox；来源修订/权限/策略在提交前变化则重新验证或保留 stale，不让旧结果成为 current。retired 历史保留，恢复需新的规则版本。

T28 读取授权 published 规则、指定快照、必要源事实，调用 evaluate_rule；PG 证据包组合规则收据、节点树、来源坐标、资产快照字段、版本/epoch 与 input_digest。提交前再次比较所有输入有效性，不能仅信任纯函数结果或生命周期字段。API/worker/前端接线、真实 PG/并发重判/源文本 ACL、OpenVEX 和 3→5 个产品真人金标均留相应后续切片验证。
