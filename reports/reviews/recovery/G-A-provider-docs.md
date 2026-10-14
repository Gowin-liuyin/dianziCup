# G-A / R00：模型与测绘供应商官方接口核定

状态：`awaiting_review`（文档核定）；产品实现、账户能力与 live 验证未在本任务执行。核定时间：`2026-10-14 21:11:36 +08:00`，时区 `Asia/Shanghai`。代码基线：`codex/full-delivery-recovery@b8199ce5dd0a7920ce5770e4f580fe23e0fe9f6b`。

本任务只新增本报告与 `reports/runs/recovery_provider_docs_20261014/` 证据索引，不修改源码、配置、合同、依赖、进度或其他报告；不 commit、push 或自行 accepted。进入时工作树已有并行 R00 改动，全部保留。已读 AGENTS、执行索引、恢复方案 §5/6/8、R05/R08/R13、状态与交接，以及指定的 Ponytail 5.2.0 技能。

输入是用户指定的 DeepSeek V4.1 Flash、两种 API 风格与四个平台名称；输出是官方资料可支持的接口矩阵、未定字段、适配建议和最小补充信息。此次产品 API 调用次数为 **0**，未读取环境凭据或账户页面，未请求资产数据，未下载模型。公开文档中的能力声明不升级为 `live_verified`。

## 1. 结论与三类模型能力

| 能力 | 官方核定 | R05 可实行的决策 | 尚缺什么 |
|---|---|---|---|
| 生成 | 当前 V4.1 Flash 的请求标识是 **`deepseek-flash`**。旧 `deepseek-v4-flash` / `deepseek-v4-flash-vision-exp` 暂时路由至新 Flash；不能猜 `deepseek-v4.1-flash`。 | 两种风格均显式发送已批准的 `deepseek-flash`，记录请求标识、响应 model、协议、文档核定时间和可获得的模型元数据。 | 凭据存在性由主控维护；实际鉴权、输出、耗时和用量待受控探测。[官方入口](https://api-docs.deepseek.com/) |
| embedding | 查阅当前 API 导航、模型列表、能力表，并检索官方站点的 `embedding`；没有取得公开 embedding endpoint / model / dimension / batch 合同。 | 保持该能力 `not_configured`；不能以生成接口、哈希向量或 fixture 替代真实 embedding。 | 独立提供者及准确模型标识，或已授权本地模型、权重来源、许可与资源；维度/空间版本须再核定。[官方 API 导航及模型列表](https://api-docs.deepseek.com/api/list-models/) |
| reranker | 官方站点的 `rerank` / `reranker` 检索没有取得公开接口；能力表也未列重排。 | 保持 `not_configured`，不声明 DeepSeek 提供原生 rerank，不把 LLM 打分静默算作选定 reranker。 | 独立重排提供者/model 或已授权本地模型；输入长度、批量上限、score 语义及费用须核定。[官方能力表](https://api-docs.deepseek.com/quick_start/pricing/) |

没有搜索到文档只证明本轮**无法核定**；不是对私有、未来或未公开服务作“永远不支持”的断言。模型列表示例给出 `name=DeepSeek-V4.1-Flash`、`context_window=1048576`、`max_output_tokens=393216`、文本/图像输入、文本输出和 `low/high/max` effort。模型别名不是不可变权重版本，正式冻结仍须保存当次模型元数据及响应可用指纹。[官方模型列表](https://api-docs.deepseek.com/api/list-models/)

## 2. DeepSeek 两种风格与结构化输出

| 协议 | 地址、认证、请求字段 | 返回与限制 | 适配判断 |
|---|---|---|---|
| OpenAI Chat Completions | base URL `https://api.deepseek.com`；`POST /chat/completions`；`Authorization: Bearer`；`model`、`messages`，显式 `max_tokens`。 | 文本位于 `choices[].message.content`；保留 `finish_reason`、`model`、`system_fingerprint`、`usage`。`response_format.type` 只有 `text/json_object`。SSE 结束标志 `[DONE]`；不可假设独立 usage-only chunk。 | 第一条真实结构化生成可使用 JSON object + 本地完整 schema 校验。`finish_reason=length/content_filter/aborted/insufficient_system_resource` 不能算正常成功。[Chat API](https://api-docs.deepseek.com/api/create-chat-completion/) |
| OpenAI Responses | 同一 base URL；`POST /responses`；`model`、`input`/`instructions`，显式 `max_output_tokens`；`text.format={type:json_schema,name:…,schema:…}` 有文档支持。 | `status` 为 completed/incomplete/failed 等，`output` 的 message/content/output_text 提供正文，`usage` 提供输入/输出/推理 tokens；不得自行添加未文档化的 `strict` 字段。 | 可实现 JSON Schema 输出适配，仍对业务值、引用支持及 schema 作本地校验。`max_output_tokens` 包括推理 tokens。[Responses API](https://api-docs.deepseek.com/api/create-response/) |
| Anthropic Messages | base URL **`https://api.deepseek.com/anthropic`**；官方示例为 Anthropic SDK `messages.create`；`x-api-key`；`model=deepseek-flash`、`max_tokens`、`messages`、`system`。 | `output_config` 仅 `effort` 支持；`thinking.budget_tokens`、`top_k`、`citations`、`tool_result.is_error` 等忽略，document/search_result 等不支持。tools 的 name/description/input_schema 支持。 | 有 Anthropic 格式兼容，不代表 Claude 所有特性。结构化回答采用文本提示 + 本地 schema 校验和至多一次受限修复；不能宣称 Anthropic JSON Schema 严格输出已支持。[DeepSeek 兼容表](https://api-docs.deepseek.com/guides/anthropic_api/) |

Anthropic 标准 Messages 路径为 `POST /v1/messages`；与 DeepSeek 指定 base URL 组合时，SDK 路径对应 `/anthropic/v1/messages`。这是由官方兼容配置与标准 API 路径得出的**适配推断**，此次未实际调用。实现时应复核所用 SDK 的 URL 合成并经网关发送，避免重复添加 `v1`。[Anthropic 标准路径](https://platform.claude.com/docs/en/api/messages/create)

JSON object 模式需要 system/user 提示含 `json` 与目标示例，且可能返回空内容；不能把“可解析 JSON”当作“业务 schema 合格”。截断、空文本、坏 JSON、额外字段、拒绝与证据不足各自保留失败状态。[JSON Output](https://api-docs.deepseek.com/guides/json_mode/)

Chat 工具 strict 是 `/beta` 的单独能力，支持有限 JSON Schema 类型；所有 object 属性必须 required、additionalProperties=false。不要为第一条生成路径强行把现有完整业务 schema 改成 Beta 子集，也不要把生成的函数参数直接当工具执行权限。[Tool Calls](https://api-docs.deepseek.com/guides/tool_calls/)

Responses 是无服务器会话存储的接口；完整上下文由本项目持久化并按需重送，不能依赖 `previous_response_id`。流式终止事件为 `response.completed/incomplete/failed`，与 Chat 的 `[DONE]` 分开解析。内置 web_search/file_search/MCP 等工具被忽略，不可绕开本项目工具网关。[Responses 兼容指南](https://api-docs.deepseek.com/guides/responses_api/)

Anthropic 对未支持模型名会自动映射 Flash，`claude-opus*` 映射 V4 Pro。因此适配器要在发出请求前校验批准模型，不借供应商静默映射实现配置容错；Anthropic returned model 必须再核验。[模型映射](https://api-docs.deepseek.com/guides/anthropic_api/)

## 3. 测绘查询与聚合矩阵

以下为公开官方文档合同，不是本账户权限或实际返回的认证。FOFA / Hunter / Quake / ZoomEye 账户信息接口也未调用。

| 平台 | 查询与认证 | 聚合、明细和计数 | 可直接支持的来源 |
|---|---|---|---|
| FOFA | `GET https://fofa.info/api/v1/search/all`；例中 query `key` + 标准 Base64 `qbase64`；可选 `fields,page,size,full,r_type`。默认 fields=host,ip,port、size=100；最大10000，cert/banner限制2000，body限制500。 | 独立 `GET /api/v1/search/stats`；`qbase64` 与可选 `fields`，示例包含 key。返回 `size`、`distinct`、`aggs[field][{name,count}]`、`lastupdatetime`，没有 results。各字段仅前5，不能求和为总量。统计字段可选 protocol/port/country 等，拒绝 domain/title/fid 等可能携身份信息的桶。 | [查询](https://fofa.info/api)、[聚合](https://fofa.info/api/stats/statistical) |
| Hunter（奇安信鹰图） | `GET https://hunter.qianxin.com/openApi/search`；必填 `api-key`、`search`（RFC4648 base64url）、`page,page_size`；可选 `start_time,end_time,is_web,status_code,fields`。无需自报 email/account 参数。 | 公开个人/企业接口导航没有独立 count/aggregation endpoint。`data.total` 与 `data.arr` 同返；`fields` 可缩减但没有文档保证“只返回总数”，`page_size=0` 未文档化。返回的明细必须在网关立即丢弃。`data.time` 不是文档化观测时间。 | [认证](https://hunter.qianxin.com/home/helpCenter?r=5-1-1)、[个人查询](https://hunter.qianxin.com/home/helpCenter?r=5-1-2)、[企业查询](https://hunter.qianxin.com/home/helpCenter?r=5-2-2) |
| Quake | `POST https://quake.360.net/api/v3/search/quake_service`；头 `X-QuakeToken`，JSON `query`；`start,size,include,exclude,ignore_cache,latest,start_time,end_time` 等。查询总量示例位于 `meta.pagination.total`，同时有 data 明细。 | 原生聚合 `GET /api/v3/aggregation/quake_service` 列允许字段，`POST` 同路径用 `query,aggregation_list`（最多2字段）。size 默认5、最大10000；ignore_cache=false、latest=true；返回 `data[field][{key,doc_count}]`，示例 meta={}，不保证总数。可选 unique_ip 等，但其返回形态未取得示例，须探测而非猜测。 | [官方帮助第4章 API接口](https://quake.360.net/quake/#/help) |
| ZoomEye | base `https://api.zoomeye.ai`；`POST /v2/search`；头 **`API-KEY`**，JSON必填 `qbase64`（标准Base64）；可选 fields/sub_type/page/pagesize/facets/ignore_cache。默认 fields=ip,port,domain,update_time，pagesize=10，最大10000，sub_type=all。 | `facets` 为逗号分隔 country/subdivisions/city/product/service/device/OS/port；查询同时返回 `total` 与 `data` 明细。公开文档没有 standalone aggregate endpoint，也未给 facets bucket 的完整响应类型，不能沿用旧 v1 matches/facets 结构。pagesize=0 未文档化。 | [当前 API v2 查询](https://www.zoomeye.ai/doc#asset-search)、[认证](https://www.zoomeye.ai/doc#authentication) |

Quake 聚合字段白名单首批可限定 country/country_code、port、service；禁止 ip/domain/unique_domain 产生可识别明细桶。`unique_ip` 只能在确认是标量基数统计而非 IP 列表后接入。服务数据按 IP+端口+时间计量，主机模式按独立 IP 计量，两者不可混用。Quake `code=0` 才是业务成功；权限、积分、限速及语法错误需按 message/code 分类。文档 code 表称 int，但错误表又有 q3011 等字符串，解析必须留意这一官方表内不一致。[同一官方帮助：第4章、第6章](https://quake.360.net/quake/#/help)

FOFA `distinct` 描述列支持 server/icp/domain/title/fid，但例中还有 distinct.ip；应记录差异，不把例中 ip 当成所有账户的稳定保证。`consumed_fpoint/required_fpoints` 在不同示例注释的“应扣/实扣”描述有差异；保存字段名与探测响应，不先猜计费语义。[FOFA 聚合](https://fofa.info/api/stats/statistical)、[FOFA 查询](https://fofa.info/api)

Hunter 个人可选返回字段包括 country/province/city、component、updated_at 等；企业额外有 whois/body/vul_list 等。公网链没有使用这些额外明细的需要。分页上限不能从“最多10000个结果”推导为 page_size=10000；后者在查询参数表未给上限。[个人查询](https://hunter.qianxin.com/home/helpCenter?r=5-1-2)、[企业查询](https://hunter.qianxin.com/home/helpCenter?r=5-2-2)、[检索/导出限制](https://hunter.qianxin.com/home/helpCenter?r=4-4)

ZoomEye 参数表写 facets 的 `OS`，官方 SDK 示例通常写 `os`。具体大小写接受范围应由小探测核定，不在未核定时强改。`facets` 列表是声明，普通 asset-search 响应例未展示其形态；空 facets 和未请求 facets 的语义也需要验证。[API v2](https://www.zoomeye.ai/doc#asset-search)、[当前官网链接的官方 SDK](https://github.com/zoomeye-ai/ZoomEye-python)

## 4. 账户、限额与费用边界

| 平台 | 官方资料可核定 | 本账户仍未知 |
|---|---|---|
| DeepSeek | Flash 每百万 tokens 的美元价格：缓存命中 off-peak/peak 0.003/0.006，未命中0.15/0.30，输出0.60/1.20。Peak 为工作日 UTC 01–04/06–10，排除中国公众假期；价格可能变化。 | 实际余额、账户服务可用性、当次计费与用量；本探测花费0产品API调用，不承诺未来费用。[价格](https://api-docs.deepseek.com/quick_start/pricing/) |
| DeepSeek 限制 | 文档 Flash 账户级并发2500，超限HTTP429；等待期可能有空行/SSE keep-alive，10分钟未启动推理会关闭连接。 | 本项目应设置更小预算与deadline，不把官方并发上限作为获准批量范围，也不拿keep-alive刷新总deadline。[限额](https://api-docs.deepseek.com/quick_start/rate_limit/) |
| FOFA | 一般调用建议 <2请求/秒；统计聚合5秒/次，统计/Host权限随会员等级。`/api/limit` 泛称账号信息主要 email/key；详细 query/stats 示例只有key，构成资料不一致。 | email是否为本账户现行请求必要项、等级、聚合权限、精确F点价格/扣费。可先经网关核定 `GET /api/v1/info/my?key=…`：文档只列key，返回email、vip_level、remain_api_query/data等。无需现在重复向用户索取邮箱。[限制](https://fofa.info/api/limit)、[账号](https://fofa.info/api/info) |
| Hunter | API扣个人积分；资产查阅/导出通常1条1分，查询0结果仍可1次1分；付费语法或超出近30天仅扣权益积分。账户接口 `GET /openApi/userInfo` 只要api-key，个人/企业响应有额度字段。 | 当前账户类型、免费/权益积分、实际导出限制、请求速率；文档没有提供稳定数值RPS。缺省/−1含义在官方账户页称无相关限制，不应把它作为允许无界调用。[计费](https://hunter.qianxin.com/home/helpCenter?r=4-3)、[积分](https://hunter.qianxin.com/home/helpCenter?r=7-1)、[个人账号](https://hunter.qianxin.com/home/helpCenter?r=5-1-4)、[企业账号](https://hunter.qianxin.com/home/helpCenter?r=5-2-4) |
| Quake | Key绑定身份与接口权限；UTC起止时间筛选仅付费会员。免费调用福利耗尽后返回1条资产消耗1积分；`GET /api/v3/user/info` 获取角色/credit/persistent_credit。文档提示不同等级有速率限制。 | 本账户角色、免费剩余次数、精确RPS、聚合请求计费（文档没有单独可核定费率）及 unique_ip 形态；不得为探额度访问未收录接口。[官方帮助第4章](https://quake.360.net/quake/#/help) |
| ZoomEye | `POST /v2/userinfo` 只需API-KEY；返回 subscription.plan/points/zoomeye_points/end_date。公开套餐API RPS：Free0.5、Personal1、Professional1、Business2、Corporate5，Enterprise自定；聚合项数量也随等级。ZoomEye Point对应1条结果。 | 当前订阅/余额、聚合额外消耗与重放/cache成本。ignore_cache 为Business及以上能力；未探测前不默认可用。[账户](https://www.zoomeye.ai/doc#user)、[套餐](https://www.zoomeye.ai/pricing) |

账户接口会返回邮箱、电话、token等私人或认证字段，后续探测**仅提取**角色、可用额度、权限与状态，原响应不得进日志、缓存、LLM或此报告。公开套餐表不能替代账户实测；此次没有核定产品使用/再分发许可条款，正式分发前仍需按项目授权记录执行。

## 5. 适配器与安全前置建议

这些是实施建议，不是本轮已实施能力或供应商保证：

1. 复用 `backend/src/ai_intel/infrastructure/models/clients.py` 的结果/校验和现有 network 网关边界。两种生成协议分别编解码，领域层共享生成结果；不把SDK直接绕网关发请求。
2. R03 首次 live 前补**精确认证键脱敏**。当前 `SENSITIVE_QUERY_KEYS` 缺 Hunter 的 `api-key`；`SENSITIVE_HEADERS` 缺 Quake 的 `x-quaketoken` 和 ZoomEye 的 `api-key`。已有 `x-api-key` 只覆盖 DeepSeek Anthropic。需验证大小写、URL编码、请求异常、重试、trace及响应账户对象都不泄密。此结论来自本地只读代码，尚未修复。
3. R08 公网链优先使用原生聚合。可输出固定 schema 的非负整数 total/合法非身份桶、query_id/query_version、retrieved_at、TTL和局限。Hunter/ZoomEye若只能查询带明细的API，先请求最小文档化页与非身份fields，并在网关解析后丢弃整段 arr/data。总数缺失/权限失败不得用0代替；供应商原响应禁止debug dump或SDK自动磁盘缓存。
4. Quake aggregation top-N不能提供全量总数时，显示“仅统计分桶、总量未知”，不求和造总数。需要 total 时经预算核定 search 的最小页+立即丢明细，或先核实原生基数统计能力。
5. R13 与公网链分开：认证上下文授权资产→服务端限定ip/domain条件→FOFA被动查询→范围内观察。请求体不可扩展租户或资产范围。`lastupdatetime` 在查询字段表需专业会员及以上；缺失则 observed_at未知，retrieved_at不能替代它。[FOFA字段权限](https://fofa.info/api)
6. 在R05/R08核定配置中明确 connect/read/total deadline、输出/响应字节上限、最大请求次数、token预算与重试预算。可用初始候选 connect=5s、read=30s、total=60s；这是本地建议，需以网关合同和真实延迟验证，不宣称上游SLA。深任务走异步并保存真实完成时间。普通生成一次、格式修复至多一次；网络超时后的计费可能未知，不自动无限重试。
7. HTTP错误之外还检查业务code和终止状态。DeepSeek400/422是请求错误，401鉴权、402余额、429限流、500/503服务失败。有限退避须消费同一调用/费用预算；不得静默换供应商或返回fixture成功。[官方错误表](https://api-docs.deepseek.com/quick_start/error_codes/)

宽泛 Ollama/vLLM 指纹只给公开服务数量，不能自动成为受影响资产数。产品查询模板、数据模式、latest/cache、时间范围与统计单位都要版本化；此次没有验证任何产品表达式的命中率。

## 6. 最小待补信息与可并行部分

| 缺口 | 最小非秘密输入/后续动作 | 影响 | 可继续部分 |
|---|---|---|---|
| embedding与reranker未核定 | 确认选定提供者+官方文档URL+准确model，或已有本地模型位置/版本、许可、资源和允许下载记录；不得再发明文key。 | R05/T18、pgvector真实检索、R12/R21/R22 | 两风格生成编解码、schema校验、错误与网关合同测试 |
| 账户能力未测 | 主控维护secret引用；在已获授权预算中各做最小账户/能力探测，仅保存脱敏元数据。 | R05/R08/R13 live | 按本报告字段实现纯解析和模拟错误测试 |
| FOFA资产范围 | 租户、已授权IP/CIDR/域名范围、用途及外发许可，来自认证/授权记录。 | R13；不能以拥有key视为授权第三方资产 | 白名单查询编译、越界拒绝、未知时间测试 |
| 公网产品模板与计数单位 | 首批产品、确认的查询模板、统计服务还是独立IP；优先沿主控已有明确选择，不重复询问已授权事项。 | R08/F2/P2 | 聚合schema、明细零泄漏、stale和失败分类 |
| 费用和限额 | 引用主控已有预算授权；设每任务的有界调用/token/耗时上限，核定当前余额/配额后启用。 | 所有live和批量探测 | 不收费的文档、unit/contract开发；不自动采购或下载 |

## 7. 真实核验记录与未运行项

- 本地只读命令：`Get-Content AGENTS.md`、执行索引/恢复方案/任务卡/状态/交接/Ponytail；`git status --short`、`git branch --show-current`、`git rev-parse HEAD`；`Get-Content .../clients.py` 与 `.../network.py`。有效读/状态命令均exit0。
- 检索优先使用 `rg`。两次搜索传了不存在的 `backend/app/…`、`src`路径，另一次PowerShell路径通配写法不能传给rg；stderr如实见查询索引，不算业务测试失败。已改为正确 `backend/src/ai_intel/infrastructure/` 只读核对。
- 官方公开网页使用 web 搜索/open；FOFA/Hunter/Quake/ZoomEye的SPA改用后台浏览器只读DOM。未登录、未接受协议、未填写或提交表单、未调用页面提供的测绘工具。一次子Agent不支持visibility参数，去掉该参数后正常建立只读页，不改变账户设置。
- DeepSeek多个带末尾斜线页面初次open超时，官方无末尾斜线路径重开后取得Chat/JSON/Models/Responses/限额/错误正文；Tool Calls仍以官方搜索正文支持其Beta声明。Hunter web open403，官方浏览器帮助正常加载；Quake web仅JavaScript提示，浏览器第4章可读；FOFA/ZoomEye web正文不完整，浏览器取得完整官方参数表。
- `unit/integration/live = not_run`，产品live请求0；人工文档核定完成但没有独立验收。没有编造输出准确率、调用成功率、性能或账户剩余额度。
- 本报告文档范围检查将在 `reports/runs/recovery_provider_docs_20261014/local_checks.txt` 记录；它不计为产品unit/contract测试。
- 首次文档检查的正则把内联URL后的Markdown字符纳入URI，PowerShell产生非终止转换错误但退出码仍为0；该次“passed”输出无效，保留在 `local_checks_initial.txt`。修正为仅解析Markdown链接并启用终止错误后重跑；只以后者为文档检查证据。

检索问题、官方URL、来源更新时间、获取方式和未定字段见 [证据索引](../../runs/recovery_provider_docs_20261014/query_log.json)。索引是本轮摘要，未转载原网页或保存资产明细。

## 8. 评分证据与下一步

本轮为R00提供R05/R08/R13资源前置事实，支持F2/F3/A1/E1的可审查实施输入，不提升这些评分项的完成/优秀状态。无合同变更；两种API兼容、独立embedding/reranker与公网/授权资产分链遵循现有恢复合同。

下一步建议：先把网关认证名称脱敏缺口纳入R03安全验收；主控登记独立embedding/reranker最小选择；R05按确证的 `deepseek-flash` 与两种协议完成真实生成切片，R08先核定Quake聚合或Hunter最小查询后丢明细的账户能力，R13等待既有授权资产范围。此文档任务到此停止。
