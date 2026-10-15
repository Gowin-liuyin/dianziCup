# CR-R04 / R05 · 受控JSON POST补充

首次创建/本次写作开始/结束/最后更新时间：2026-10-15T13:33:31+08:00。状态awaiting_review；记录者/root；属于既有R03/T08/R05/T18已授权接口能力，无评分/金标/来源或费用边界变化。

新行为：共享可信外部网关允许有界JSON POST，保留原GET合同；请求bytes1..1MiB，固定Content-Type，额外普通头只允许anthropic-version日期；凭据精确origin注入，所有重定向失败，单次网络尝试，不跟进/改为GET、不泄漏正文或秘密到下一origin。响应大小/TLS/固定peer/绝对deadline/共享并发/错误正文不读沿用既有合同。仅复用传输基础，无新依赖/schema或任意URL/shell/SQL工具。模型配置和数据外发仍须由认证上下文与批准provider决定，接口存在不代表上游可用或可以发送私有资产。

兼容：旧fetch和request GET默认参数不变；新POST是keyword-only。现有URL指纹不宣称涵盖POST body，prompt/schema/payload摘要由模型层明确记录。迁移无；回滚为停止新模型调用并还原本小接口，保留原任务/用量/失败，不启用fixture后备。影响R05/R08需要POST的受控供应商；对应验收是body/headers大小、私有输入、无重定向、真实HTTP错误/超时、schema和原GET回归。root20新cases及512相关通过，独立审查未发生，正式live0。
