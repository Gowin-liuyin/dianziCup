# CR-R18 · MCP HTTP transport的逐请求身份

文档首次创建时间：2026-10-17T06:28:51.143+08:00
状态：approved_for_implementation；新独立审查与真实客户端证明另需完成。

现MCP仅stdio，HTTP request context返回not_configured。允许指定SDK作者新增成熟官方mcp2.3.0的Streamable HTTP入口，并在mcp_adapter的现server构造器添加内部可选request-bound client factory。旧stdio调用签名/默认两工具discovery与错误/预算/取消契约保持；HTTP用明确六工具profile、每请求Bearer创建并关闭独立DianziClient，不复用跨身份固定client，不输出credential。四现GET真实接线可先验证，ask/check仍委托真实后端错误，不能fake或模板成功。

HTTP所有协议请求须受身份验证，包括initialize和list_tools；复用后端现鉴权，限定内部APIbase配置不来自请求，Origin/Host/body/deadline/concurrency及8000 token预算受控。若以最小已鉴权list_sources探测身份，明确额外一次read配额消耗/失败分类，不冒称免费。无任意URL/shell/SQL，旧stdio不得受HTTP request credential影响；取消/close只回收自身。

唯一修改范围sdk/python/ai_intel_client/mcp_adapter.py和新增http transport module/直属tests/docs；不得改公共schema/后端auth/迁移/lock/全局用户配置。只复用已锁mcp/httpx/anyio，不加依赖或另一套PG业务状态。OAuth具体PG issuer/选定客户端授权流仍属于后续必须完成的R18切片，不把Bearer key或metadata配置存在当OAuth已通过。没有实际issuer就诚实not_configured，不伪发token、不用内存数据库替代授权事实。

兼容旧包安装和stdout纯协议，新的HTTP入口先本机loopback、不开公开部署。测试含两用户交错/重复或缺失header/401403429/Origin及DNS rebinding/下游失败/取消/close/完整output schema；fixture只unit/contract，真实backend和Codex/Claude live另由Root排。回滚停止本地HTTP入口及恢复adapter factory，保留PG事实/账号/历史，无数据迁移。
