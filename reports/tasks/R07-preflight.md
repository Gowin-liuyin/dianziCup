# R07 · 九维富化能力切片前检

文档首次创建时间：2026-10-15T22:27:33+08:00
本次写作开始时间：2026-10-15T22:27:33+08:00
本次写作结束时间：2026-10-15T22:27:35+08:00
最后更新时间：2026-10-15T22:27:35+08:00
主控：/root；前检 Agent：/root/r07_enrichment_contract_preflight。
状态：只读 preflight complete；R07 产品实现、整卡验证与最终独立验收未由本报告开始/签署。
工作分支：codex/full-delivery-recovery；源码基线：`0a45185ae3ffb73a6d186b98421e26a52f78bfc6`；backend/src tree：`9a392b4c6cbb713079f23c9fa3bb7c36fc3f68ea`。
证据截止：2026-10-15T22:27:35+08:00。未 commit/push；仅新增本报告和专属 run 目录。主控已有 progress/reports 修改保护，未覆盖。

## 1. 可直接采用的结论

九维状态表、类型化发布输入、历史、幂等收据、事件版本检查、权限与 outbox 已有；NVD CVSS 已经沿真实采集路径发布并由详情 API 读取。R07 应补其余八维与抽取发布门，复用这些模块，不重写另一个富化台账。`dimensions.py` 的六维旧矩阵和 `ExtractionBatch` 等旧 helper 目前是隔离测试能力，不能直接接入产品作为可信发布校验。

主控可先冻结下列 attempt/candidate seam，然后同时分派公共信号适配与证据字段抽取；不需要机械等待 R06 整卡 accepted。依赖 R06 尚未实测的 OSV/论文/标准/政策 live 必须保留等待，不能越过能力前置。暴露维度在 R07 完成接口与状态合同，真实 Hunter/Quake 在 R08，不能涂绿。

实际 state 快照：R02=accepted/complete; R05=accepted/complete; R06=in_progress/partial; R07=pending/not_started。状态仅用于定位；本报告不更改它们，不把旧 accepted 转为全功能完成百分比。

## 2. 权威、能力依赖与已有证据

已核对 AGENTS、00、11/12、03/04/05/06/07、CR-R01–09、manifest/requirements/state、交接/阻塞、T13/T19/T20/T22/T23/T41 与 R02/R05/R06 报告。33 个文档的实际字节 hash 和严格重复键 JSON 检查见 `contract_snapshot.json`。用户完整有界批次与现行 CR-R07 允许按能力切片推进；这里不申请新批准、不削减验收。

| requires_slice | 可复用事实与传播边界 |
|---|---|
| R02:T19 | `DimensionSubmission` 九维/七态，`DimensionRepository` 同 Session 结果历史、CAS、收据/epoch/outbox；G-A 维度初审固定 a366，173 原回归 +20 独立 PG 探针。后续 CVSS 真实接线已进入当前基线。 |
| R02:T21 | `KnowledgeRepository` 当前/历史 Claim、别名、冲突/修订与证据权限。结构/引用门可复用；不据此声称领域语义冲突全部正确。 |
| R05:T18 | 两种 wire 生成客户端、严格 JSON/schema、有界网关和用量轨迹、真实 E5/重排。G-B 固定1927限定 Ship；累计8真实模型调用、费用unknown是历史证据，本轮调用0。 |
| R05:T20 | 首事件回答生成与独立支持核验已有真实链；原合同描述明确不等于九维抽取。可复用客户端与证据验证策略，不能复用旧 dataclass 作为输出 schema。 |
| R06:T11/T13 | 当前 main 有 OSV/AVID/release 纯解析和公共文档持久化。新 worker/页边界仍由主控冻结复核，尚不能在本报告证明实际业务来源 live；结构化字段纯适配可独立开发。 |
| R06:T14/T15 | arXiv/RSS 元数据、NIST/CAC 原文适配与 PG 公共资料合同已有；与完整实测/全文许可分别判断。论文/标准/政策的 live 发布依赖对应实际页校验通过。 |

主控同 SHA 的 R06-document-live 原始证据：独立专库从空库到0015，NVD20+厂商10资料/143证据，2来源任务均 explicit 单页预算 partial；真实 Edge3passed，1366/390、永久证据/历史/退出边界，0模型。不能将其扩展为另外7源或九维已上线。R06 的 source boundary、自动轮询、原 CPU 修复等后续 WT 不在本图/本次代码审查范围。

整原卡合并条件保留：T13=R06+R07；T19=R02+R07+R08；T20=R05+R07；T22=R07+R09+R10；T23=R07+R08+R10；T41=R04+R07+R10+R17。每卡原 C01–C06、原最终前置与独立验收均不能因 R07 子包完成而自动 accepted。

## 3. 真实入口与共同根因

### 3.1 已贯通的产品路径

`create_application`（api/app.py:38、:117–138）→认证/CSRF 的 source route→`enqueue_job`/PG payload/outbox→`workers/runtime.py:EXECUTION_HANDLERS` 的 `SOURCE_JOB_TYPE`→`execute_job`（executor.py:80–122，前后 PG lease）→`build_source_page_handler`→`persist_source_response`→`_persist_member`→不可变原文/text block/evidence→`KnowledgeRepository.publish`→`_publish_cvss`（source_documents.py:727–774）→`DimensionRepository.publish`→PG current/history/收据/epoch/change/job/outbox。

读取：`GET /v1/events/{id}` 与 `/api/v1` 别名→同事务认证→`KnowledgeReadService.event_detail`（:310）→`_dimensions`（:543–676）→查 PG 可见 claim/evidence/source、校验当前事件/修订与 freshness→`EnrichmentProjection`→frontend `features/events/event-workspace.tsx:80–82` 九行状态/引文。不是“全部仓储未接线”；已有 CVSS 链必须保持。

模型：`GenerationClient.generate`（generation.py:371）经 `NetworkGateway`，固定 provider endpoint、输入/调用/响应/token/总耗时边界，返回 `TypedGenerationResult[T]` 与 `AttemptMetadata`。`grounding.generate_grounded_answer` 的生成+支持核验只是可复用策略；它不是九维 ExtractionBatch 发布服务。

### 3.2 已复现的旧 helper 限制

| 触发 / 位置 | 实际结果 / 根因 | R07 最小处理 |
|---|---|---|
| `dimension_status_for_kind('cvss', 'advisory')`，dimensions.py:9–43 | not_applicable；只有六旧维名和 vulnerability_advisory/research_paper 等旧 kind。当前公共合同 canonical kind 是 advisory/paper/standard/policy。 | 新业务矩阵使用现有 DocumentKind 与九维 canonical 名；旧 fixture 词汇不能静默进入新调度。兼容旧测试由唯一主控记录规则，勿把历史全部改为 available。 |
| `reject_unsupported_identifiers(['CVE-2024-12345'])`，extraction.py:88–90 | 返回空拒绝列表，即语法有效 CVE 未拒绝；函数仅正则，没有传入来源支持集合。 | 标识必须与当前源值/证据对应，CWE/ATLAS 再校验固定版本官方目录；语法检查和支持校验分开。 |
| 两次重复句、block_id='missing-block'，extraction.py:71–79 | (True,True)，仅检查 block_id 是否非空，不查真实块或位置。 | 按 revision+真实 TextBlock+明确 occurrence/Unicode 坐标定位，再调用 attach_evidence_span 的 hash/范围检查。未知 block 和多次未定均拒绝。 |

上述4个观察在 `legacy_helper_observations.json`，纯 fixture 无 IO。源码 rg 与 CBM 交叉确认旧 helper 无当前业务调用；这是不能扩大复用的已证实限制，不称当前真实来源已污染/数据泄漏。旧49个 unit/contract 全通过也不能证明这三项新业务边界已满足。

还存在明确接口缺口：`ClaimObjectValue` 只支持文本、ScoreValue、LinkValue、VersionRangeValue；ScoreValue 未独立存 CVSS standard_version/scored_at，VersionRangeValue 仅 expression，其他谓词的结构化值会被拒绝。不能把 EPSS/KEV/CWE/ATLAS/暴露等核心语义藏进任意 metadata 或塞字符串后称 typed。扩展必须由主控写正式小变更单、同步 domain schema/export/fixture/frontend，保留v1/v2历史读取，不应由多个 Agent 发明不同模型。

## 4. 主控先冻结的小接口（提案，不是实现）

仅建议新增业务明确的 `enrichment/contracts.py`；复用 StrictRecord/DocumentKind/DimensionStatus/FreshnessStatus/DimensionName、已有 ClaimSubmission、永久 evidence 与 GenerationClient，不新增 BaseService/通用 CRUD/新事实库。

```python
class EnrichmentContext(StrictRecord):
    event_id: UUID
    expected_event_version: int  # strict >=1
    revision_ids: tuple[UUID, ...]  # server derives active visible revisions, <=20
    document_kinds: tuple[DocumentKind, ...]
    external_cve_ids: tuple[str, ...]  # validated IDs with source support
    rule_version: str

class EvidenceBoundCandidate(StrictRecord):
    dimension: DimensionName
    predicate: str  # closed registered predicate, not arbitrary new model predicate
    value: EnrichmentValue  # discriminator union, listed below
    source_revision_id: UUID
    block_id: UUID
    quote_text: str
    start_offset: int
    end_offset: int
    origin: ClaimOrigin
    qualifier_evidence_ids: tuple[UUID, ...]
    support_status: Literal['pending', 'supported', 'rejected']
    reason_code: str | None

class DimensionAttempt(StrictRecord):
    dimension: DimensionName
    status: DimensionStatus
    candidates: tuple[EvidenceBoundCandidate, ...]  # <=100, cannot mean published
    searched_at: UtcTimestamp | None
    source_ids: tuple[UUID, ...]
    observed_at: UtcTimestamp | None
    source_version: str | None
    freshness: FreshnessStatus
    error_code: str | None
    attempts: tuple[AttemptMetadata, ...]  # persisted only as safe typed usage trace

def enrich_structured_fields(context, stored_documents) -> tuple[DimensionAttempt, ...]: ...
def extract_evidence_candidates(context, bounded_blocks, generation_client) -> tuple[DimensionAttempt, ...]: ...
def validate_candidate_support(candidate, stored_block, source_field) -> ValidatedCandidate: ...
def publish_dimension_attempt(session, access_scope, context, attempt, job_context) -> SavedDimensionResult: ...
```

代码块是可分派字段草案，函数应补明确参数类型后由主控冻结，不能复制省略号成为产品占位。`AttemptMetadata` 是现有 dataclass：服务存储应按既有 `_attempt_records` 风格明确转换时间/token/fee，不拿未知费用写0。`ValidatedCandidate` 必须由定位/字段/语义门生成，不能允许模型直接自填通过；未知/拒绝候选保留，不进入支持事实或规则。

EnrichmentValue 最小闭集：`CvssSignalValue`（standard_version/vector/base_score/authority/scored_at）；`EpssSignalValue`（cve_id/probability/percentile/date/model_version）；`KevSignalValue`（cve_id/catalog_version/date_added/required_action）；`WeaknessValue`（cwe_id/taxonomy_version）；`AtlasMappingValue`（technique_id/taxonomy_version/mechanism/qualifiers）；`VersionAssertionValue`（package/ecosystem/scheme/原范围、fixed右开、branch/unsupported理由、官方修复和一般缓解分栏）；`LiteratureReferenceValue`（document/revision/type/支持机制/limitations）；`ArtifactReferenceValue`（URL/固定commit/template ID/title/static状态/许可，不执行）；`ExposureAggregateValue`（provider/query_id/query_version/service_count/observed_at/TTL/limitations，vulnerable_estimate默认None且禁止资产明细）。这些是语义字段提案，不是提供者真实 wire schema；提供者字段/版本必须另核官方正文和实际响应。

已有 `DimensionSubmission` 可直接作为最终 PG 发布输入，自动从已发布 Claim IDs 构造，不直接接收候选任意值。九维值应按 predicate→类型契约进入现有 Claim 表 JSONB，迁移/版本与 JSON Schema 由主控唯一负责；不另建并行 dimension values 真相。

## 5. 九维状态与适用性

不新增或合并状态。unknown 由“值为空+pending/blocked/failed 或 freshness unknown +固定原因”表达，不允许写 score/count=0 冒充未知。每维独立，失败不删除其他维事实；同一维最新失败可显示 failed，同时历史可信结果保存且显示旧观察时间/stale，不回退当前绿灯。

| 维度 | 正例发布 / 不适用与缺失 |
|---|---|
| cvss | 沿已核验 NVD 字段继续；保留标准版本/向量/机构/日期。同版本不同评分冲突并列，不把不同标准版本简单冲突或取最大。论文/政策不强制评分；无CVE并非绝对不能有作者评分，按事件/材料支持判适用。 |
| epss | 有来源支持 CVE，概率/分位数[0,1]且模型/数据日期；有效0为 available。无CVE为 not_applicable；适用但查无条目为 not_found；API失败为failed，授权/未配置为blocked。 |
| kev | 有来源支持 CVE 且目录条目匹配/版本/日期。合法完整目录中未找到只记录 not_found+搜索范围/时间，不能推导“不可利用/安全”。无CVE不伪造值。 |
| cwe | 显式来源 CWE ID+固定目录校验；缺失为not_found。名称相似不自动映射。非CVE AI风险也可能适用，不能单凭无CVE不适用。 |
| atlas | 固定目录 ID 且组件/风险机制与原文共同支持；相似文本只候选。不存在可验证映射时保留 pending/not_found，不能把所有论文默认关联。 |
| versions | 软件身份+原始范围/生态/分支/固定边界+限定配置证据；未知比较保持unknown/unsupported理由。无软件版本概念的政策可not_applicable；有软件身份但字段缺失计缺口。R11才完成比较/资产四态，不能提前称已完成自查。 |
| literature | 明确分析事件/验证同类机制/提供防御等证据；只同主题为background候选，不变确认关系。缺搜索信息保持pending，真实搜过无结果not_found。R09知识卡/R10强关系最终范围仍保留。 |
| poc | 公告或固定仓库引用的存在性，candidate_found/static_reviewed分列；链接存在不叫lab_verified。未执行授权外PoC，模板文件也不执行。来源删/转私有失败不自动撤回历史。 |
| exposure | R07只冻结 aggregate 合同；未配置为blocked或pending，不能not_applicable回避必要维。R08 provider返回真实0才available0；服务数量不等于受影响资产数量，明细不入PG/log/cache/model。 |

适用性函数应接 `DocumentKind + event_type + verified external IDs + verified product/version scope`，不是仅kind字符串矩阵。`not_found`沿用仓储强制 searched_at/source_ids；`available/conflict`沿用支持 Claim/引文门，conflict还需新增真实同范围互斥语义检查，不仅两条Claim数量。缺观察时间 freshness=unknown；TTL和当前事件/修订版本检查在读取时复用 `_dimensions` 并补必要规则，不能以抓取时间冒充上游发布时间。

公共 `EnrichmentProjection` 与 public_api_v2 已冻结为8字段，frontend parser拒绝extra：第一批继续复用原GET/claims/citations，不偷偷把上述内部字段塞进响应。若U02需显示 searched_scope/尝试历史/值结构，主控先正式登记 additive DTO/新只读投影合同，前后端/SDK同时升级；不能通过修改严格 parser 跳过边界。

## 6. 调度与 GET 复用点

1. 根用户问题不是“创建9个函数”，而是同事件当前原文变化后形成逐维真实状态。主控新增唯一 `enrichment/jobs.py` 的 `ENRICHMENT_JOB_TYPE='enrich_event'` 固定 handler，payload只event/revision/version/维度集合/策略版本与幂等摘要，不接受tenant/provider URL/key。服务端从认证/PG job_context注入范围。
2. 在原文页成功持久化同一事务边界（source writer完成事件/claims/版本之后）enqueue一次事件富化；幂等键含 event/version/维度/规则/源版本摘要，沿PG payload/outbox dispatch。不要从每次维度 `save_change_publication` 再入队同种任务造成自触发循环。
3. 每次任务完成1个维度或小有界组；公开信号无需LLM。模型维度默认生成1+必要独立支持校验1，共享现有整次调用/token/字节/时间预算；需确认 current runtime 25/30秒与实际模型完整耗时兼容，不能直接把数分钟调用塞入30秒handler并称可恢复。
4. `execute_job` 现有事务会包裹handler外部 IO：在短有界调用下复用；更长模型需要正式两阶段预约/结果提交，参照R05 PG reservation/CAS，分别保存未知已计费用。不要依靠PG长事务/行锁跨多个网络维度，也不新增Celery另一套状态。先发布重启/中断/已付费未知与预算测试，再启live。
5. 最终提交重新读事件版本与lease，并通过 `KnowledgeRepository.publish` 和 `DimensionRepository.publish` 同Session原子提交；迟到版拒绝重判，其他维成功历史不删。语义错误候选不得在 attach_evidence_span 时直接自填supports_claim=True。
6. GET复用 `KnowledgeReadService._dimensions`/EventDetailResponse、原 jobs轮询与永久 EvidenceResponse，不增加空stub。frontend已有九行，不应由UI把缺行补available；完整九态来自PG。首次主控若增加manual trigger，保持system_admin/CSRF/幂等与原读权限，旧route别名同步。

## 7. 可以直接分派的文件所有权

宿主4槽下主控+2实施+1新review轮换；本前检释放后优先独立R19初审。下表需由主控先提交冻结 seam 后从相同正确基线开worktree；实现者不得commit公共schema/锁/迁移/progress，不push/签accepted。

| 包 / 依赖 | 允许文件 | 交付与结束条件 |
|---|---|---|
| Root R07-core | `enrichment/contracts.py`、domain/records.py、必要 schema/export/变更单、`enrichment/jobs.py`、runtime、shared API、迁移编号/配置/锁 | 固定九维/值/候选门与兼容策略，冻结commit交作者；根改动另交新reviewer。只有root改公共接线和PG事务，避免两作者各自声明Model。 |
| A R07-signals / R02与已证实NVD+冻结seam | 新 `enrichment/signals.py`、`enrichment/signal_sources.py`、直接unit/contract tests与其报告/run | 原文CVSS/CWE适配+固定FIRST/CISA响应解析/网关请求计划，正常/空/字段/授权/429/乱序日期/异常数值；只返回typed attempts/candidates。官方schema核实、真实GET由授权受控段执行，fixture不计live。禁止改source_jobs/旧writer/共享Gateway；需要调整报root。 |
| B R07-candidates / R05与固定已保存公开证据+seam | 新 `enrichment/candidate_validation.py`、`enrichment/extraction_service.py`、本包prompt/dev样例、直接unit/contract tests与报告/run | 版本/修复/PoC/文献候选字段型、定位/否定/限定/支持门，ATLAS ID匹配可先纯函数官方目录快照。无CVE风险正例、不存在block/原文注入/错值/错ID拒绝。不写PG/runtime/API、不接私有外发、不修改holdout/金标。 |
| C R07-UI / Root GET合同冻结、已有事实/九态样本 | `features/events/event-workspace.tsx/.css/.test.tsx` 和直接e2e；API parser仅唯一指定集成人可改 | 复用黑客背景/九行、成功值/失败/空/冲突/过期/未知/待人工/历史/引用。先开发显式fixture，不冒在线；然后同SHA真实API/浏览器。不能改App/auth/client/锁/全局路由。 |

A/B纯内部可现在准备，因为只消费冻结公开结构/已持久化材料，R06 新source正文Must不影响已有NVD路径或纯边界测试；涉及新OSV/arXiv/NIST/CAC真实输入的提交/验证仍要等待对应切片关闭。整个R07完成依赖全部要求，不由可并行包代替。

## 8. 六类原验收与八层实际/待补测试

| 层 | 本轮实际 | R07必须补 |
|---|---|---|
| unit | 原T19/T20/T22/T23 + R02 typed publication边界49passed，0fail/error/skip；纯helper4观察 | 九维正例+所有七态/三freshness、CVE缺失/适用缺失、各值类型/NaN/bool/非法ID、同范围冲突/版本不同范围、quote存在与语义分开。 |
| contract | 上述原测试中的3个contract文件实跑，显式fixture；未跑新R07合同 | 原36个C01–C06保留：release与commit分文档、多漏洞不合并、固定SHA/404/403/PoC；少样本family泄漏、错CVE/CVSS/否定/限定；论文主题与机制区分/政策草案正式/未知范围；静态非运行、官方修复非项目建议；schema导出与runtime/front同步。 |
| integration | not_run，本轮不接PG/Redis/MinIO | 真PG + Redis worker +原文对象：各维独立失败/其他成功，同key重放/碰撞、多worker、SQL中途故障、迟到事件版本、重启读取、failed→success history、source修订、job/outbox原子，不能SQLite替代。 |
| security | not_run；源码/既有范围门只定位 | 跨tenant候选/claim/source/evidence/历史均拒绝；viewer public写拒绝；注入材料不授予工具；凭据不入prompt/log/front；arbitrary URL/SQL拒绝；曝光明细网关即丢弃、PoC无执行；模型真实账户与编程Agent账户分离。 |
| frontend | not_run；已有代码/合同可复用 | 原T41六例、9行所有状态与可读值/长版本/中文表、固定revision evidence、未知时间、403清除详情/竞态、reduced-motion、390/1366无溢出。 |
| e2e | not_run | 同冻结代码真实认证→源/worker→PG九维→页面→原文/历史→重跑/失败恢复；禁止route intercept计live，UI不伪完成。 |
| live | not_run；引用已有R05/R06历史证据，不重新签 | 逐维真实数据/版本/观察时刻/失败/unknown，真实model关键字段支持核验、授权 R08聚合；按实际 source可用性分别列；正式准确率/召回/分母留R19/R22。 |
| manual | not_run | 双人独立金标/裁决、语义争议/关键版本条件复核。无核验人就awaiting_human_label，不能模型投票替金标。 |

本轮测试cwd D:/dianzi，Python D:/dianzi/backend/.venv/Scripts/python.exe，2026-10-15T22:20:21+08:00至2026-10-15T22:20:22+08:00，exit0，49passed，pytest测试0.16秒。`--no-cov`是现存少量定向行为检查，不是产品全量覆盖门，不修改原60门或声称新覆盖率。未运行整仓质量/PG/security/frontend/e2e/live/manual；报告无新模型用量/费用估值。

## 9. 原始命令、索引与异常记录

独立 CBM cache `/tmp/dianzi-cbm-r07-preflight-20261015`，project `dianzi-r07-preflight-0a45185`，官方 portable0.11.0，仅backend/src，fast，persistence默认false。实际1206nodes/5910edges/91Python源文件、17种边。architecture默认仅把_pdf_worker.main列entry_point，是分析器识别范围，不能证明API未接；源码与create_application trace交叉有双前缀21routes。没有索引报告、fixture、holdout或秘密，缓存仓外未提交。

`DimensionRepository.publish` inbound实得 `_publish_cvss`/`_persist_member`/`persist_source_response`；outbound现有引用验证+收据+epoch。`locate_quote` inbound0与rg只tests一致。GenerationClient、worker入口和source persist的合格名称定向trace已保存，图只能定位，不证明业务语义/live。

| 实际命令收据 | 开始→结束 Asia/Shanghai | exit |
|---|---|---|
| `baseline.command` | 2026-10-15T22:15:08+08:00 → 2026-10-15T22:15:08+08:00 | 0 |
| `caller_search.command` | 2026-10-15T22:20:21+08:00 → 2026-10-15T22:20:21+08:00 | 0 |
| `cbm_architecture.command` | 2026-10-15T22:15:14+08:00 → 2026-10-15T22:15:17+08:00 | 0 |
| `cbm_dimension_publish.command` | 2026-10-15T22:20:02+08:00 → 2026-10-15T22:20:06+08:00 | 0 |
| `cbm_index.command` | 2026-10-15T22:15:08+08:00 → 2026-10-15T22:15:14+08:00 | 0 |
| `cbm_model_generate.command` | 2026-10-15T22:20:15+08:00 → 2026-10-15T22:20:18+08:00 | 0 |
| `cbm_quote_helper.command` | 2026-10-15T22:20:12+08:00 → 2026-10-15T22:20:15+08:00 | 0 |
| `cbm_schema.command` | 2026-10-15T22:15:17+08:00 → 2026-10-15T22:15:20+08:00 | 0 |
| `cbm_source_cvss.command` | 2026-10-15T22:20:06+08:00 → 2026-10-15T22:20:09+08:00 | 0 |
| `cbm_source_persist.command` | 2026-10-15T22:20:18+08:00 → 2026-10-15T22:20:21+08:00 | 0 |
| `cbm_trace_build_knowledge_router.command` | 2026-10-15T22:15:36+08:00 → 2026-10-15T22:15:39+08:00 | 0 |
| `cbm_trace_configure_worker.command` | 2026-10-15T22:15:23+08:00 → 2026-10-15T22:15:26+08:00 | 1 |
| `cbm_trace_create_application.command` | 2026-10-15T22:15:20+08:00 → 2026-10-15T22:15:23+08:00 | 0 |
| `cbm_trace_enrich_event.command` | 2026-10-15T22:15:33+08:00 → 2026-10-15T22:15:36+08:00 | 1 |
| `cbm_trace_parse_extraction_payload.command` | 2026-10-15T22:15:29+08:00 → 2026-10-15T22:15:33+08:00 | 1 |
| `cbm_trace_publish_enrichment_batch.command` | 2026-10-15T22:15:26+08:00 → 2026-10-15T22:15:29+08:00 | 1 |
| `cbm_worker_entry.command` | 2026-10-15T22:20:09+08:00 → 2026-10-15T22:20:12+08:00 | 0 |
| `final_baseline.command` | 2026-10-15T22:20:22+08:00 → 2026-10-15T22:20:23+08:00 | 0 |
| `targeted_legacy_tests.command` | 2026-10-15T22:20:21+08:00 → 2026-10-15T22:20:22+08:00 | 0 |

先前按候选函数名查询 configure_worker/publish_enrichment_batch/parse_extraction_payload/enrich_event 返回exit1，保留4组原CBM输出；这些名称未实现，随后用真实源码名称/qualified方法名查询成功。不能单靠图未匹配证明业务缺失。一次读取猜测 backend/src/ai_intel/app.py 返回exit1，随后rg找到实际 api/app.py；真实工具错误未伪装源码缺失。`context_snapshot.py`初版把manifest子键误写slices，实际KeyError，改为真实capability_slices后读取33合同/严格JSON成功；原工具输出留宿主，不伪造文件日志或历史时刻。这些是前检仪器问题，无业务修复，也未与成功测试合成新分母。

命令起止/argv/cwd/exit见各command.json；源码26文件hash来自git show固定0a45185 blobs，见source_files.json，最终run manifest列精确字节hash。报告不包含任何秘密/私有资产/holdout答案，无外部网络/模型/第三方扫描/PoC执行。实际检索/测试前后HEAD与tree一致，报告封存时主控已合入独立CPU守护修复使checkout推进06423e8；首次封存保护assert拒绝，未生成报告。改为从已核对旧SHA取不可变源码hash，保留实际当前HEAD，仅给0a45185前检范围背书，不借旧图审新代码。后续合并必须刷新图。

## 10. 资源、限制与交回

模型与公共NVD/厂商已授权能力可复用；本Agent未读取DPAPI或凭据。公开FIRST/CISA已由主控probe，但接口probe不等于产品信号落库。CWE/ATLAS目录版本/许可与真实schema、论文全文再分发、POC/template固定来源范围、R08提供者字段/授权与预算边界需对应实施核对，本轮不猜。

双人核验/裁决与FOFA授权资产范围仍属最终人工/外部输入；它们不阻断公开九维代码与候选工具，但依赖live/人工不能accepted。无新增服务采购/大模型下载，0产品模型调用，未处理任何秘密。R08公网统计不依赖FOFA私有资产，原授权资产研判仍保留。

复用PG/永久证据/网关/两wire/原API与UI是最小完整路线；必要新增仅 typed value/候选校验/明确单卡handler，避免九个BaseService和逐维独立事实库。不记录虚构省行/费用。当前不实施代码，交主控冻结seam/正式小变更单后再分派；新作者自检→固定SHA→新独立review→root合并→真实集成。R07/G-C仍未由本前检验收，正式评分指标not_run。

文档修订记录：2026-10-15T22:27:33+08:00，前检Agent首次创建；2026-10-15T22:27:35+08:00，核对实际命令、26源码hash、49测试与范围后封存。本轮没有独立最终验收签字。
