# CR-R04 · R06资料只读投影合同

首次创建/本次写作开始/结束/冻结时间：2026-10-15T19:22:52+08:00；作者/root。

状态：frozen_for_implementation / awaiting_review。属于已授权CR-R04公开合同适配与R06/R09/R17资料范围，不改变身份、评分或金标；完整R09知识卡与R16变化重判继续验收。

## 输入输出与权限

新增GET同时挂载`/v1`、`/api/v1`。仅使用原Cookie认证与READ_PUBLIC，范围来自认证上下文；当前资料库只列公开来源，任何租户私有/asset_inventory不混入该列表。没有写入、任意URL抓取、模型或付费调用。响应固定schema_version=2，data_mode=live或fixture（fixture仅显式隔离测试）。错误复用现有problem：401未认证/过期、403权限、404资源或版本不可见、422过滤/游标错误、503依赖/投影失败；失败不能以空列表返回。

### GET /documents

查询：`document_kind`可省略或advisory/article/paper/repository_record/standard/policy；`source_category`可省略或既有SourceCategory八值；`q`字符串0..500（仅已存标题关键词，拒NUL）；`cursor`省略或不透明有界字符串1..2048；`limit`整数1..100，默认20。当前版本列表以当前revision入库时间、document_id稳定排序；cursor绑定过滤条件，每页重新做权限。返回`{schema_version:2,items:DocumentSummary[],next_cursor:string|null,data_mode}`。

DocumentSummary所有字段必需（null显式保留）：

| 字段 | 类型/含义 |
|---|---|
| document_id, source_id, revision_id | UUID |
| source_name | 有界字符串，注册来源名称 |
| source_category | 既有八类SourceCategory |
| document_kind | 上述六类，不含资产清单 |
| title | 1..500，所选revision标题，不用当前标题覆盖历史 |
| canonical_uri | 安全https URI或null，不带凭据 |
| revision_number | >=1整数 |
| is_current | boolean，当前/历史状态独立于内容覆盖范围 |
| source_published_at, source_modified_at, first_observed_at, ingested_at | RFC3339有时区字符串或null，复用既有UtcTimestamp |
| parse_status | pending/parsed/partial/failed/legacy_unverified |
| content_coverage | full_text/abstract/feed_excerpt/metadata/unknown；仅据已存解析事实，不把摘要称全文 |
| published_at_raw | 来源原发布日期文本或null，用于日期精度展示，不转换为推测时区 |
| published_precision | instant/calendar_date/unknown；instant须有实际source_published_at，calendar_date无精确UTC时刻 |

### GET /documents/{document_id}

查询`revision_id`可省略（读当前）或UUID（读该文档可见历史版本）；`evidence_offset`整数0..2000默认0；`evidence_limit`整数1..100默认100。后续证据页须保留第一响应revision_id，不能换当前版本拼正文。

返回`{schema_version:2,document:DocumentSummary,evidence:EvidenceResponse[],evidence_total:integer>=0,next_evidence_offset:integer|null,license_identifier:string|null,license_uri:https-string|null,source_notes:string[],data_mode}`。EvidenceResponse完全复用现有knowledge_contracts.EvidenceResponse（span_id/revision_id/block_id/Unicode坐标/quote_text/hash/locator/page/json_pointer/verified_at及来源时间等）。evidence为源文本片段，不表示支持安全结论；按start_offset/end_offset/span_id稳定排序。可以作为章节正文/证据列表直接展示，不新增重复的section正文。更多页按next_evidence_offset加载，保留同一revision。无可验证正文时evidence可空，但parse_status、coverage、source_notes必须诚实说明。

license_identifier是原许可标识或null；license_uri只允许安全https；缺许可不猜许可证/转载许可。source_notes只为有界文本说明，至多20条、每条至多1000字符；不执行/解析HTML，不从任意metadata链接生成额外访问。正文/标题/许可均React text。

### GET /documents/{document_id}/revisions

查询`offset`整数0..100000默认0，`limit`整数1..100默认20。返回`{schema_version:2,items:DocumentSummary[],next_offset:integer|null,data_mode}`，revision_number降序。每页权限/文档归属重新校验；用户可加载更多历史并以revision_id打开不可变原文。不能只返回第一页却声称全部历史。

## 兼容、迁移、回滚与验收影响

已有events/evidence/questions字段、认证与幂等合同不变；新增只读端点不改变原调用方。0015只给document_revisions加有界JSON对象source_metadata，旧记录默认{}，缺失值unknown/null，旧内容/hash/ID不改。新catalog保存时以正文与标题/URI/日期/解析版本/来源metadata共同判断复用，A→B→A必须三修订。观察时间不进入正文身份，不因每次轮询重复建版本；不自动制造CVE/Claim/关联。停止新资料采集/关闭新导航与GET后以前向修复回滚，保留0015与全部历史，不downgrade/删除数据。

R06存储/API切片、R09资料输入与R17页面增量；不签完整R09/R17或原T。必要验收：类型/过滤/绑定游标、空/部分/日期精度、历史归属/权限负例、证据精确子串与原文hash、PG重复/并发/A→B→A、前端strict DTO/注入/会话撤销/分页/历史、1366/390/reduced-motion与真实API浏览器。fixture不算live；新源worker尚未接线时明确not_run。

边界补充冻结 · 2026-10-15T19:27:04+08:00：source_name 1..300、license_identifier null或1..256、published_at_raw null或1..256、所有新canonical_uri/license_uri安全https最长2083、禁止userinfo/fragment/敏感query；source_notes最多20×1..1000。与既有HttpUrl上限一致。Pydantic实现以api/document_contracts.py为准；不改变上列字段或枚举。
