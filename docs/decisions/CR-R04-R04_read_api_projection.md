# CR-R04 · R04只读工作台投影合同

本补充落实已批准R04/R17与03/05、公用API v2；不改变评分、盲测、范围或权限。
状态：接口冻结供并行实现；实现/独立验收尚未完成。文档首次创建/本次写作开始/结束/证据截止时间：2026-10-15T10:37:00+08:00（本次小接口冻结写作）；阶段未过门。

## 端点与分页

统一 `/v1`，认证身份来自现有服务端session；READ_PUBLIC允许公共内容，同租户私有内容还要求READ_ASSET。不可见对象和不存在统一404，缺权限403，缺认证401，依赖失败503并遵循既有RFC9457。不得把503/未实现404转成200空列表。响应schema_version为数值2；data_mode由服务端配置、数据集隔离取得，不接受客户端声明。

GET `/events`：q、product、risk_type、updated_after、cursor、limit。默认20最大100；稳定分页按first_seen_at降序、event_id降序，cursor是不透明有界编码，严格验证类型/长度，不执行客户端SQL。q搜索事件标题与外部标识；product仅按已保存的产品关联匹配，未接通该能力时非空参数返回明确422 unsupported_filter；risk_type对event_type匹配。updated_after使用业务修订/关联的实际更新时间；缺可靠时间不能按first_seen_at伪装修订时间。完整过滤仍属最终R04/R17验收，不因首切片暂未实现而删去。

列表响应：`{schema_version:2,items:EventSummary[],next_cursor:string|null,data_mode:'live'|'fixture'}`。EventSummary字段：event_id（UUID字符串）、event_type、title、external_ids（字符串数组）、primary_product_ids（UUID字符串数组）、first_seen_at（带时区）、status、source_count（非负整数）、latest_revision_id（UUID字符串或null）、freshness（current/stale/unknown）。没有业务知识不伪造统计；source_count只计可见有效事件文档关联的去重来源，不计暴露资产。primary_product_ids只来自明确保存的关联，没有已知关联为空，不能推论无受影响产品。latest_revision_id来自实际关联顺序与稳定ID。freshness不能因新采集就认定所有事实current，缺规则/观察证据显示unknown。合并旧事件不会伪装成新的独立active事件。

GET `/events/{id}`：`{schema_version:2,event:EventSummary,dimensions:Enrichment[],revisions:RevisionSummary[],claims:ClaimSummary[],data_mode}`。Enrichment完全复用contracts/schemas/public_api_v2.json定义：九个维度cvss/epss/kev/cwe/atlas/versions/literature/poc/exposure，七状态、claim_ids、citations、freshness、observed_at、source_version、error_code。原03内部EnrichmentResult的source_scope/searched_at/last_job_id等由持久化服务保留，不能在公共Enrichment中偷偷增加字段。available必须有真实验证引用；未采集是pending，供应商失败是failed/blocked，不把未知变成0或false。

RevisionSummary字段：revision_id、document_id、revision_number、source_id、source_published_at、source_modified_at、first_observed_at、ingested_at、parse_status、document_kind、canonical_uri。四个时间/原文URI缺历史证据可null，不从文件mtime、当前文档头或source base_origin猜测；新的采集必须逐版本保存原文URI及各真实时点。parse_status明确pending/parsed/partial/failed/legacy_unverified。canonical_uri仅http(s)受控来源，不暴露对象存储路径。时间语义分别为源发布/源修订/首次观察/入库完成，不互相冒充。

ClaimSummary字段：claim_id、predicate、display_value（仅用于显示的文本）、origin、status、source_revision_id（可null）、evidence_ids。展示所有可见候选/已支持/冲突/失效状态时保持标识，不把候选当确认；display_value从服务端canonical类型生成，前端文本渲染、不执行HTML。候选引用不因存在而被计作支持证据。

GET `/evidence/{id}`：`{schema_version:2,span_id,revision_id,block_id,start_offset,end_offset,quote_text,quote_sha256,locator_kind,page_number,json_pointer,verified_at,source_uri,source_published_at,source_modified_at,first_observed_at,ingested_at,data_mode}`。block_id、页码、JSONpointer、验证时点及历史来源时点可以null，locator_kind为text/pdf_page/json_pointer/legacy_unverified。source_uri可null；有原文时提供可打开的http(s)URI。offset为规范全文Unicode code point左闭右开；旧未验证坐标明确legacy，不靠引用存在自证支持。不得返回DSN、bucket路径、秘密URL查询或其他租户资料。

## 并行与兼容

前端仅按这些DTO编写，未知字段/非法enum应显示合同错误，不能成功默认值。03/05范围保留；公用Vulnerability/NormalizedIntel/MCP投影由R18继续完成，本补充不取代或改写这些schema。root唯一负责后端投影/schema/迁移与事务，前端Agent只其独立WT。接口准备与UI组件可以并行，不表示G-A/G-B通过；真实来源、任务、模型与正式业务e2e仍遵守阶段依赖。

兼容现有auth/health与问题格式；旧API没有这些业务端点，无需覆盖旧历史。回滚停止新写/暂退只读新路由并保留数据库历史，前向修复，不自动downgrade。新增测试要求：ACL预过滤、不可见404、错误非空结果、cursor跨页稳定、原文非零block、旧版本时间未知、冲突/失效明确、真实来源列表→详情→证据浏览器操作。root将实际冻结提交交新非作者核对，再依据范围登记验收；本文不是作者自签accepted。


2026-10-15T11:35:26+08:00 · 非空游标细则：next_cursor=null表示无后续页；非null必须长度1–2048，为不透明continuation。空字符串是协议错误，不得把它当首页重取。服务端Pydantic和前端边界共同拒绝，原有效返回和字段无变化，新增unit负例；本实现须随R04批次独立审查。
