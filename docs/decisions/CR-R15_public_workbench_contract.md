# CR-R15 · 订阅与报告工作台公开接口

文档首次创建时间：2026-10-16T12:49:22+08:00
本次写作开始时间：2026-10-16T12:49:22+08:00
状态：approved_for_implementation；schema与API联调待独立验收。

冻结JSON Schema：[recommendation_api_v1.json](../../contracts/schemas/recommendation_api_v1.json)，ID urn:dianzi:recommendation-api:v1。旧public_api_v2和extensions_v1不改。响应复用内部严格SubscriptionRecord/Page、RecommendationRecord/Page、ReportReceipt/Page的字段；不输出PreparedGeneration/ActorReference、model input或秘密。Generation简回执另外严格给generation_id、recommendation_ids、partial、gaps、reused、data_mode，不返内部prepare对象。

请求PublicSubscriptionSpec为product_keys、asset_ids、risk_topics（各最多100、不重复、至少一类非空）、minimum_priority整数0–3默认3、enabled默认true。minimum_priority同值映射内部maximum_priority_bucket：0仅最高档、1前两档、2前三档、3全部档；响应SubscriptionRecord.spec返回明确的normalized maximum_priority_bucket。用户/tenant不从请求体取；响应owner只是当前本人记录。PATCH为两种严格互斥对象：expected_version+完整spec，或expected_version+enabled。bool不充当int；未知字段拒绝。

路径采用canonical /v1与前端alias /api/v1：GET/POST /api/v1/subscriptions；GET/PATCH /api/v1/subscriptions/{subscription_id}；POST /api/v1/subscriptions/{subscription_id}/generate；GET /api/v1/subscriptions/{subscription_id}/recommendations；POST /api/v1/recommendations/{recommendation_id}/read（query subscription_id必需）；GET /api/v1/subscriptions/{subscription_id}/reports；POST /api/v1/reports；GET /api/v1/reports/{report_id}；GET /api/v1/reports/{report_id}/export（两者query subscription_id必需）。读列表limit默认20、1–100，cursor为前一页next_cursor的UUID定位符，必须每次当前owner/tenant过滤，cursor不是权限。响应items与next_cursor，历史报告和current overlay分别呈现。

generate请求只max_candidates（1–200默认200），服务端选当前授权事件、截止时刻与范围，超过2000输入明确partial/input_scope_partial，不信客户端cutoff/验证标记/已准备receipt。当前规则服务无外部模型IO，本入口返回200已完成简回执；以后转异步须新version合同，不能把202接收当成功完成。POST /api/v1/reports请求subscription_id、generation_id、frequency(day/week)、max_items(1–200默认20)；报告截止从既有generation取，不回填历史事实。

导出GET执行新的当前授权/来源/资产/内容hash校验，返回与ReportReceipt相同严格JSON、application/json、服务端UUID固定下载名。不能用旧前端缓存生成“授权导出”。不发送外部消息。订阅退订是PATCH enabled=false，保留历史，不删除数据库。已读返回完整RecommendationRecord，由服务回执后更新页面。

权限：本轮cookie会话+READ_PUBLIC，本人非空tenant；涉及资产须READ_ASSET。POST/PATCH要求现有Origin/CSRF校验，READ_PUBLIC不授予修改事实。APIkey写配置未开放；未来readonly协议另适配共享服务。401清会话、403拒权限、本人/跨owner未知资源统一404、CAS409、输入400、依赖503；RFC9457无原始异常/秘密。服务未装配返回503 not_configured，不能伪造空列表。body/list/export有界，过大明确错误或分页，不静默删证据。

兼容/迁移：新增prefix与v1schema，旧接口不变；PG0027持久服务、root挂载后才产品可用。回滚关闭新router，保留不可变历史；不自动downgrade。测试：schema正负例/重复字段严格JSON、两owner/租户、CSRF/CAS/退订/已读、partial、历史current、hash失败/403后清数据、真实浏览器完整操作与JSON导出。本次契约不代表R15/R17/R18完成。

本次写作结束时间：2026-10-16T12:51:58+08:00
最后更新时间：2026-10-16T13:13:42+08:00

修订记录：2026-10-16T13:13:42+08:00，沿现有canonical /v1与alias /api/v1纠正未提交路径草案；已读/报告详情/export显式subscription_id绑定；新增generate/report请求与回执defs。
