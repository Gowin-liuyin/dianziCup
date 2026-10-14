# R02 · 持久化准备与接口草案（不生效）

创建：2026-10-15T01:41:10+08:00（Asia/Shanghai，真实系统时钟）；本轮第一个已采集时间戳：2026-10-15T01:34:14+08:00。结束时间及最终只读核对见 `../runs/recovery_r02_preflight_20261015/completion.json`。主控委派：`/root/r02_persistence_preflight`。

**结论：可以准备可实施的最小接口与回归输入，但不能登记 R02 持久化通过。** 本报告只完成源码、合同、调用方和验收准备；R02 产品实现仍 `not_started`，unit/contract/integration/security/frontend/e2e/live/manual 均 `not_run`。本报告待主控冻结，未修改 `progress/task_state.json`，未签 `accepted`。

开始时主控交接说明 R00 已接受、真实 PG 可用，R01 已取得 runtime 与三条 UI 链证据，但 G-A/R01 仍有 base TLS、tmpfs 与 CR-R10 范围待解决，原前置没有整体放行。报告交付前主控另告知已冻结 TLS 修复 `f497865`，并将质量四提交集成到 `37277dfdc797522b2010d2f4cd160c7d03f73644`；坐标、payload重放与epoch竞态将由主控纳入统一接口冻结。本报告未扩展源码审查到新SHA，也未收到前置整体接受结论。这些资源与runtime/修复结论来自主控交接，本分析没有独立复跑，不能作为本报告的PG、MinIO、业务链或产品通过证据。冻结快照中的R01状态仍是早先 `in_progress/not_started`；状态索引与最新证据的时间差不以本报告改写。

## 1. 本轮边界与冻结对象

- 只读源码：`C:\Users\yinha\.codex\worktrees\recovery-r01-recheck-final\dianzi`。HEAD 为 `d30eeab1d723080decea5f64a992b909a0d834c2`；Git tree `86162477cdeea61cfb94b501bc6d8e427efaf1bb`；`backend/src` tree `0ad74ab5e158d1a6fb0df3e875df3b5c7435dc13`。
- 主仓初查：`D:\dianzi`，分支 `codex/full-delivery-recovery`，HEAD `b504c2376142c6557ac3cfa7c42ffe2baa0dbca4`，存在主控/审查者未提交修改。没有 reset、checkout、stash、清理、提交或 push。
- 冻结 worktree 进入时已有 `M frontend/tsconfig.tsbuildinfo`，未触碰；本轮不操作其 HEAD、index 或 tree。
- 唯一写入：本文件与 `reports/runs/recovery_r02_preflight_20261015/` 的命令元数据、图结果、文件 blob ID 和完成收据。未保存完整 source 副本；图 cache 位于仓库外 `/tmp/dianzi-r02-preflight-20261015/cache`。
- 没有改 models、迁移、schema、锁、业务、测试、金标、阈值、分母或状态；没有读 KEYS、`.env`、DPAPI、秘密参考附件或 holdout；没有付费调用、下载模型、运行 PoC、操作第三方资产或创建用户侧聊天。

已读依据：AGENTS；00 执行地图；恢复 11 的 R02 相关架构/原文/富化条款、12 的 R02；03/04/05/06；原 T04/T05/T06/T17/T19/T21 全部 C01–C06；CR-R02/04/07；09 运维合同与既有交接。Ponytail full/review 使用安装路径 `C:\Users\yinha\.codex\plugins\cache\ponytail\ponytail\5.2.0\skills\ponytail\SKILL.md` 与同包 `ponytail-review\SKILL.md`，最小完整改动优先，不添加万能仓储或重写模块。中文报告遵从本轮明确交付要求。

## 2. 真正读取的调用链与可复用能力

官方可执行文件 `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp` 的真实 `--help` 显示版本 `0.11.0`；随后真实读取 `index_repository/search_graph/trace_path/query_graph --help`，使用 fast 模式、`persistence=false`、显式 `CBM_CACHE_DIR` 与 `CBM_ALLOWED_ROOT`，只索引冻结目录的 `backend/src`。结果为 539 nodes、2038 edges，parse_partial/unusable/skipped/not_indexed 均 0；这是工具索引结果，不是业务测试数或覆盖率。

对 login、authenticated_session、validate_write_request、reserve、audit、publish_claims、apply_claims、merge_events、save_document_revision、bump_scope_epoch、enqueue_job 做入/出方向两跳 trace。日志见 `cbm_traces.json`；随后 `rg` 遍历 backend/src、backend/tests、scripts 并阅读源码。图的 login/validate_write_request 入边为 0，但真实 HTTP 闭包调用存在，证明**图无边不能证明未接线**。未依赖图结果替代动态闭包、SQL 调用和测试调用的源码核实。

| 现有位置（冻结源码行） | 入/出链核实 | R02 复用或边界 |
|---|---|---|
| api/app.py:33–54 | 默认 create_application → DatabaseUserDirectory(engine) → AuthenticationSessionService；auth_routes 注册 /v1 与 /api/v1 | 默认只用户目录接 PG；会话、限流、审计尚未接 PG。保留路由与目录，不另建认证 |
| api/auth_routes.py:42,95,138,165 | login → service.login；me → authenticated_session；csrf → session_record；logout → validate_write_request → logout | 现有 Cookie、CSRF 响应、错误映射与刷新行为要保持；不要改坏已经取得的 UI 证据 |
| api/authentication.py:205–210,226–366 | sessions/attempts/audit 为进程 dict/list；reserve 先于目录与 Argon2；成功只释放自己的占位 | 共享后端需保持失败+在途计数和一次身份/CSRF 快照，线程 Lock 不能代替多进程锁 |
| api/app.py:75–88 | 请求校验拒绝自报 tenant/role 等字段 → record_identity_spoof_attempt | 新审计持久化是实际调用方；只记字段名，不记值 |
| scripts/admin_user.py | 直接使用 build_engine/session_scope/users 插入 PG，密码经环境/无回显输入 | 复用预创建账户与 Argon2，不增注册/默认账户，不运行此 CLI |
| knowledge/claims.py:45–120 | ClaimsLedger 仅被 test_t21 导入/实例化；发布追加 list 并返回 transactional:true | 替换业务权威；原 dict 只能保留为明确 fixture，不能登记真实事务 |
| knowledge/entities.py:15–56 | canonicalize/can_merge/resolve_alias 仅 test_t21 调用 | 保留正确纯判断，entity_key 是规范键而非稳定 UUID；alias 只有 source_record_id，尚无证据 FK |
| knowledge/event_linking.py:28–81 | EventLinkingLedger 仅 test_t17；merge/undo 追加列表 | 持久化操作历史、版本和影响事件；不要由来源/文章顺序生成产品主键 |
| enrichment/structured.py:28–83 | EnrichmentLedger 仅 test_t19；apply → dimension_status_for_kind | 保留适用性与明确部分成功判断，新增事务仓储；不要把 in-memory input_fingerprint set 当并发幂等 |
| revisions.py:78–152,186–253 | tests/integration/test_t05 使用真实 Session；save → ContentStore.store_bytes；attach 关联 revision/block | 可复用现有 PG 保存、不可变原文字节、证据检查和 rollback 边界；没有生产采集调用方的证据 |
| revisions.py:278–296 | bump_scope_epoch 当前 select 后 update/insert；tests/T05 使用 | 原子递增后复用；不能在并发中丢 epoch |
| infrastructure/database.py | session_scope 显式 commit/rollback；迁移由 Alembic upgrade；engine 强制 PG | 采用同一 Session，仓储内部不 commit；不用 SQLite 或内存代替并发集成 |
| infrastructure/outbox.py:21–79、knowledge/models.py | jobs/outbox 已建，enqueue_job 与 outbox 同 Session；job_id 是 outbox 必填 FK | 复用表；业务发布须有真实变更/负载引用及 scoped 幂等，不能仅追加另一套消息 list |
| migrations/0001:89–107；models.py | claims SQL 表已存在；knowledge/models.py 尚未映射 claims | **增量扩展已有 claims**，不可另建第二个默认事实库 |

`test_t21_claims_entities_conflicts.py` 尽管位于 integration，实际只创建内存台账；T17/T19 也是纯逻辑。其历史通过记录不能当真实 PG、跨进程或可重启通过。当前没有生产 claims/events/enrichment HTTP 调用链的源码证据，本报告不虚构已接通的搜/导出端点。

## 3. 已证实缺口、合同缺测与待验证假设

### 必须处理的已证实源码缺口

1. **公共 scope/状态有两个合同。** knowledge/claims.py 的 ClaimRecord 使用 `tenant_id: str`，accept private，默认 current，并处理 published/hypothesis；domain/records.py:69 使用 ClaimStatus 与 VisibilityScope，后者只 public/tenant 且 public tenant=null。例：test_t21 的 public+t1/current 被旧台账接受，但 canonical DTO 应拒绝。按 03 §1/§2、CR-R04 不能默默删 tenant 或把 current 无条件映射 supported。
2. **事务与历史状态不真实。** publish_claims 只过滤内存对象、追加 dict，未写 PG、未增 epoch、未更改发布状态；register_supersede 仅存元组，旧 claim 仍可 query_public_current。例：旧/新均 current，register_supersede 后当前查询仍返回旧值。最小修复是有锁的单 Session 发布与状态历史，不重写所有纯逻辑。
3. **幂等先标记后处理。** structured.py:35–51 先加入 fingerprint，再逐条调用维度判断/append。例：第二个候选的维度解析失败或未来持久化 insert 失败，重放相同 fingerprint 会跳过并丢第二条。字段 duplicate 还仅比 value+source_record_id，不区分同 source 的 revision、scope、json_path、评分机构。幂等收据必须在业务提交成功的同一事务内写。
4. **并发 epoch/修订缺原子操作。** 两个事务读 epoch=5 后均写6，第二个变更没有独立新 epoch；两个 save_revision 可同时读相同 tip/max，唯一约束会让一方失败，尚无序列化后同输入复用结果。复用函数中增加原子 upsert 与 document 父行锁；已有 uq_revision/current 作为最后保护。
5. **证据坐标串接有歧义。** evidence.py 的 locate 返回 block.start_offset+position，attach_evidence_span 却直接 block_text[start:end]。block 起点100、引文块内位置2时，locate返回102而 attach按块内102校验，不能直接组合。03 §1/§3.2描述规范全文坐标，§3.3又写 block.text[start:end]，须主控明确全局/局部字段与兼容规则，不能静默改变旧证据。
6. **内容 hash 不是事件同一性。** event_linking.py:52–59 对非空相同 body_fingerprint 返回 merge=True。例：一文两个不同 CVE，拆成两事件后共享同一文章指纹，should_merge会归并，违反 T17-C05/W03。R02 持久化不能把这个 fallback 升为发布条件；应只用于内容去重/候选，硬标识冲突阻止合并，业务关系判断交 R04/R10 对应切片。
7. **维度命名/类型尚未完整。** dimensions.py 只有六个旧名且使用 research_paper 等旧 kind 字符串，domain.DocumentKind 为 paper/advisory 等；schema object_value 是字符串，03 §3.5要求 predicate 限定联合类型，而两处旧 Claim.value 是 object。不能把整条 Claim dump 到 JSONB 解决。九维主实现仍属 R07，本轮提出存储和指纹合同供它使用。
8. **outbox 引用尚非业务重放收据。** enqueue_job 只存 payload SHA256 到 payload_ref，源码没有同时保存 payload bytes。R02 若直接调用并宣称能够重放事实变化，会缺读取材料。需真实 ChangeEvent 行引用/不可变 payload 与明确读取协议；R03 接消费者，仍复用 jobs/outbox 表。

上述为源码与合同对照，不是本轮运行失败或线上漏洞已复现。认证共享问题的具体场景是 A 进程签发会话后 B 进程/重启进程的 `_sessions` 为空而拒绝；限流在不同进程分别占位，突破统一 5 次窗口。源码可证明状态生命周期，但本轮没有启动双进程实验。

### 合同缺测与假设（不写通过）

- 缺测：真实重启读取、事务中间故障、PG 串行化/唯一键竞争、跨租户读/搜/导出、旧库 provenance 保留、对象 GC 与发布竞争、状态重放、schema 适配。现有纯台账测试覆盖不足，不通过改名变成 integration。
- 未独立验证：本机 PG 状态与容量、MinIO 服务/账号/bucket/依赖版本/读写能力、备份恢复、真实来源/模型新鲜度。MinIO 已批准采用但未核实版本或资源，不能填写版本、资源值或 live=passed。
- 不推断：全产品权限已通过、九维已建成、搜索/图投影可用、达95%或≤6h、持续运行跨度、对照提升。未读取盲测，不设计降低阈值的替代。

## 4. 建议冻结的最小接口（均为草案）

调用层统一接认证构造的 `AccessScope`、同一 request/job Session 和类型化输入。纯判断与 IO 分离。仓储直接实现具体业务操作，最多显式 Protocol 用于 fixture/PG 两个后端；不加 BaseRepository、通用 CRUD、可执行 SQL/URL 接口或新的业务框架。

| 接口草案 | 输入/输出与原子边界 |
|---|---|
| `reserve_login_attempt(client_key_hash, now) -> attempt_id` | PG 锁定单 client bucket 后清理已过窗口占位、计 failed+inflight；已达5拒绝；独立短事务先提交再做目录/Argon2 IO。客户端 key 沿用路由获取的受控 client.host，不信任转发头 |
| `complete_login_attempt(attempt_id, session_record, audit_event)` | 成功在同事务存 session hash+CSRF、只释放本 attempt、写脱敏成功审计；失败把本 attempt记failed并写失败审计；异常保守保留至窗口过期，不清别人的失败/在途 |
| `load_authenticated_session(session_hash, now) -> (Principal, SessionRecord)` | 单查询 join有效session与当前users；expiry/revoked/user缺失拒绝。保持 me/CSRF 同一身份快照；role/tenant取 PG 用户，不从请求或缓存复写 |
| `revoke_session(session_hash, now, audit_event)` | 幂等撤销并写审计。写业务需在其事务内再验证未撤销/权限，不只沿用早先 HTTP 校验 |
| `list_audit_events(scope, cursor, limit)` | 明确 READ_AUDIT 和 tenant过滤、稳定分页；旧 audit_events() 只供显式内存 fixture测试，不能作为无scope数据库导出 |
| `find_or_create_entity(session, scope, canonical_key, identifiers) -> entity_id` | 稳定 UUID 与规范key分离，同scope唯一；正确生态、类型与硬标识冲突拒绝；无CVE后补CVE不换ID |
| `add_entity_alias(session, scope, alias, evidence_ids, valid_range) -> alias_id` | alias出处指向已校验证据/revision；非空source_record_id本身不等于alias已核验；受限模糊只存 unverified候选 |
| `save_claim_candidates(session, scope, canonical_claims, source_assertions, evidence_links) -> candidate_ids` | 冻结 DTO/enums 校验后保存候选，证据存在/定位与语义支持分开。私有输入不能产公共衍生记录；不commit |
| `publish_knowledge_change(session, scope, expected_versions, publication_key, claims, relations, status_changes) -> PublicationReceipt` | 先验证整个批次，锁业务版本/相关scope；写事实、证据关系、source assertions、状态历史、relation/event操作、ChangeEvent、scope epoch和jobs/outbox一起提交。失败抛明确错误，任何一半不可见 |
| `apply_enrichment_batch(session, scope, event_id, revision_id, dimension_results, fingerprint) -> BatchReceipt` | 每维值/状态/新鲜度/来源/错误独立，失败维度不覆盖成功可信值；预先判定的部分成功结果与已成功事实作为一个完整批次提交。SQL失败整个发布事务回滚；partial不是允许半事务commit |
| `read_current_claims / read_claim_history / read_event_relations(session, scope, query)` | 当前与历史明确，返回canonical状态、固定revision/evidence、版本/epoch；每个读/搜候选/导出共用同一授权和有效性检查，不能查全库后只在渲染层过滤 |
| `store_bytes/read_verified/delete_unreferenced` | 沿用内容 hash接口；MinIO实现返回 object_key而非本地Path，仅调整具体 StoredObject合同。存不可变bytes后写metadata；引用对象不能覆盖或删除 |

PublicationReceipt 最少：`change_id, business_version, changed_claim_ids, changed_relation_ids, scope_epochs, job_id, outbox_id, reused`。相同 publication_key+同输入返回原 receipt；相同key+不同digest返回409语义。任何 receipt只在commit后作为成功给调用方；不以 transactional:true 代替数据库证据。输入的 expected_versions 来自授权读，不由模型选择任意版本绕过CAS。

### 必须显式冻结的适配

1. 用现有 `domain.enums` 的 ClaimOrigin/ClaimStatus/ConditionValue/DimensionStatus/FreshnessStatus、`VisibilityScope`、`Identifier`、`UtcTimestamp`；DTO扩展由主控完成。现有 domain ClaimRecord.object_value 仅str与03所需union冲突，不能偷偷用 `Any/cast/ignore` 穿透。
2. 旧 knowledge ClaimRecord 仅作为旧fixture DTO明确隔离。`explicit`需有来源定位才映射source_explicit/structured_source；`hypothesis`映射unverified，model_hypothesis保持来源；current/published不是canonical状态，没有独立支持核验不得映射supported。
3. 旧public+tenant=t1不能简单清tenant来提升为全局公开；private也不能无认证改为tenant。默认拒绝业务导入，保留原scope与错误记录；必要的历史兼容导入需有明确scope/provenance映射与审核结果。
4. 旧 effective_at 无时区字符串不能猜UTC；无证据ID的文本不能伪造EvidenceSpan。既有SQL事实的subject/value/time/unknown原样保留；新增 provenance为空时不得变为“已支持”，需按主控冻结的 legacy来源/可用性标识读取，不凭空补引用。
5. DocumentKind旧别名到canonical映射、九维ID/predicate/value union、alias状态、证据全局/局部坐标、ChangeEvent/payload_ref读取协议都需一次冻结，并带正负schema样例。报告不是新批准变更单。

## 5. 表、索引与迁移草案

唯一公共schema/models/Alembic编号所有人是主控。已确认末版 `0005_runtime_observations`，只建议下一迁移为 `0006_auth_state`；后续事实迁移名称/编号由主控分配，子任务不得抢号。本节未生成或运行迁移。

### 5.1 认证 0006 增量建议

| 表 | 必要列与约束 |
|---|---|
| auth_sessions | session_hash CHAR(64) PK（仅hash，不存原session token），user_id FK users，created_at/expires_at/revoked_at timestamptz，csrf_token敏感服务器字段，schema_version；expires>created；expiry/user索引 |
| auth_login_buckets | client_key_hash CHAR(64) PK、created_at；作为同client行锁锚点。不存username/password/token，不增第二套用户目录 |
| auth_login_attempts | attempt_id UUID PK、bucket FK、reserved_at/expires_at、state=inflight/failed；bucket+expires索引、expires>reserved。成功只删除/结束自己的attempt；失败+在途均计数，原5次/900秒门槛不变 |
| auth_audit_events | audit_id UUID PK、event_type白名单、occurred_at、trace_id非空、user_id可空、tenant_id可空、reason_code、submitted_keys受限数组、schema_version；tenant/time/id索引，append-only。无通用任意fields JSON与凭据值 |

CSRF 当前 me/csrf接口需要在刷新/另一进程返回同会话绑定值。最小兼容草案是仅在服务器 PG 敏感字段保存 csrf随机值并保持compare_digest，禁止日志、普通审计和前端持久存储；session bearer始终仅存hash。若主控选择CSRF digest-only，必须同时冻结安全的取值/轮换协议并复跑多tab/刷新链，不能hash后让现有GET接口无值可返，也不新增自制加密。这个选择尚未生效。

成功登录发行session/释放自身attempt/成功审计同事务；错误账户与错密码统一invalid_credentials+失败审计；数据库失败返回既有503，不能 fallback内存。reserve短事务不把锁跨越Argon2。进程崩溃遗留inflight按原有限窗口保守计数；用统一数据库时钟避免两API进程时间偏差。敏感查询不把SQL参数、DSN、hash或CSRF写JUnit/日志。

### 5.2 后续事实增量建议

| 现有表/新增表 | 明确业务列、索引与约束 |
|---|---|
| entities + entity_identifiers + entity_aliases | UUID entity_id；entity_type/ecosystem/canonical_name/canonical_key/外部ID/scope/schema_version。public规范键唯一与tenant规范键唯一用两个部分唯一索引，避免NULL tenant导致重复；tenant参与私有键。identifier/alias保留source assertion与evidence FK、valid_from/to、ClaimStatus；硬ID不相交不能合并 |
| events + event_external_ids + event_documents | 稳定event UUID、event_type/title/first_seen/status/scope/schema_version；公开ID规范映射在scope内唯一；一document_revision可关联多event；来源版本、同源组、内容hash不当事件身份。后补CVE只增加external映射 |
| 扩展既有 claims | 保留subject/predicate/object_value/claim_status/origin/condition/freshness/时间/scope。增event_id可空、subject_id、condition_scope、source_revision_id、extractor_version、rule_version可空、claim_family_key、business_version、valid_from/to、recorded_at、schema_version、value_type与受predicate限定value字段。来源/core ACL/status/time/版本不得藏JSONB；JSONB仅可存已冻结的嵌套值union，校验其discriminator，不dump整Claim |
| source_assertions + claim_evidence | assertion_id/claim_id/source_id/source_record_id/document_revision_id、来源明示值、origin、有效范围、提取/规则/模型版本、scope、schema_version。claim_id+evidence_id+support_kind唯一；evidence FK，支持supports/refutes/context，validation_status与verified_at/validator_version。出处、引文存在、语义支持分别记录 |
| claim_status_history + claim_supersedes + claim_disputes | append-only状态转换 from/to/reason/actor/recorded_at/来源修订；旧→新FK、scope/subject/predicate/来源修订约束；dispute保留两方、相同条件/时间范围和核验理由。当前status只是同事务维护投影，historical查询按known_at重建，不覆盖旧值/原文 |
| relation_versions + event_operations | relation_id/业务version/relation_type/from/to、source_revision_id、evidence IDs关联表、rule_or_model_version、reason、ClaimStatus、scope、时间/schema_version。merge/undo/split为不可变operation，撤销引用原operation且幂等；已确认/候选分开。六类自动产生逻辑仍由R10建设 |
| enrichment_results + enrichment_claim_refs | event/revision/dimension、DimensionStatus、FreshnessStatus、searched/observed时间、source_scope、last_job FK、error_code、policy/extractor/model/source版本、input_fingerprint、scope、schema_version；每维独立状态与claim/reference关联，不只存job字符串 |
| publication_receipts + change_events | scope+operation_kind+idempotency_key唯一，input_digest、business_version与已提交receipt字段；change_type/changed_ids/affected_scope/before_after_version/occurred/recorded、epoch。与facts/status/relations/epoch/jobs/outbox同事务；无跨进程内存收据 |
| 既有 scope_epochs/jobs/outbox | scope包含public或tenant和产品/包范围，不信任请求体；epoch>=0，原子upsert递增RETURNING。复用jobs/outbox并明确ChangeEvent真实引用读取。现job幂等键全局unique：短期用确定性scope+operation+主体编码键并核对digest，后续R03增量规范复合唯一，不无声改现有幂等语义 |

新增 claims 查询索引为 `(visibility,tenant_id,subject_id,predicate,claim_status)` 与history/source_revision索引；business version唯一包含逻辑 family与scope；source assertions唯一覆盖来源revision、subject/predicate/condition、origin、值fingerprint；不能用整个历史hash唯一阻止A→B→A。private FK/证据scope在服务与PG约束共同检查，跨范围复杂约束需可执行integration，不因单列FK存在就称跨tenant已拒绝。

九维 fingerprint 输入冻结建议：`scope + event_id + document_revision_id + dimension + source_id/source_snapshot_version + scoring_authority + extractor/rule/model/prompt/schema/policy_version + normalized_input_digest`。并列机构、分支与出处不同不能相互覆盖；同revision同输入幂等，修订后的相同内容也有不同revision输入；原九维为 CVSS/EPSS/KEV/CWE/ATLAS/affected-fixed versions/literature/PoC-template existence/public exposure aggregates，机制/修复建议/政策卡另保留。未实现某维不可把status设available；适用而缺失为not_found，provider失败为failed/blocked，unknown不可置0。

### 5.3 升级、事务和失败恢复

1. 空库upgrade到head与0005已有数据upgrade分别测试。先备份并校验样本；新增列先可空/兼容旧读，按有依据的映射回填，再验证约束。旧未知、事实文本、时间、hash、原文与证据不删除；没有provenance的旧行不能编造source/evidence，未能转换明确隔离与可读历史。
2. 同document修订先锁父行，末版hash相同复用；A→B→A第三行新UUID/new revision_number，不复用第一版revision身份。content_objects插入用hash唯一+ON CONFLICT并核对尺寸，不能 SELECT→INSERT竞态冒充成功。
3. 单发布在锁定顺序中先取得document/claim family/event，再按稳定scope key顺序锁epoch，校验expected版本；claim/value/history/证据/关联/change/receipt/job/outbox一次提交。并发相同key只有一commit，失败的一方rollback后读原receipt并比较digest；不同digest明确409。
4. `supported/disputed/unverified/superseded/withdrawn` 使用canonical状态；明确自修订只supersede该source assertion/相应claim，其他来源主张仍并列。source404只更新fetch状态；撤回需明确撤回证据/核验记录。当前读不返回superseded/withdrawn为有效，historical仍可按recorded/valid时点读旧原文。
5. 规则/事实改动引起scope epoch；scope需覆盖旧命中、新命中与旧空结果，R02保存change受影响范围供R16消费，不能只沿旧evidence引用。搜索/图/caches是投影；回查PG ACL/status/epoch，投影落后标partial/stale，不把已知失效事实返current。
6. 原文先写不可变bytes并read/hash校验，再提交metadata。DB失败留下未引用orphan是可恢复失败，不能出现有效记录指向缺字节。GC仅删除经PG引用检查且与发布共享hash锁/保护窗口的orphan，提交前再次验证对象存在；不覆盖已引用对象。MinIO可重建/重读/错误分类均需实测，客户端锁版本与资源由主控确认，不用假版本填表。
7. 回滚采用停新写/消费者、前版兼容应用与前向修复或隔离环境的已验证备份恢复；有数据不自动执行破坏性downgrade。发布失败保留原有效版本，PG不可用返回503/not-ready，不启用memory事实。已提交outbox可重复投递，消费者按change/business_version幂等；不宣称exactly-once外部调用。

## 6. 待执行验收计划与原任务逐项映射

**本节全为 `not_run`。** 本轮执行的命令只有读文件、Git核对、官方CBM帮助/索引/trace与报告写入/检查；测试执行数量未采集，不能填passed=0或某个估计数量；pytest/Ruff/mypy/browser/PG/MinIO均未运行。

后续真实测试必须有 `DIANZI_TEST_RUN_ID`、专用loopback端口/数据库 `test_dianzi_<run_id>`、test专用用户与不输出值的TEST_DATABASE_URL；现 conftest通过scripts/dev.py统一验证，不用常规开发库，不开清库/downgrade。复用该隔离fixture；明确“新增测试文件尚未创建”。每次日志保存真实开始/结束秒、命令/工作目录/退出码、JUnit通过/失败/error/skip数、输入版本与迁移revision。资源失败登记blocked，不改skip/阈值。

### R02 六项必要可观察实验

| R02项 | 输入/实际操作 | 必须观察的结果 |
|---|---|---|
| ① 重启 | 进程A真实PG登录/发布事实与证据，关闭A；独立B同DB加载session、claim/entity/alias/history | 原session/hash/CSRF有效、同UUID/版本/证据可读；B注销后A/C请求立即失效；不是复用同Python对象 |
| ② 半发布失败 | 批次两个合法claim，注入第二claim/关系/outbox insert后的异常，另Session查询 | 所有新事实、关联、历史、receipt、epoch/outbox均未提交；旧版本仍在；重放后只有一个完整版本 |
| ③ tenant隔离 | A私有revision/evidence/claim；B按ID、查询、搜索候选和导出请求；恶意自报tenant | 一律404/空可见集合、无名字/计数/私有值；公共派生不能引用A私证；真实SQL预过滤，最终引用再核对 |
| ④ A→B→A | 同document输入bytes A、B、A，各保存text/evidence后新进程读历史 | 三个按顺序修订，1/3同hash但不同revision_id，旧证据指原版；相同末版重复无新revision/event |
| ⑤ supersede/撤回 | 同来源明确修订old→new；并列另一来源；随后明确撤回；另404获取 | 历史不可变、有效状态分别正确、原文保留，404不撤回；旧索引命中经PG回查不能返current |
| ⑥ 并发重放 | 两独立连接/进程同时相同publication_key+digest发布，再重复消费outbox；另同key不同digest | 唯一业务version/receipt/change/outbox，epoch只随实质变化递增；异digest409；重复消费不重复关系/副作用 |

### 六类原卡 C01–C06（全部保留；R02只实现其持久化切片）

| 原case | 保留的输入与断言；本次计划覆盖 |
|---|---|
| T04-C01 | aware UTC+合法scope DTO roundtrip；持久化后读取不改变enum/time/字段语义 |
| T04-C02 | public+tenant或tenant无ID→拒绝DTO与PG写，不偷偷清tenant |
| T04-C03 | unknown与false同批保存/读回仍不同，未观察不填current/0 |
| T04-C04 | naive时间/负时长拒绝，旧输入适配不猜UTC |
| T04-C05 | 模型多出skip_validation→extra forbid，不进入事实batch |
| T04-C06 | schema重复生成无漂移；主控统一schema版本与兼容生成物 |
| T05-C01 | 同末版重复导入只复用revision，fetch与业务event不同计数 |
| T05-C02 | A→B→A真实PG保存三修订，各可重读原字节与证据 |
| T05-C03 | bytes落盘后DB异常→无有效dangling引用；orphan可回收，已引用不可删 |
| T05-C04 | path traversal/非法hash拒绝；本地与MinIO都只派生content key |
| T05-C05 | tenant B引用A证据/修订→拒绝事务且无部分行 |
| T05-C06 | 0005旧库含事实/时间/unknown升级后保留；空库/备份恢复另核验 |
| T06-C01 | 正确账号真实双API登录/注销/重启；session共享、撤销立即生效 |
| T06-C02 | B读A资产/证据及审计→404，无名称泄漏；相同access规则用于事实 |
| T06-C03 | 自报tenant/role额外字段拒绝，审计只留submitted_keys |
| T06-C04 | 无CSRF、非ASCII/不匹配CSRF、错误Origin写请求拒绝且不错误注销 |
| T06-C05 | 过期/错误session与两个进程共5次failed+inflight窗口；第6拒绝；成功只释放己方占位 |
| T06-C06 | 认证SQL错误、审计/JUnit/日志/前端构建无真实密码、token、CSRF、DSN或秘密 |
| T17-C01 | AI公告direct证据保留；分类业务仍R04切片，不以PG持久化代替分类通过 |
| T17-C02 | 通用依赖在AI清单仍dependency_relevant；保留来源证据与分类版本 |
| T17-C03 | 普通发布background/irrelevant；存状态而非生成漏洞事实 |
| T17-C04 | 同CWE不同CVE，不因指纹/产品相同合并；硬ID冲突负例 |
| T17-C05 | 一文两CVE→两稳定事件、多条event-document关联，不合并 |
| T17-C06 | merge后undo→操作历史与来源引用可恢复，change/epoch/outbox同事务 |
| T19-C01 | CVSS/版本raw值、机构、JSON pointer、revision/evidence ID实际可追溯 |
| T19-C02 | 无CVE论文CVSS not_applicable而机制仍pending；canonical paper kind适配 |
| T19-C03 | 一维provider失败、论文成功→partial+保留成功；DB故障另全事务rollback |
| T19-C04 | 相同fingerprint重跑/并发只一组事实/消息；failed事务不占已处理key |
| T19-C05 | 不同评分机构并列；同source不同revision/path/authority也不吞掉 |
| T19-C06 | 私资产维度tenant保存，public_event_summary/事实查询/导出不能出现私有值 |
| T21-C01 | 同名包不同生态为两UUID；type/硬ID冲突不自动合并 |
| T21-C02 | 明确alias核验后可归一且evidence/revision可读；只有source字符串仍候选 |
| T21-C03 | 同scope/有效时间互斥结论disputed并列；不同机构/分支不多数投票 |
| T21-C04 | 厂商明确自修订supersedes，old历史保留且current只返回适当新状态 |
| T21-C05 | source404只改FetchAttempt/获取状态，旧claim不自动withdrawn |
| T21-C06 | 跨tenant事实/私证不入公共结果；model_hypothesis无支持不升格supported |

原整卡最终需要所有映射切片与原前置：T04=R00+R02；T05=R02；T06=R01+R02+R20；T17=R02+R04+R10；T19=R02+R07+R08；T21=R02+R10。仅本预备分析或单R02不能自动验收这些整卡；以manifest恢复DAG/CR-R07为准。

### 六层最小真实命令计划（未运行）

| 层 | 后续必要命令/证据 |
|---|---|
| unit | backend工作目录：`uv run pytest tests/unit/test_t04_domain_contracts.py tests/unit/test_t05_content_store_boundaries.py tests/unit/test_t17_relevance_and_event_linking.py tests/unit/test_t19_structured_enrichment.py -v`；新增最小adapter/fingerprint纯判断负例。最终冻结覆盖门按全回归执行，不降低 |
| contract | `python scripts/dev.py check --scope contract`；新增R02 canonical scope/status/value union及正负公开适配合同测试，不修改旧金标 |
| integration | backend：`uv run pytest tests/integration/test_t05_persistence_and_raw_store.py tests/integration/test_t07_jobs_and_outbox.py -v`；新增 `tests/integration/test_r02_knowledge_persistence.py`、`test_r02_auth_state.py` 后真实运行，涵盖上述六实验、0005→head、空库、重启和双进程；不能把旧test_t21内存结果记integration |
| e2e/security | `python scripts/dev.py check --scope security`、`python scripts/dev.py check --scope e2e`，并 `uv run pytest tests/security/test_t06_authentication_and_scope.py tests/security/test_r01_http_authentication.py -v`；浏览器登录/刷新/me/csrf/退出和另一API进程；fixture证据与真实PG证据分开 |
| live/evaluation | 本R02仅需真实授权隔离PG/MinIO的重读/重启/故障metadata；具体MinIO adapter客户端和命令待主控核定版本与资源后给出。没有provider/模型/真实来源时不能外推评分；R07/R22正式实测另验 |
| manual | 独立非作者核对：备份样本hash、旧证据时间线、legacy输入拒绝理由、授权scope/状态适配、真实UI失败显示。未人工查看写not_run，不以代码审查代替live |

后端改动完成后按冻结入口再执行 `uv run ruff check .`、`uv run ruff format --check .`、`uv run mypy src` 与完整相关回归；前端受影响需 `npm run lint/typecheck/test/build` 与既有三链browser复跑。实际scope命令须非0测试且非全skip，否则不能passed。不得为了定向文件的覆盖结果降低60%或其他冻结门；测试策略与完整质量门分别留下原始结果。

## 7. 实施文件所有权与主控下一步

建议主控冻结后再派不重叠实现，当前只有报告写权限：

- **主控独占公共集成**：domain DTO/schema/enums、knowledge/models.py、Alembic编号/迁移、schema生成物、公共outbox/payload协议、app.py默认装配、跨模块公共合同、状态/任务整卡记录。
- **认证实现包**：authentication.py与一个具体PG auth state repository，专属R02 auth integration/security tests；保持auth_routes返回shape与原fixture显式注入。需主控给定0006表合同，不触事实文件。
- **知识实现包**：claims/entities/event_linking及其具体repository，revisions/证据坐标桥接与有锁发布服务、专属R02知识integration；不改公共models/schema/迁移编号，先按冻结Typed DTO实现。
- **富化实现包**：structured.py与字段/维度fingerprint adapter及专属unit/contract；引用知识发布服务，不自己写outbox/epoch、另建事实表或改九维指标。
- **对象存储实现**：content_store现有接口兼容修正与MinIO具体adapter及专属存储测试，资源/版本未核定前不编依赖；与revisions调用协同，不能抢同文件所有权。

最小所需输入是主控的统一表/DTO/坐标/CSRF/payload_ref合同与文件所有权、R01受影响切片放行和隔离测试资源标识；不需再次向用户询问普通编码许可。现在可冻结草案/准备回归输入，不能开始未放行依赖上的业务迁移。

评分证据只登记准备工作对 E1（共享状态/事务/恢复）、F1（修订/去重/重放）、F2（事实与九维存储/关系）、F3（授权有效性/历史）的合同覆盖；没有评分项能力通过或性能数字。本报告未改变原计划/验收条件；所有新增接口与表仍为不生效建议。

报告与图证据可审查；产品迁移、pytest、PG/MinIO重启与浏览器均未执行。当前风险是旧scope/status/value/坐标适配若未先冻结，会把旧fixture语义误当canonical事实；应先解决这些具体合同点，再实施R02。
