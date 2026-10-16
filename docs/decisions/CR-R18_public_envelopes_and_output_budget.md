# CR-R18 · 公开结果封装与输出预算

文档首次创建时间：2026-10-16T09:12:52+08:00
本次写作开始时间：2026-10-16T09:12:52+08:00
状态：approved_for_implementation；本合同和生产接线仍待独立审查。
授权依据：用户批准 CR-R09/R18 的 API、SDK、MCP、四态和输出预算；没有削减功能、改变评分或盲测。

## 变更与兼容性

新增 `contracts/schemas/public_api_extensions_v1.json`，ID `urn:dianzi:public-api:extensions:v1`。其中14个旧定义从冻结 v2 完整复制，结构逐个相等；原文件、八对象及其 additionalProperties=false 不变。新增10个 common 定义：RiskFinding、RiskSummary、StackCheckEnvelope、VulnerabilityPage、VulnerabilityDetailPage、SourceDescriptor、SourcePage、TaskDescriptor、PublicProblem、TaskResultEnvelope。当前 schema SHA256 `4ccc4337586137a407359a1c4a59dc5d92081a2f4b50ee32cc53fac16095d50b`；原 v2 canonical SHA256 `1c12e4dee3682a531f35f776760da4a97e47eab65564e28e93f9b026382a17f3`。

`/api/v1/stack/check` 默认保持原 StackCheckResult。新版客户端显式请求媒体类型 `application/vnd.dianzi.public-envelopes.v1+json` 才取得 StackCheckEnvelope；旧客户端缺风险摘要仍 CLI=2。其它已有 ask/四态输入不扩大字段。新 sources/vulns/tasks 使用新增封装。当前 TaskDescriptor 仅描述 ask/stack_check；10MiB/10000组件上传、报告任务和订阅的完整合同须在对应 R15/后续 R18 切片冻结并扩展版本，范围没有取消，不能用本片签整 R18。

## 风险判定

指定策略 `r18-risk-policy-1`。风险显示采用R18显式归一化分带（参考 [FIRST CVSS v3.1 rating](https://www.first.org/cvss/v3.1/specification-document)，并保留原来源版本/等级；CVSS v2分数也按本应用策略显示，不能称其源等级具有critical名称）：0 none、(0,4) low、[4,7) medium、[7,9) high、[9,10] critical，默认 minimum_severity=high；合法版本2.0/3.0/3.1/4.0。每条 RiskFinding 必须关联当前已支持的适用性研判/已发布规则版本，以及**同事件**经既有证据 validator 核验的 CVSS claim 和完整引用。模型假设、裸 source_score、EPSS/KEV、服务暴露数或自然语言都不能代替它。引文语义、当前 ACL、冲突和版本由共享 PG 服务在最终事务核验，JSON 格式校验不能代替业务支持判断。

confirmation=confirmed 必須有至少一个达到本次最低等级的当前 finding。来源等级不消除冲突；冲突仍 conflict。coverage 是**本次明确查询/研判范围**的完成状态；无命中、缺版、unsupported、无分级、缺证据或过期都不能当 complete/none_confirmed。CLI执行错误3；存在已确认阈值 finding 为1且同时显示未知；无该finding但任意 unknown/conflict/partial/stale 为2；只有所有请求组件在完整当前查询范围得到有证据的排除或明确有分级研判、且无达到阈值finding时才0，显示“本范围无确认高风险”。不宣称没有漏洞或PoC运行成功。

RiskSummary component indices 必须在真实输入范围内，重复finding/相互矛盾摘要、score/severity不一致、finding与assessment/claim事件不一致都拒绝。schema已校验基础grade分界、required引用和confirmed阈值；跨数组一致性与最终 PG 资格在 producer/SDK typed validator 再验，本片未实现，不能称CLI0/1已运行。

## 来源与任务

SourceDescriptor只投影当前 PG 可见来源和实际持久化观测，不返回 secret_ref/凭据/任意源正文；未采集或缺证据的健康必须 never_polled/unknown，不能因 enabled=true 就 healthy。分页最多100，cursor最多2048字符，服务端游标须绑定principal/有效权限、查询、scope epochs和排序；ACL/epoch改变拒绝继续，不能只按客户端cursor相信owner。

TaskDescriptor取PG九种真实job状态（含blocked），terminal不伪用原queued TaskHandle。不同task_type只接受对应result；queued/running/retry_wait/waiting_approval没有答案；succeeded必有结果且无error/pending/failed；failed/cancelled/blocked显式PublicProblem且无伪成功。step列表最多100，各完整事实/必要引用作为分页单元，不能切断support或去掉unknown来凑页。

## 输出预算、迁移与回滚

指定 `r18-output-budget-1`：tiktoken==0.14.0 / o200k_base，最终 CallToolResult 的 structuredContent、TextContent与continuation整个紧凑JSON ≤8000 tokens且UTF8≤1MiB。这是协议词表预算，不能冒称DeepSeek/Anthropic计费tokens。词表只在部署准备时从官方固定URL获取，SHA256 `446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d`，3613922B；缓存工作区外。运行必须先核cache digest，缺失/损坏返回not_configured，禁止 tiktoken 隐式下载或字符估token。完整单元超限返回完整引用/摘要hash/授权原文入口及明确限制，不能削事实后伪complete。词表准备实际offline3 roundtrips/network0；最初仪器patch.mock AttributeError的exit1原日志保留。

兼容迁移为新增profile/client显式opt-in，不重写旧答案/资产/规则或降级数据库。回滚关闭新媒体类型/公开入口，保留原v2和历史、证据、key撤销记录。所有持久化迁移仍由主控0023–0026前向接入；本schema没有执行DDL。API Key ask限流必须外部IO前与新job幂等/预算同事务只计一次，最终再锁当前身份，不在模型调用后才限流，也不重放重复计费。

## 任务与测试影响

R18/T04/T32/T35/T51、R11/R12/R14/R15/R16/R20；原验收、金标、分母、60%全仓覆盖门不改。本片23个隔离schema合同case passed；最初把纯JSON合同套全仓coverage导致23passed但coverage2%/exit1，原日志保留。后续明确--no-cov只作JSON合同检查，完整全仓套件尚未运行；本子集触发原覆盖门exit1，门槛未撤销或调低。初style4长行、runner缺check=False各exit1修正后style/format0。API/PG/MCP新版/八千词完整输出/浏览器/客户端/live/manual均待实际接线与独审。

本次写作结束时间：2026-10-16T09:12:52+08:00
最后更新时间：2026-10-16T10:23:55+08:00
证据截止时间：2026-10-16T09:12:52+08:00

修订记录：2026-10-16T09:26:01+08:00；明确应用归一化等级与原CVSS版本等级不同，原分数/claim不改；澄清初子集覆盖门真实exit1。

修订记录：2026-10-16T10:23:55+08:00；831c61f收紧新TaskDescriptor.poll_uri UUID分组；原14defs不变，独立28+97通过。旧23/root初始schema和原红保留。新source/contract摘要已同步，不放行整R18或生产接线。
