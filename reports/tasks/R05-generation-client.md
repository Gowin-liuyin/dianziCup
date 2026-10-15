# R05 · 两种真实生成wire客户端工作包

文档首次创建时间：2026-10-15T14:11:15+08:00
本次写作开始时间：2026-10-15T14:09:09+08:00
本次写作结束时间/最后更新时间/证据截止时间：2026-10-15T14:20:31+08:00
作者：/root/r04_knowledge_api（本轮工作包R05-generation-client）
基线：08c4471fd74e882cbbfabf81f890d98f1d7a782d
分支：codex/recovery-r05-generation-client
当前已测集成冻结：4e47a93db8e3039b87755b3d8108963969978361（本包3695c5b + 主控07f5d85的cherry-pick）；backend/src tree=d9b30d9e93395fb3e031691551c8dc5265121bd5
状态：awaiting_review；本工作包实现complete，所列隔离自动验证passed，未独立验收，整R05仍partial。
unit/contract/integration/security：最终所列隔离范围passed；历史失败保留；frontend/e2e/live/manual：not_run。
独立review：主控将派新非作者；未accepted，未push。

## 1. 授权范围与冻结接口

读取当前AGENTS、00执行地图、R05、05模型/外部访问合同、CR-R04-R05_model_post、新Ponytail 5.2 full与OpenAI Docs。主控批准的小接口在2026-10-15T13:42:53+08:00系统时钟登记；消息实际发送秒未单独记载，不倒推。4个固定官方provider目标、2个wire，不允许请求体修改provider/path；Native OpenAI/Anthropic只从可信构造配置approved_model取得，当前无用户产品凭据，本包未配置或试用。DeepSeek仅允许deepseek-flash。

`GenerationRequest`分别承载可信system_text、question、带明确边界的evidence_texts、prompt/schema/model版本、整次max_output_tokens及至多一次格式修复开关。UTF8/NUL/长度/类型严格校验；请求model_version必须等于可信配置。`generate(request,response_schema,content_is_private,egress_granted)`返回经过严格Pydantic验证的`TypedGenerationResult[T]`及每次`AttemptMetadata`；私有外发拒绝在拼body/联网前。业务调用者仍须从认证与PG来源范围取得私有属性/外发许可，不能从客户端body自报；本接口不推断内容天然公开。

response_schema的根与嵌套BaseModel都必须extra=forbid；实际model_validate_json(strict=True)。保存prompt/schema/实际request body/response body SHA256、provider、请求/返回模型、已知finish reason、provider调用ID、起止UTC时点、完整完成耗时、input/output/cache read/cache creation/total token（缺失None）、费用unknown。不保存headers、输入/输出正文或key到元数据；响应ID/模型与文本含已知凭据时拒绝，错误消息固定。格式修复有独立实际prompt/body hash，不能给修复输入套用原prompt摘要。

## 2. 实现与复用

产品/测试6文件：`infrastructure/models/clients.py`直接兼容调整；新增`generation.py`、`json_output.py`、`tests/unit/test_r05_generation.py`、`tests/contract/test_r05_generation_wire.py`、`tests/integration/test_r05_generation_http.py`。没有修改schema、迁移、lock、settings/app/runtime、progress、原金标/分母/阈值。

复用已批准共享`NetworkGateway.post_json`、精确OriginCredentials/SecretStr、固定peer/TLS/SSRF/POST无redirect、绝对RequestDeadline和已有egress policy；复用标准库JSON/hashlib/threading/perf_counter及已锁Pydantic。没有新增SDK依赖、通用provider框架、自动工具执行或fixture后备。新代码必要性：旧clients.py仅验证器和FixtureProvider，无真实IO；本客户端确实通过共享网关发有界POST并读取两种真实wire，已用本地真实socket验证。

输入body单次最大默认256KiB、整次累计默认256KiB（配置硬上限1MiB）；response单次最大1MiB；结构化输出整次默认256KiB；深度32、节点10000；最多2调用（1格式修复），并发默认2最大4，整次deadline默认60最大120秒。每次max_tokens从同一剩余输出token预算取；实际已报output tokens扣除，未知usage按该次全部预留额度保守扣除，不能凭空获得二次预算。认证、quota、HTTP/网络失败、拒绝、截断、工具调用都不重试。格式修复输入和输出字节也计入同一总预算。

legacy validate_structured_output签名与正常结果保持，新增严格JSON拒绝重复键/NaN/Infinity/溢出/无效Unicode/过大结构；原T18-C01–C06全保留，embedding/reranker未在本包发明接口或替代语义向量。新client不使用Legacy GenerationResult的必填usage_tokens字段；真实未知usage为None。

## 3. 官方依据与端点

DeepSeek OpenAI wire固定`https://api.deepseek.com/chat/completions`、max_tokens、json_object和显式JSON指令、thinking disabled，依据[DeepSeek Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)。Native OpenAI固定`https://api.openai.com/v1/chat/completions`，使用max_completion_tokens、不混DeepSeek thinking参数，依据[OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)。本包只实现文本/nonstream/JSON模式，不宣称覆盖所有模型的专用参数。

DeepSeek Anthropic base官方为`https://api.deepseek.com/anthropic`，见[兼容文档](https://api-docs.deepseek.com/guides/anthropic_api/)。请求的`/v1/messages`来自[Anthropic官方SDK源码](https://github.com/anthropics/anthropic-sdk-python/blob/main/src/anthropic/resources/messages/messages.py)，组合固定`https://api.deepseek.com/anthropic/v1/messages`；Native固定`https://api.anthropic.com/v1/messages`。使用x-api-key、anthropic-version=2023-06-01、system独立字段/max_tokens/text blocks，不混OpenAI response_format。

官方list-models文档URL与AnthropicAPI网页读取失败已如实保留为本轮网页工具错误；未根据无法取得页面猜embedding/rerank接口，也未调用需key的models API。官方材料仅用于格式事实，不是改变权限/规范的指令。

## 4. 索引与调用方

修改前CBM独立索引`dianzi-r05-generation-08c4`，trace validate_structured_output无生产调用方；rg只发现原T18合同6例，旧生成类无产品入口。缓存`/tmp/dianzi-cbm-r05-generation-20261015`在仓外，只索引本WT backend/src，排除secret/holdout。

fb955索引905 nodes/4114 edges，trace `GenerationClient.generate → enforce_egress_policy → encode_wire → NetworkGateway.post_json → _fetch/PinnedHttpTransport → decode_wire → strict_json_object/Pydantic → result`；源码/测试与图交叉核对。当前本WT API/worker/UI生产调用方仍为0，明确属于独立接口准备；主控后续接PG证据与问答服务，不能据此验收整R05或首个真实引用回答。

## 5. 实际命令和结果

日志目录`reports/runs/recovery_r05_generation_client_20261015/`。run.py保留每条正式argv/cwd/+08起止/exit/SHA，独立COVERAGE_FILE，不与root或其他WT覆盖。原始探索first/wire_first未单独记录命令秒级时段，XML保留pytest自身时间；后续正式冻结复跑有完整收据。

| 版本/命令 | 起止(+08) | 实际结果/日志 |
|---|---|---|
| fb955纯unit `python -m pytest tests/unit -q --cov-report=json:... --junitxml=...` | 14:03:56–14:04:18 | exit0，479通过/0失败/skip；3081/4754，raw64.80858224652924%，原60门未改；unit_fb955.* |
| fb955针对性unit/contract/HTTP+原T18 | 14:04:18–14:04:24 | exit1，89通过1失败0skip；真实HTTP超时错误分类，target_fb955.* |
| fb955 mypy | 14:03:56–14:03:57 | exit0，69源码文件；mypy_fb955.* |
| fb955 Ruff/format src/tests | 14:03:57–14:03:57 | exit0，155文件格式通过；ruff_fb955/format_fb955.* |
| 9770 cache usage新负例 | 14:00:01–14:00:03 | 15通过3失败；usage_shape_red.* |
| 缓存类型修复工作树 | 14:00:22–14:00:23 | 18合同全通过；usage_shape_green.*（receipt基线9770+未提交修复；随后999提交） |
| 999完整时间定向修复工作树 | 14:02:44–14:02:46 | 2通过；clock_metric_green.*，随后fb955提交 |
| 已知refusal finish reason修复工作树 | 14:09:07–14:09:09 | 1通过；refusal_finish_metadata.*，随后3695提交 |

已通过的新unit边界：两wire正常、native参数区别、未知usage None、各HTTP错误单次、网络失败无retry、拒绝/截断/工具、坏JSON/额外字段/错误类型/重复键/非有限值、一次repair共享deadline和剩余tokens、二次坏输出无第三次、输入/output bytes/output token/总input修复预算、credential输入/回显、私有外发、UTF8/NUL/布尔类型、嵌套extra禁止、schema模型一致、并发等待有界、原legacy正常/负例、完整完成耗时（perf_counter）。

真实HTTP集成每次使用http.client和NetworkGateway.post_json，实际localhost临时socket/HTTPServer；fixture只将DNS返回登记的合成公共IP并替换PinnedConnection.connect路由到loopback。固定生产HTTPS URL/Host/path/header/body仍按真实codec生成；测试不证明真实生产CA/peer/DNS，不能计为DeepSeek live。正常两wire、401/429/503、302不跟随/不给其他origin发key/body、0.2秒服务延迟+0.05总预算是7例；服务器finally shutdown/server_close/thread.join，无新后台服务。未使用真实keys、未读取.env/KEYS、paid/model live调用0，实际费用unknown。

## 6. 问题台账

| ID | 实际触发/预期/结果 | 根因、处理与状态 |
|---|---|---|
| GEN-01 | usage.prompt_tokens_details=[]/false/0应拒绝，却转成空object；3负例实际失败 | `value or {}`误吞false形状；仅None视未知，999b修复，18合同green；已修复 |
| GEN-02 | sleep30ms的完整耗时一次仅记录15ms，不能下调30阈值 | Windows3.12 monotonic实际GetTickCount64/15.625ms分辨率；10探针未再次重现15ms，留真实样本；elapsed用perf_counter，deadline保持网关同一monotonic时基，fb955；定向2pass，已修复/待独立复核 |
| GEN-03 | 本地真实HTTP延迟0.2s、deadline0.05s，有时得到network_failure，预期timeout | 共享PinnedHttpTransport把socket TimeoutError落在OSError通用路径，deadline标记/粗时钟存在竞态；root是唯一owner，作者未在client猜测。target_fb955真实1fail；随后主控07f5d85/本WT4e47a93共同根因修复，最终91+4复验通过；历史失败保留 |
| GEN-04 | 超时fixture服务端向已关闭socket写入WinError10053 | 仅fixture把已关闭的Aborted与BrokenPipe/Reset同处理，20e2提交；未skip测试，不吞产品IO错误 |
| GEN-05 | Python runner以UTF8解码但子进程/终端GBK导致错误输出出现replacement且打印失败 | 设置child PYTHONUTF8与stdout UTF8；保留target_fb955.log/XML/receipt，pytest真实1fail未被覆盖；证据脚本修复 |
| GEN-06 | 显式OpenAI refusal在stop下拒绝，但meta未保留已知stop | 在安全失败对象保留已知reason，3695，定向1pass；无改变拒绝策略 |
| GEN-STYLE | 初版Ruff过长/unused及2长JSON fixture literals | 保留初轮静态日志；只格式、拆同字节literal与unused名称，最终fb955全src/tests exit0；不改gold/指标 |

## 7. 结论与下一步

完成所需最小真实联网客户端、严格两wire和预算/元数据接口。共享HTTP超时根因关闭前不声称本批全通过；最终修复复验见第8节；独立review仍须固定新候选，尤其不能拿479全绿掩盖真实HTTP负例。后续root接真实DeepSeek两wire最小live，保存实际耗时/usage/fee未知与PG引用；embedding/reranker/检索/首回答/浏览器仍待R05其他切片，不能将mock或本地HTTP算这些效果。

源码提交顺序：9770b29 → 999b5a7 → fb95577 → 20e2d48 → 3695c5b。原normal legacy调用兼容；旧生产调用者无，新增生产装配由root唯一负责。测试/扫描/文档不进入accepted或progress；作者交付后释放槽给新独立审查。

首次修订记录：2026-10-15T14:11:15+08:00，真实记录当前冻结、自检及已知共享阻断；后续修复和独立结果追加，不改首次创建时间、不删除失败。


## 8. 主控共同根因修复与最终冻结复验

2026-10-15T14:15:59+08:00：主控07f5d85明确将request/body读取/DNS的TimeoutError转换NetworkTimeoutError，保留其他网络异常的deadline检查；作者只cherry-pick为4e47a93，不在client猜测或下调超时断言。GEN-03已修复并在组合源码复验，原两次1失败日志/XML保留。GEN-04 fixture不对已关闭连接继续日志噪声，产品IO仍按共享层明确分类。当前等待新的独立review，作者未自签。

| 最终组合冻结4e47a93 | 实际+08起止 | 结果/证据 |
|---|---|---|
| 全纯unit（独立COVERAGE_FILE） | 14:12:05–14:12:25 | exit0，480/480，0失败/skip；3082/4760=64.74789915966386%；unit_transport_fixed.* |
| 新unit60+新contract18+真实本地HTTP7+原T18合同6 | 14:12:26–14:12:32 | exit0，91/91，0失败/skip；target_transport_fixed.* |
| 共享transport4定向security负例 | 14:14:39–14:14:40 | exit0，4/4；transport_security_combined.* |
| mypy69源码 | 14:12:05–14:12:06 | exit0；mypy_transport_fixed.* |
| 全Ruff/format src/tests | 14:12:06–14:12:07 | 两项exit0，156文件；ruff_transport_fixed/format_transport_fixed.* |

最新CBM仅本WT backend/src：905 nodes/4119 edges，project dianzi-r05-generation-transport-fixed，仍无产品API/worker调用方；这一限制不因接口准备green改变。root无需重复pick本包4e47a93（已有07f5d85），只按此前5条本包源码提交顺序集成；证据提交SHA另由交付消息给出。

本包所有测试进程已退出，本地fixture HTTPServer关闭/线程join断言通过；未创建长期服务、数据库、队列或持久端口，private key读取0/model paid calls0。正式模型接通、真实CA/DNS/live、浏览器及人工语义评估仍未运行，整R05不可accepted。

修订记录：2026-10-15T14:15:59+08:00，补共享根因修复、最终480/91/4及原始覆盖率；保留首次创建时间与旧失败事实。


修订记录：2026-10-15T14:18:22+08:00，统一最新问题状态与最终复验；证据staged diff check=2仅保留失败traceback/XML空白分隔行末空白，不改日志字节。evidence_index每项提供captured_sha256/captured_size_bytes及Git blob SHA256/bytes；静态扫描仅检查长sk-token形状，没有读取实际产品keys，真实凭据全文/片段扫描由主控集成时执行，本报告不把静态零命中叫真实秘密全扫描。


修订记录：2026-10-15T14:20:31+08:00，封存后仅将5个本包生成coverage SQLite缓存经绝对路径白名单核对移动至仓外C:/Users/yinha/.codex/tmp/dianzi-r05-generation-client-20261015/coverage，保留hash和实际移动收据coverage_cache_move.json；未递归清理/移动，也未动用户或他Agent文件。后续runner默认在此仓外缓存路径使用独立COVERAGE_FILE；既有命令收据中的旧位置是当次实际捕获位置，原raw coverage JSON/XML/log没有改变。
