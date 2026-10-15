# R05 · 共享网关的有界JSON POST准备切片

首次创建/本次写作开始/结束/最后更新时间：2026-10-15T13:33:31+08:00。
实现者/root；状态awaiting_review；R05整体partial/not_started实际模型；G-A/B未过门，本包是安全独立接口准备。

既有网关只支持GET，无法发送OpenAI Chat Completions或Anthropic Messages请求。复用现有numeric-IP固定、Host/SNI、CA验证、绝对deadline、共享并发、响应大小/错误分类与凭据脱敏；新增post_json只发送1..1MiB bytes、固定Content-Type、只允许受控anthropic-version日期头；Host/认证/Content-Length不由调用者覆盖。凭据仍只由OriginCredentials向精确HTTPS origin注入。POST所有301/302/303/307/308拒绝，不把输入或鉴权转发到下一地址；没有网络重试或GET成功后备。JSON业务schema在上层模型适配器校验，本层只限传输资源，不假装已经实现模型输出校验。

必要新增仅PinnedHttpTransport.request的GET/POST关键字和NetworkGateway.post_json；两入口共用_bounded_fetch避免复制预算/IO，旧fetch公共参数和GET行为保持。request_fingerprint_sha256继续是既有URL指纹，不能当作POST payload/prompt指纹或缓存键，模型层必须另存prompt/schema摘要。无依赖/PG/public DTO迁移。

实际验证：第一次相关运行511passed但新oversized参数未指定短test id，pytest把1MiB合成值放进PYTEST_CURRENT_TEST，Windows32767环境变量上限造成setup/teardown 2errors；不是HTTP产品负例失败。保留network_regression.log/tests.xml原始失败，仅给3个新参数显式ids，未改输入/预期/阈值。post_fixed20/20；fixed/完整相关512passed/0fail/skip，raw coverage 2823/4175=67.61676646706587%。纯unit396passed raw 2602/4141=62.8350639942043%，静态Ruff/format/mypy65当时版本通过；该代码快照尚未包括后来的API挂载，不能给API背书。所用全部socket fixture明确隔离，不计live。实际命令/时刻/退出码均在run目录receipt；post_fixed直接命令未单独记录起止，写历史未记录，不补造。

两个真实请求协议的官方依据：[OpenAI Chat API](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)、[DeepSeek Chat](https://api-docs.deepseek.com/api/create-chat-completion/)、[DeepSeek Anthropic兼容](https://api-docs.deepseek.com/guides/anthropic_api/)。DeepSeek网页直接open多次timeout，官方检索正文及既有provider-docs报告保留，OpenAI页面实际open读取；文档不当成本机实际调用事实。

unit/contract/security仅上述传输切片passed，integration/frontend/e2e/live/manual=not_run；产品模型调用0、费用unknown；生成codec、embedding/reranker、pgvector索引和问答还要实现。新非作者必须固定候选复跑后才可有限验收；不签整R05/T18/G-B。后续若模型服务301/307，明确配置错误而非放宽自动重定向；业务失败由PG唯一调度与调用预算处理。
